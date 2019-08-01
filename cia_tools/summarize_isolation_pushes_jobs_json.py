#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging
import re
import sys

from common_args import ArgumentFormatter, log_level_args, treeherder_urls_args
from treeherder import get_repositories, get_repository_by_id, get_bug_job_map_json


re_job_group_symbol = re.compile(r'-I$')
re_job_type_symbol = re.compile(r'-(id|it)$')


def is_isolation_job_group_symbol(job_group_symbol):
    return re_job_group_symbol.search(job_group_symbol)


def is_isolation_job_type_symbol(job_type_symbol):
    match = re_job_type_symbol.search(job_type_symbol)
    if match:
        return match.group(1)
    return None


def summarize_isolation_pushes_jobs_json(args):
    failure_munge_res = [
        re.compile(r'GECKO[(]([\d]+)[)]'),
        re.compile(r'PID ([\d]+)'),
    ]
    def munge_failure(failure):
        for r in failure_munge_res:
            match = r.search(failure)
            if match:
                failure = failure.replace(match.group(1), '...')
        return failure
    def get_test(failure):
        try:
            return failure.split(' | ')[1]
        except IndexError:
            return failure

    data = load_isolation_push_jobs_json(args)
    summary = {
        "revision": data["revision"]
    }

    job_type_names = sorted(data.keys())

    for job_type_name in job_type_names:
        if job_type_name == "revision":
            continue
        if job_type_name not in summary:
            summary[job_type_name] = job_type_summary = {}
        job_type = data[job_type_name]

        for section_name in ("original", "repeated", "id", "it"):
            if section_name not in job_type_summary:
                job_type_summary[section_name] = job_type_section_summary = {}
                job_type_section_summary['failures'] = {}
                job_type_section_summary['tests'] = {}
                if section_name == 'original':
                    job_type_section_summary['job_bug_map'] = []
            section = job_type[section_name]
            run_time = 0
            number_jobs_testfailed = 0
            number_failures = 0

            for job in section:
                if section_name == 'original':
                    job_type_section_summary['job_bug_map'].extend(job['job_bug_map'])
                run_time += job['end_timestamp'] - job['start_timestamp']
                number_jobs_testfailed += 1 if job['result'] == 'testfailed' else 0
                number_failures += len(job['bugzilla_suggestions'])

                for bugzilla_suggestion in job['bugzilla_suggestions']:
                    failure = munge_failure(bugzilla_suggestion['search'])
                    if failure not in job_type_section_summary['failures']:
                        job_type_section_summary['failures'][failure] = {
                            'count': 0,
                        }
                        if section_name != 'original':
                            job_type_section_summary['failures'][failure]['failure_reproduced'] = 0
                    job_type_section_summary['failures'][failure]['count'] += 1

            for failure in job_type_section_summary['failures']:
                test = get_test(failure)
                if test not in job_type_section_summary['tests']:
                    job_type_section_summary['tests'][test] = {
                        'count': job_type_section_summary['failures'][failure]['count'],
                    }
                    if section_name != 'original':
                        job_type_section_summary['tests'][test]['test_reproduced'] = job_type_section_summary['failures'][failure]['failure_reproduced']
            job_type_section_summary['run_time'] = run_time
            job_type_section_summary['jobs_failed'] = number_jobs_testfailed
            job_type_section_summary['jobs_total'] = len(section)
            job_type_section_summary['tests_failed'] = number_failures
            if section_name != 'original':
                job_type_section_summary['failure_reproduced'] = 0
                job_type_section_summary['test_reproduced'] = 0

        job_type_original_summary = job_type_summary['original']

        for section_name in ("repeated", "id", "it"):
            job_type_section_summary = job_type_summary[section_name]

            for failure in job_type_section_summary['failures']:
                if failure in job_type_original_summary['failures']:
                    count = job_type_section_summary['failures'][failure]['count']
                    job_type_section_summary['failures'][failure]['failure_reproduced'] += count
                    job_type_section_summary['failure_reproduced'] += count

            for test in job_type_section_summary['tests']:
                if test in job_type_original_summary['tests']:
                    count = job_type_section_summary['tests'][test]['count']
                    job_type_section_summary['tests'][test]['test_reproduced'] += count
                    job_type_section_summary['test_reproduced'] += count

    if not args.include_failures:
        # Remove failures lists from sections
        for job_type_name in summary:
            if job_type_name == "revision":
                continue

            for section_name in summary[job_type_name]:
                summary_section = summary[job_type_name][section_name]
                if 'failures' in summary_section:
                    del summary_section['failures']
                if 'failure_reproduced' in summary_section:
                    del summary_section['failure_reproduced']

    if not args.include_tests:
        # Remove tests lists from sections
        for job_type_name in summary:
            if job_type_name == "revision":
                continue

            for section_name in summary[job_type_name]:
                summary_section = summary[job_type_name][section_name]
                if 'tests' in summary_section:
                    del summary_section['tests']
                if 'test_reproduced' in summary_section:
                    del summary_section['test_reproduced']
    return summary


