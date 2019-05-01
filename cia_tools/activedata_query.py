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

import common_args
import utils


class ArgumentFormatter(argparse.ArgumentDefaultsHelpFormatter,
                        argparse.RawTextHelpFormatter):
    """
    myformatter docstring
    """
    def __init__(self, prog, **kwargs):
        super(ArgumentFormatter, self).__init__(prog, **kwargs)


def query(args):
    """
    raw json queries
    """
    logger = logging.getLogger()
    logger.debug("query %s", args)

    with open(args.file) as json_file:
        query_json = json.loads(json_file.read())
    activedata_json = utils.query_active_data(query_json, limit=10000)
    print(json.dumps(activedata_json, indent=2, sort_keys=True))


def main():
    log_level_parser = common_args.log_level.get_parser()
    parser = argparse.ArgumentParser(
        description="""Perform queries against ActiveData.
""",
        formatter_class=common_args.ArgumentFormatter,
        epilog="""You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.""",
        parents=[log_level_parser],
        fromfile_prefix_chars='@'
    )

    parser.add_argument("--file",
                        help="File containing ActiveData query as json..")

    parser.set_defaults(func=query)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    args.func(args)


main()
