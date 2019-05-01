#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
docstring
"""

#params = {
#    'push_startdate': utils.date_to_timestamp(utils.CCYY_MM_DD_to_date(args.start_date)),
#    'push_enddate': utils.date_to_timestamp(utils.CCYY_MM_DD_to_date(args.end_date))
#}

import argparse
import json
import logging

import thclient

import common_args
import utils


def query_tests(args):
    """
    query tests
    """
    logger = logging.getLogger()
    logger.debug("get_tests %s", args)

    push_params = utils.get_treeherder_push_params(args)

    client = thclient.client.TreeherderClient(server_url=args.treeherder)
    pushes = client.get_pushes(args.repo, **push_params)
    for push in pushes:
        logger.debug("push\n%s", json.dumps(push, indent=2, sort_keys=True))
        test_data = utils.query_tests(args.repo, revision=push['revision'],
                                      include_passing_tests=args.include_passing_tests)
        for test in test_data:
            logger.debug("test\n%s", json.dumps(test, indent=2, sort_keys=True))

def main():
    log_level_parser = common_args.log_level.get_parser()
    push_selection_parser = common_args.push_selection.get_parser()
    urls_parser = common_args.urls.get_parser()

    parser = argparse.ArgumentParser(
        description="""ActiveData query tests.""",
        formatter_class=common_args.ArgumentFormatter,
        epilog="""You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.""",
        parents=[log_level_parser, urls_parser, push_selection_parser],
        fromfile_prefix_chars='@'
        )

    parser.add_argument(
        "--include-passing-tests",
        dest="include_passing_tests",
        action='store_true',
        default=False,
        help="Query tests against ActiveData.")

    parser.set_defaults(func=query_tests)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    args.func(args)


main()
