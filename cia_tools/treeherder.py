#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import logging
import time

import thclient
import requests

import utils


CLIENT = None
REPOSITORIES = None

def get_client(args):
    global CLIENT

    if CLIENT is None:
        CLIENT = thclient.client.TreeherderClient(server_url=args.treeherder)
    return CLIENT

def get_pushes_json(args):
    """get_pushes_json

    Retrieve pushes matching args set via the pushes_parser.
    """
    logger = logging.getLogger()
    logger.debug("treeherder %s", args)

    push_params = utils.get_treeherder_push_params(args)

    client = get_client(args)
    pushes = client.get_pushes(args.repo, **push_params)
    return pushes


def get_pushes_jobs_json(args):
    """get_pushes_jobs_json

    Retrieve nested pushes, jobs matching args set via push_args
    parser and job_args parser.

    """
    pushes = get_pushes_json(args)
    client = get_client(args)
    for push in pushes:
        jobs = client.get_jobs(args.repo, push_id=push['id'], count=None)
        if not args.filters:
            push['jobs'] = jobs
        else:
            push['jobs'] = []
            for job in jobs:
                include = True
                for filter_name in args.filters:
                    include &= args.filters[filter_name].search(job[filter_name]) is not None
                if include:
                    push['jobs'].append(job)
        if args.add_bugzilla_suggestions:
            for job in push['jobs']:
                if job['result'] != 'testfailed':
                    job['bugzilla_suggestions'] = []
                    continue
                bugzilla_suggestions_url = '%s/api/project/%s/jobs/%s/bug_suggestions/' % (
                    (args.treeherder, args.repo, job['id']))
                suggestions = utils.get_remote_json(bugzilla_suggestions_url)
                if args.test_failure_pattern:
                    job['bugzilla_suggestions'] = [
                        suggestion for suggestion in suggestions
                        if args.test_failure_pattern.search(suggestion['search'])]
                else:
                    job['bugzilla_suggestions'] = suggestions
    return pushes


def get_pushes_jobs_job_details_json(args):
    """get_pushes_jobs_job_details_json

    Retrieve nested pushes, jobs, job details matching args set via
    push_args parser and job_args parser.

    """
    logger = logging.getLogger()

    pushes = get_pushes_jobs_json(args)
    client = get_client(args)
    for push in pushes:
        for job in push['jobs']:
            job['job_details'] = []
            # We can get all of the job details from client.get_job_details while
            # get_job_log_url only gives us live_backing.log and live.log.
            # Attempt up to 3 times to work around connection failures.
            for attempt in range(3):
                try:
                    job['job_details'] = client.get_job_details(job_guid=job['job_guid'])
                    if hasattr(args, 'add_resource_usage') and args.add_resource_usage:
                        for job_detail in job['job_details']:
                            if job_detail['value'] == 'resource-usage.json':
                                job['resource_usage'] = utils.get_remote_json(job_detail['url'])
                    break
                except requests.exceptions.ConnectionError:
                    logger.exception('get_job_details attempt %s', attempt)
                    if attempt != 2:
                        time.sleep(30)
            if attempt == 2:
                logger.warning("Unable to get job_details for job_guid %s",
                               job['job_guid'])
                continue

    return pushes


def get_repositories(args):
    global REPOSITORIES

    if REPOSITORIES is None:
        client = get_client(args)
        REPOSITORIES = {}
        repositories = client.get_repositories()
        for repository in repositories:
            REPOSITORIES[repository['id']] = repository


def get_repository_by_id(id):
    return REPOSITORIES[id]
