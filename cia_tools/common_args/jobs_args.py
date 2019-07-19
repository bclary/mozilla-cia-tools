"""
standardized argparse parser for job_args
see https://github.com/mozilla/treeherder/blob/master/treeherder/webapp/api/jobs.py

The arguments returned by the parser be passed to compile_filters in
order to compile the patterns and prepare them for use.

parser = get_parser()
args = parser.parse_args()
compile_filters(args)
"""

import argparse
import re


def get_parser():

    parser = argparse.ArgumentParser(
        description="""Job Related Arguments

Job related pattern objects are used to select the jobs which will be
returned. All specified patterns must match to return a job.
""",
        add_help=False)

    parser.add_argument(
        "--add-bugzilla-suggestions",
        action='store_true',
        default=False,
        help="Add bugzilla suggestions to job objects.")

    parser.add_argument(
        "--test-failure-pattern",
        default=None,
        help="Include failures from bugzilla suggestions matching this regular expression.")

    parser.add_argument(
        "--build-platform",
        default=None,
        help="Match job build platform regular expression.")

    parser.add_argument(
        "--job-group-name",
        default=None,
        help="Match job group name regular expression.")

    parser.add_argument(
        "--job-group-symbol",
        default=None,
        help="Match job group symbol regular expression")

    parser.add_argument(
        "--job-type-name",
        default=None,
        help="Match job type name regular expression.")

    parser.add_argument(
        "--job-type-symbol",
        default=None,
        help="Match job type symbol regular expression.")

    parser.add_argument(
        "--machine-name",
        default=None,
        help="Match job machine name regular expression.")

    parser.add_argument(
        "--platform",
        default=None,
        help="Match job platform regular expression.")

    parser.add_argument(
        "--platform-option",
        default=None,
        help="Match job platform option regular expression: opt, debug, pgo,...")

    parser.add_argument(
        "--result",
        default=None,
        help="Match job result regular expression: unknown, success, testfailed, ....")

    parser.add_argument(
        "--state",
        default=None,
        help="Match job state regular expression: pending, running, completed.")

    parser.add_argument(
        "--tier",
        default=None,
        help="Match job tier regular expression.")

    # who same as author handled in push_args

    return parser


def compile_filters(args):
    """compile_filters

    :param: args - argparse.Namespace returned from argparse parse_args.

    Convert job filter regular expression patterns to regular
    expressions and attach to a `filters` dict on the args object.

    """
    filter_names = ("build_platform",
                    "job_group_name",
                    "job_group_symbol",
                    "job_type_name",
                    "job_type_symbol",
                    "machine_name",
                    "platform",
                    "platform_option",
                    "result",
                    "state",
                    "tier",)
    args.filters = {}
    for filter_name in filter_names:
        filter_value = getattr(args, filter_name)
        if filter_value:
            args.filters[filter_name] = re.compile(filter_value)

    if args.test_failure_pattern:
        args.test_failure_pattern = re.compile(args.test_failure_pattern)

