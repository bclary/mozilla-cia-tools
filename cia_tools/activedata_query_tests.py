#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging
import sys

import utils

from common_args import (ArgumentFormatter, log_level_args, pushes_args,
                         treeherder_urls_args, activedata_urls_args)
from treeherder import get_pushes_json, init_treeherder

def query_tests(args):
    tests = []
    pushes = get_pushes_json(args, args.repo)
    for push in pushes:
        tests.extend(utils.query_tests(args, revision=push['revision']))
    return tests


def main():
    parent_parsers = [log_level_args.get_parser(),
                      pushes_args.get_parser(),
                      treeherder_urls_args.get_parser(),
                      activedata_urls_args.get_parser()]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""ActiveData query tests.

Query ActiveData tests and write the result as json to stdout.

Errors will be written to stderr.

%s
""" % '\n\n'.join(additional_descriptions),
        formatter_class=ArgumentFormatter,
        epilog="""
%s

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
"""  % '\n\n'.join(additional_epilogs),
        parents=parent_parsers,
        fromfile_prefix_chars='@'
        )

    parser.add_argument(
        "--include-passing-tests",
        dest="include_passing_tests",
        action='store_true',
        default=False,
        help="Query tests against ActiveData.")

    parser.add_argument(
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.set_defaults(func=query_tests)

    args = parser.parse_args()

    init_treeherder(args.treeherder_url)

    logging.basicConfig(level=getattr(logging, args.log_level))

    tests = args.func(args)

    if args.raw:
        json.dump(tests, sys.stdout)
    else:
        json.dump(tests, sys.stdout, indent=2)

main()
