#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
module docstring
"""

import argparse
import logging
import os
import re

from urllib.parse import urlparse

import utils

from common_args import (ArgumentFormatter, jobs_args, log_level_args, pushes_args,
                         treeherder_urls_args)
from treeherder import get_pushes_jobs_job_details_json, init_treeherder


def download_treeherder_job_details(args):
    logger = logging.getLogger()

    try:
        re_download_job_details = re.compile(args.download_job_details)
    except re.error:
        logger.error("--download-job-details must be a valid regular "
                     "expression not a file glob.")
        return

    pushes = get_pushes_jobs_job_details_json(args)
    for push in pushes:
        for job in push['jobs']:
            # get some job type meta data to allow us to encode the job type name and symbol
            # into the job detail file name.
            job_type_name = job['job_type_name']
            job_type_symbol = job['job_type_symbol']

            for job_detail in job['job_details']:
                job_detail_url = job_detail['url']
                if job_detail_url:
                    url_parts = urlparse(job_detail_url)
                    file_name = os.path.basename(url_parts.path)
                    if not re_download_job_details:
                        print(job_detail_url)
                    elif re_download_job_details.match(file_name):
                        (job_guid, job_guid_run) = job['job_guid'].split('/')
                        path_dir = os.path.dirname(url_parts.path)
                        # remove leading /
                        path_dir = re.sub('^/', '', path_dir)
                        # Encode the meta data into the file_name in a
                        # parseable fashion as
                        # platform,buildtype,jobname,jobsymbol,filename
                        if '/' in job_type_name:
                            (platform, buildtype) = job_type_name.split('/')
                            if '-' in buildtype:
                                buildtype_parts = buildtype.split('-')
                                buildtype = buildtype_parts[0]
                                job_name = '-'.join(buildtype_parts[1:])
                            else:
                                job_name = job_type_symbol
                        else:
                            (platform, job_name, buildtype) = (job_type_name, 'na', 'na')

                        platform = re.sub(r'[^\w.-]', ',', re.sub(r'[^a-zA-Z0-9.-]', '_', platform))
                        file_name = "{},{},{},{},{}".format(
                            platform,
                            buildtype,
                            job_name,
                            job_type_symbol,
                            file_name)
                        destination = os.path.join(
                            args.output,
                            push['revision'],
                            job_guid,
                            job_guid_run,
                            path_dir,
                            file_name)
                        destination = os.path.abspath(destination)
                        destination_dir = os.path.dirname(destination)
                        if not os.path.isdir(destination_dir):
                            if os.path.exists(destination_dir):
                                logger.error("destination %s but is not a directory",
                                             destination_dir)
                            else:
                                os.makedirs(destination_dir)
                                if args.alias:
                                    cwd = os.getcwd()
                                    os.chdir(args.output)
                                    if not os.path.islink(args.alias):
                                        os.symlink(push['revision'], args.alias)
                                    os.chdir(cwd)
                        if not os.path.exists(destination):
                            utils.download_file(job_detail_url, destination)
                        else:
                            logger.debug('%s already downloaded to %s', job_detail_url, destination)


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
        description="""Download Job Details files from Treeherder/Taskcluster.

--download-job-details specifies a regular expression which will be matched
against the base file name of the url to the file to select the files to be
downloaded. This is not a shell glob pattern, but a full regular expression.
Files will be saved to the output directory using the path to the job detail
and a file name encoded with meta data as:

output/revision/job_guid/job_guid_run/path/platform,buildtype,job_name,job_type_symbol,filename

if --alias is specified, a soft link will be created from
output/revision to output/alias.

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
        "--download-job-details",
        dest="download_job_details",
        default=None,
        required=True,
        help="""Regular expression matching Job details url basenames to be
        downloaded.  Example:live_backing.log|logcat.*.log. Default
        None.""")

    parser.add_argument(
        "--output",
        dest="output",
        default="output",
        help="Directory where to save downloaded job details.")

    parser.add_argument(
        "--alias",
        dest="alias",
        default=None,
        help="Alias (soft link) to revision subdirectory where the downloaded job details were saved.")

    parser.set_defaults(func=download_treeherder_job_details)

    args = parser.parse_args()

    init_treeherder(args.treeherder_url)

    if args.revision_url:
        (args.repo, _, args.revision) = args.revision_url.split('/')[-3:]

    pushes_args.compile_filters(args)
    jobs_args.compile_filters(args)

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    args.func(args)

if __name__ == '__main__':
    main()
