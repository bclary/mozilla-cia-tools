#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging

import utils

from common_args import ArgumentFormatter, log_level_args, activedata_urls_args

def query(args):
    """
    raw json queries
    """
    logger = logging.getLogger()
    logger.debug("query %s", args)

    with open(args.file) as json_file:
        query_json = json.loads(json_file.read())
    return utils.query_active_data(args, query_json, limit=10000)


def main():
    parent_parsers = [log_level_args.get_parser(),
                      activedata_urls_args.get_parser()]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""Query ActiveData tests and write the result as json to stdout.

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
""" % '\n\n'.join(additional_epilogs),
        parents=parent_parsers,
        fromfile_prefix_chars='@'
    )

    parser.add_argument("--file",
                        required=True,
                        help="File containing ActiveData query as json..")

    parser.add_argument(
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.set_defaults(func=query)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    activedata_json = args.func(args)

    if args.raw:
        print(activedata_json)
    else:
        print(json.dumps(activedata_json, indent=2))


main()
