#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
module docstring
"""

import argparse
import json
import logging
import re
import sys

from common_args import ArgumentFormatter, log_level_args


re_job_group_symbol = re.compile(r'-I$')
re_job_type_symbol = re.compile(r'-(id|it)$')


def is_isolation_job_group_symbol(job_group_symbol):
    return re_job_group_symbol.search(job_group_symbol)


def isolation_job_type(job_type_symbol):
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

    summary = {}
    data = load_isolation_push_jobs_json(args)

    job_type_names = sorted(data.keys())

    for job_type_name in job_type_names:
        if job_type_name not in summary:
            summary[job_type_name] = job_type_summary = {}
        job_type = data[job_type_name]
        for section_name in ("original", "repeated", "id", "it"):
            if section_name not in job_type_summary:
                job_type_summary[section_name] = job_type_section_summary = {}
                job_type_section_summary['failures'] = {}
            section = job_type[section_name]
            run_time = 0
            number_jobs_testfailed = 0
            number_failures = 0
            for job in section:
                run_time += job['end_timestamp'] - job['start_timestamp']
                number_jobs_testfailed += 1 if job['result'] == 'testfailed' else 0
                number_failures += len(job['bugzilla_suggestions'])
                for bugzilla_suggestion in job['bugzilla_suggestions']:
                    failure = munge_failure(bugzilla_suggestion['search'])
                    if failure not in job_type_section_summary['failures']:
                        job_type_section_summary['failures'][failure] = {
                            'count': 0,
                            'reproduced': {
                                'repeated': 0,
                                'id': 0,
                                'it': 0,
                            }
                        }
                    job_type_section_summary['failures'][failure]['count'] += 1
            job_type_section_summary['run_time'] = run_time
            job_type_section_summary['jobs_failed'] = number_jobs_testfailed
            job_type_section_summary['jobs_total'] = len(section)
            job_type_section_summary['tests_failed'] = number_failures
            job_type_section_summary['reproduced'] = {
                'repeated': 0,
                'id': 0,
                'it': 0,
            }
        job_type_original_summary = job_type_summary['original']
        for section_name in ("repeated", "id", "it"):
            job_type_section_summary = job_type_summary[section_name]
            for failure in job_type_section_summary['failures']:
                if failure in job_type_original_summary['failures']:
                    count = job_type_section_summary['failures'][failure]['count']
                    job_type_original_summary['failures'][failure]['reproduced'][section_name] += count
                    job_type_original_summary['reproduced'][section_name] += count
                    job_type_section_summary['failures'][failure]['reproduced'][section_name] += count
                    job_type_section_summary['reproduced'][section_name] += count
    if not args.include_failures:
        # Remove failures lists from sections
        for job_type_name in summary:
            for section_name in summary[job_type_name]:
                summary_section = summary[job_type_name][section_name]
                if 'failures' in summary_section:
                    del summary_section['failures']

    return summary

def load_isolation_push_jobs_json(args):
    """Load job data from the specified file, collecting the jobs which are
    related to test isolation (group symbol suffix -I) and organizing them
    in a dict according to.

    data = {
        "<job-type-name>": {
            "original": [],
            "repeated": [],
            "id": [],
            "it": [],
        },
        ...
    }
    """
    data = {}

    if args.file is None or args.file == '-':
        push = json.loads(sys.stdin.read())[0]
    else:
        with open(args.file) as input:
                push = json.loads(input.read())[0]

    # Find the job_type_names associated with test isolation jobs
    for job in push['jobs']:
        job_type_symbol = job['job_type_symbol']
        isolation_type = isolation_job_type(job_type_symbol)
        if isolation_type:
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
        isolation_type = isolation_job_type(job_type_symbol)
        if isolation_type is None:
            if is_isolation_job_group_symbol(job['job_group_symbol']):
                data_job_type['repeated'].append(job)
            else:
                data_job_type['original'].append(job)
        elif isolation_type == 'id':
            data_job_type['id'].append(job)
        elif isolation_type == 'it':
            data_job_type['it'].append(job)
        else:
            pass # Ignore non test isolation related jobs

    return data


def output_csv(summary):
    line = "job_type_name,"
    for section_name in ("original", "repeated", "id", "it"):
        for property_name in ("run_time", "jobs_failed", "jobs_total", "tests_failed"):
            line += "%s.%s," % (section_name, property_name)
        for reproduced_property_name in ("repeated", "id", "it"):
            line += "%s.reproduced.%s," % (section_name, reproduced_property_name)
    line = line[0:-1]
    print(line)
    for job_type_name in summary:
        line = "%s," % job_type_name
        job_type_summary = summary[job_type_name]
        for section_name in ("original", "repeated", "id", "it"):
            job_type_section = job_type_summary[section_name]
            for property_name in ("run_time", "jobs_failed", "jobs_total", "tests_failed"):
                line += "%s," % job_type_section[property_name]
            for reproduced_property_name in ("repeated", "id", "it"):
                reproduced_property = job_type_section["reproduced"][reproduced_property_name]
                line += "%s," % reproduced_property
        line = line[0:-1]
        print(line)


def main():
    """main"""

    parent_parsers = [log_level_args.get_parser()]

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
        help="Output in csv format. Not compatible with --include-failures.")

    parser.add_argument(
        "--include-failures",
        action='store_true',
        default=False,
        help="Include individual failures in output.")

    parser.set_defaults(func=summarize_isolation_pushes_jobs_json)

    args = parser.parse_args()

    if args.csv and args.include_failures:
        parser.error("Can not specify both --csv and --include-failures.")

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    summary = args.func(args)

    if args.raw:
        print(summary)
    elif args.csv:
        output_csv(summary)
    else:
        print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
