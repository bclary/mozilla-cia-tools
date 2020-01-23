# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import csv
import json
import re
import sys


TRUNK = set(["autoland", "mozilla-central"])
ALL = set(["autoland", "mozilla-central", "mozilla-beta", "mozilla-release", "try"])

def args_key(*args):
    return ",".join(str(arg) for arg in args)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Associate Task Labels to Task costs.",
        epilog="""

This script matches a costs json file to a tasks json file to
associate a task label to costs and writes a new costs file with the
attached task label.

To obtain the costs file execute a BigQuery containing an sql query of
the form

select w.provisionerId, w.workerType, s.project, s.tier,
       s.suite, s.groupSymbol, s.symbol, s.collection,
       sum(s.execution*1000.0*w.cost_per_ms) as cost
from taskclusteretl.derived_task_summary as s,
     taskclusteretl.derived_daily_cost_per_workertype as w
where s.workerType = w.workerType
and s.provisionerid = w.provisionerid
and s.date = w.date
and s.date between '2019-12-02' and '2020-01-06'
and s.project in ('autoland', 'try')
and s.tier in (2, 3)
group by provisionerId, workerType, project, tier, suite, groupSymbol, symbol, collection
order by provisionerId, workerType, project, tier, suite, groupSymbol, symbol, collection;

and save the results locally to a costs.json file.

Using a source checkout, obtain a tasks json file via

./mach taskgraph tasks --json  > /tmp/tasks.json

Then execute

python %(prog)s --costs=costs.json --tasks=tasks.json 2> costs.err > costs-annotated.csv

or

python %(prog)s --costs=costs.json --tasks=tasks.json --json 2> costs.err > costs-annotated.json

""",
    )
    parser.add_argument(
        "--costs", help="Path to json file containing costs.", required=True
    )
    parser.add_argument(
        "--tasks", help="Path to json file containing tasks.", required=True
    )
    parser.add_argument(
        "--project",
        dest="projects",
        default=[],
        action="append",
        help="One or more of mozilla-central, autoland, ... If not specified, returns all projects.",
    )
    parser.add_argument(
        "--tier",
        type=int,
        dest="tiers",
        default=[],
        action="append",
        help="One or more of 1, 2, 3. If not specified, returns all projects.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results in json format.",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Output no cost warnings.",
    )
    args = parser.parse_args()

    projects = set(args.projects)

    with open(args.costs) as costs_file:
        costs = json.load(costs_file)

    with open(args.tasks) as tasks_file:
        tasks = json.load(tasks_file)

    cost_dict = {}
    for cost in costs:
        cost_key = args_key(
            cost["provisionerId"],
            cost["workerType"],
            cost["project"],
            cost["tier"],
            cost["suite"],
            cost["groupSymbol"],
            cost["symbol"],
            cost["collection"],
        )
        assert cost_key not in cost_dict
        cost_dict[cost_key] = cost

    data = {}

    for task_label in tasks:
        task = tasks[task_label]
        extra = task["task"]["extra"]
        if "treeherder" not in extra:
            continue
        treeherder = extra["treeherder"]

        tier = treeherder["tier"]
        if args.tiers and tier not in args.tiers:
            continue

        provisionerId = task["task"]["provisionerId"]
        workerType = task["task"]["workerType"]
        run_on_projects = task["attributes"]["run_on_projects"]
        # If the suite or groupSymbol are not specified, treat
        # them as wild-cards and use regular expressions to
        # find the matching cost.
        suite = extra.get("suite", ".*")
        groupSymbol = treeherder.get("groupSymbol", ".*")
        symbol = treeherder["symbol"]
        collection = list(treeherder["collection"].keys())[0]

        projects = set()
        for project in run_on_projects:
            if project == "trunk":
                projects |= TRUNK
            elif project == "all":
                projects |= ALL
            else:
                projects.add(project)

        if args.projects:
            projects = projects & set(args.projects)

        for project in projects:
            task_key = args_key(
                provisionerId,
                workerType,
                project,
                tier,
                suite,
                groupSymbol,
                symbol,
                collection,
            )
            if task_key not in cost_dict:
                # We do not have an exact match, so treat
                # the task_key as a pattern and search the costs
                # for matches.
                re_key = re.compile(task_key)
                candidate_cost_keys = set(
                    [key for key in cost_dict.keys() if re_key.match(key)]
                )
                if len(candidate_cost_keys) == 0:
                    if args.verbose:
                        print(
                            "task_key {} has no cost".format(task_key), file=sys.stderr
                        )
                    task_key = None
                elif len(candidate_cost_keys) > 1:
                    if args.verbose:
                        print(
                            "task_key {} has too many cost candidates {}".format(
                                task_key, candidate_cost_keys
                            ),
                            file=sys.stderr,
                        )
                    task_key = None
                else:
                    task_key = candidate_cost_keys.pop()

            if task_key is not None:
                if task_key not in data:
                    task_cost = cost_dict[task_key]
                    task_cost["label"] = task_label
                    data[task_key] = task_cost
                else:
                    task_cost = data[task_key]
                    task_cost["label"] += ", " + task_label

    if args.json:
        print(json.dumps(data, indent=2))
    elif not data:
        pass
    else:
        fieldnames = task_cost.keys()
        csv_writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        csv_writer.writeheader()
        for task_key, task_cost in data.items():
            csv_writer.writerow(task_cost)


if __name__ == "__main__":
    main()
