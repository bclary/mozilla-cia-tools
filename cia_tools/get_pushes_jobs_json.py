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

from common_args import (ArgumentFormatter, jobs_args, log_level_args, pushes_args,
                         treeherder_urls_args)
from treeherder import get_pushes_jobs_json


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
Downloads pushes and jobs data from Treeherder, writing results as nested json to
stdout.

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
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.set_defaults(func=get_pushes_jobs_json)

    args = parser.parse_args()

    if args.revision_url:
        (args.repo, _, args.revision) = args.revision_url.split('/')[-3:]


    jobs_args.compile_filters(args)

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    pushes = args.func(args)

    if args.raw:
        print(pushes)
    else:
        print(json.dumps(pushes, indent=2))

if __name__ == '__main__':
    main()
