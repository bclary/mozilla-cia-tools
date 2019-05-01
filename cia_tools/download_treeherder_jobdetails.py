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
import re
import time

from urllib.parse import urlparse

import thclient
import requests

import common_args
import utils


def download_treeherder_job_details(args):
    """
    job_details subcommand
    """
    logger = logging.getLogger()
    logger.debug("treeherder %s", args)

    push_params = utils.get_treeherder_push_params(args)

    if args.download_job_details:
        try:
            re_download_job_details = re.compile(args.download_job_details)
        except re.error:
            logger.error("--download-job-details must be a valid regular "
                         "expression not a file glob.")
            return
    else:
        re_download_job_details = None

    client = thclient.client.TreeherderClient(server_url=args.treeherder)
    pushes = client.get_pushes(args.repo, **push_params)
    logger.debug('treeherder pushes\n:%s', pushes)
    for push in pushes:
        logger.debug("treeherder push:\n%s", json.dumps(push, indent=2, sort_keys=True))

        jobs = client.get_jobs(args.repo, push_id=push['id'], count=None)
        logger.debug("found %s jobs for push %s", len(jobs), push['id'])
        for job in jobs:
            logger.debug("job:\n%s", json.dumps(job, indent=2, sort_keys=True))
            # get some job type meta data to allow us to encode the job type name and symbol
            # into the job detail file name.
            job_type_name = job['job_type_name']
            job_type_symbol = job['job_type_symbol']

            # We can get all of the job details from get_job_details while
            # get_job_log_url only gives us live_backing.log and live.log.
            for attempt in range(3):
                try:
                    job_details = client.get_job_details(job_guid=job['job_guid'])
                    logger.debug("job_details:\n%s",
                                 json.dumps(job_details, indent=2, sort_keys=True))
                    break
                except requests.exceptions.ConnectionError:
                    logger.exception('get_job_details attempt %s', attempt)
                    if attempt != 2:
                        time.sleep(30)
            if attempt == 2:
                logger.warning("Unable to get job_details for job_guid %s",
                               job['job_guid'])
                continue

            for job_detail in job_details:
                logger.debug("treeherder job_detail:\n%s",
                             json.dumps(job_detail, indent=2, sort_keys=True))
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

                        logger.debug("job_type_name %s, platform %s, buildtype %s, "
                                     "job_name %s, job_type_symbol %s, file_name %s",
                                     job_type_name, platform, buildtype,
                                     job_name, job_type_symbol, file_name)
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
                        logger.debug("downloading %s to %s", job_detail_url, destination)
                        if not os.path.isdir(destination_dir):
                            if os.path.exists(destination_dir):
                                logger.error("destination %s but is not a directory",
                                             destination_dir)
                            else:
                                os.makedirs(destination_dir)
                        if not os.path.exists(destination):
                            utils.download_file(job_detail_url, destination)
                        else:
                            logger.debug('%s already downloaded to %s', job_detail_url, destination)


def main():
    """main"""

    log_level_parser = common_args.log_level.get_parser()
    push_selection_parser = common_args.push_selection.get_parser()

    parser = argparse.ArgumentParser(
        description="""Download Test Log files from Treeherder/Taskcluster.

blah blah metadata encoded file names
examples blah blah

""",
        formatter_class=common_args.ArgumentFormatter,
        epilog="""

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.

""",
        parents=[log_level_parser, push_selection_parser],
        fromfile_prefix_chars='@'
    )

    parser.add_argument(
        "--treeherder",
        default='https://treeherder.mozilla.org',
        help="Treeherder url.")

    parser.add_argument(
        "--download-job-details",
        dest="download_job_details",
        default=None,
        help="""Regular expression matching Job details url basenames to be
        downloaded.  Example:live_backing.log|logcat.*.log. Default
        None.""")

    parser.add_argument(
        "--output",
        dest="output",
        default="output",
        help="Directory where to save downloaded job details.")

    parser.set_defaults(func=download_treeherder_job_details)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    args.func(args)

if __name__ == '__main__':
    main()
