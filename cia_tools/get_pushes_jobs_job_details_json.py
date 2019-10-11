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
import os
import sys

import cache

from common_args import (ArgumentFormatter, jobs_args, log_level_args, pushes_args,
                         treeherder_urls_args)
from treeherder import get_pushes_jobs_job_details_json, init_treeherder


def main():
    """main"""

    parent_parsers = [log_level_args.get_parser(),
                      pushes_args.get_parser(),
                      jobs_args.get_parser(),
                      treeherder_urls_args.get_parser()]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""
Downloads pushes, jobs and job details data from Treeherder, writing results as
nested json to stdout.

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
        '--cache',
        default='~/cia_tools_cache/',
        help='Directory used to store cached objects retrieved from Bugzilla '
        'and Treeherder.')

    parser.add_argument(
        '--update-cache',
        default=False,
        action='store_true',
        help='Recreate cached files with fresh data.')

    parser.add_argument(
        '--dump-cache-stats',
        action='store_true',
        default=False,
        help='Dump cache statistics to stderr.')

    parser.add_argument(
        "--add-resource-usage",
        action='store_true',
        default=False,
        help="Download resource-usage.json job detail and add to job object.")

    parser.add_argument(
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.set_defaults(func=get_pushes_jobs_job_details_json)

    args = parser.parse_args()

    args.cache = os.path.expanduser(args.cache)

    if not os.path.isdir(args.cache):
        os.makedirs(args.cache)
    cache.CACHE_HOME = args.cache

    init_treeherder(args.treeherder_url)

    if args.revision_url:
        (args.repo, _, args.revision) = args.revision_url.split('/')[-3:]

    pushes_args.compile_filters(args)
    jobs_args.compile_filters(args)

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    pushes = args.func(args, args.repo)

    if args.raw:
        json.dump(pushes, sys.stdout)
    else:
        json.dump(pushes, sys.stdout, indent=2)

    if args.dump_cache_stats:
        cache.stats()


if __name__ == '__main__':
    main()