def load_isolation_push_jobs_json(args):
    """Load job data from the specified file, collecting the jobs which are
    related to test isolation (group symbol suffix -I) and organizing them
    in a dict according to.

    data = {
        "revision": "...",
        "<job-type-name>": {
            "original": [],
            "repeated": [],
            "id": [],
            "it": [],
        },
        ...
    }
    """
    if args.file is None or args.file == '-':
        push = json.loads(sys.stdin.read())[0]
    else:
        with open(args.file) as input:
                push = json.loads(input.read())[0]

    repository = get_repository_by_id(push['revisions'][0]['repository_id'])
    revision = push['revisions'][0]['revision']
    revision_url = "%s/rev/%s" % (repository["url"], revision)
    data = {
        "revision": revision_url,
    }

    # Find the job_type_names associated with test isolation jobs
    for job in push['jobs']:
        job_type_symbol = job['job_type_symbol']
        job_group_symbol = job['job_group_symbol']
        isolation_group = is_isolation_job_group_symbol(job_group_symbol)
        isolation_type = is_isolation_job_type_symbol(job_type_symbol)
        if isolation_group or isolation_type:
            job_type_name = job['job_type_name']
            if job_type_name not in data:
                data[job_type_name] = {
                    "original": [],
                    "repeated": [],
                    "id": [],
                    "it": [],
                }

    # Collect the test isolation jobs
    for job in push['jobs']:
        job_type_name = job['job_type_name']
        if job_type_name not in data:
            continue
        data_job_type = data[job_type_name]
        job_type_symbol = job['job_type_symbol']
        job_group_symbol = job['job_group_symbol']
        isolation_type = is_isolation_job_type_symbol(job_type_symbol)
        isolation_group = is_isolation_job_group_symbol(job_group_symbol)
        if isolation_type is None and isolation_group is None:
            data_job_type['original'].append(job)
            # Add the job_bug_map object to the original job
            # in order to track which bug was "isolated".
            job['job_bug_map'] = get_bug_job_map_json(args, repository['name'], job['id'])
        elif isolation_type == 'id':
            data_job_type['id'].append(job)
        elif isolation_type == 'it':
            data_job_type['it'].append(job)
        elif isolation_group:
            data_job_type['repeated'].append(job)
        else:
            pass

    return data


def output_csv(args, summary):
    re_job_type_name = re.compile(r'test-([^/]+)/([^-]+)-(.*)')
    line = "revision,job_type_name,platform,buildtype,test,bugs,"

    for section_name in ("repeated", "id", "it"):
        for property_name in ("run_time", ):
            line += "%s.%s," % (section_name, property_name)
        if section_name != "original":
            if args.include_failures:
                line += "%s.failure_reproduced," % section_name
            if args.include_tests:
                line += "%s.test_reproduced," % section_name
    line = line[0:-1]
    print(line)

    for job_type_name in summary:
        if job_type_name == "revision":
            continue

        match = re_job_type_name.match(job_type_name)
        if not match:
            raise Exception('job_type_name %s does not match pattern' % job_type_name)
        (platform, buildtype, test) = match.groups()
        line = "%s,%s,%s,%s,%s," % (summary['revision'], job_type_name, platform, buildtype, test)
        job_type_summary = summary[job_type_name]
        job_bug_map = summary[job_type_name]['original']['job_bug_map']
        bugs = ' '.join(sorted(set([ str(job_bug['bug_id']) for job_bug in job_bug_map ])))
        line += "%s," % bugs

        for section_name in ("repeated", "id", "it"):
            job_type_section = job_type_summary[section_name]
            for property_name in ("run_time", ):
                line += "%s," % job_type_section[property_name]
            if section_name != "original":
                if args.include_failures:
                    line += "%s," % job_type_section["failure_reproduced"]
                if args.include_tests:
                    line += "%s," % job_type_section["test_reproduced"]
        line = line[0:-1]
        print(line)


def main():
    """main"""

    parent_parsers = [log_level_args.get_parser(), treeherder_urls_args.get_parser()]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""
Reads json produced by get_pushes_jobs_json.py either from stdin
or from a file and produces a summary of runtimes and test failures, writing
results as either csv text or json to stdout. By default, output is written
as formatted json.

%s

""" % '\n\n'.join(additional_descriptions),
        formatter_class=ArgumentFormatter,
        epilog="""
%s

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.

""" % '\n\n'.join(additional_epilogs),
        parents=parent_parsers,
        fromfile_prefix_chars='@'
    )

    parser.add_argument(
        "--file",
        dest="file",
        default=None,
        help="Load the file produced previously by get_pushes_jobs_json. "
        "Leave empty or use - to specify stdin.")

    parser.add_argument(
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.add_argument(
        "--csv",
        action='store_true',
        default=False,
        help="Output in csv format. Does not include individual failures or tests.")

    parser.add_argument(
        "--include-failures",
        action='store_true',
        default=False,
        help="Include individual failures in output.")

    parser.add_argument(
        "--include-tests",
        action='store_true',
        default=False,
        help="Include individual tests in output.")

    parser.set_defaults(func=summarize_isolation_pushes_jobs_json)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    get_repositories(args)

    summary = args.func(args)

    if args.raw:
        print(summary)
    elif args.csv:
        output_csv(args, summary)
    else:
        print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
