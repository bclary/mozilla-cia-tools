#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
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
    # client.MAX_COUNT is 2000 but for pushes, the maximum is 1000.
    # We need to fudge this.
    max_count = client.MAX_COUNT
    client.MAX_COUNT = 1000
    pushes = client.get_pushes(args.repo, **push_params)
    client.MAX_COUNT = max_count
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


def get_job_by_repo_job_id_json(args, repo, job_id):
    """get_job_by_repo_job_id_json

    Retrieve job given args, repo and job_id

    """
    client = get_client(args)
    jobs = client.get_jobs(repo, id=job_id)

    return jobs[0]


def get_bug_job_map_json(args, repo, job_id):
    """get_job_by_repo_job_id_json

    Retrieve job given args, repo and job_id

    """
    logger = logging.getLogger()
    bug_job_map_url = '%s/api/project/%s/bug-job-map/?job_id=%s' % (
        (args.treeherder, repo, job_id))

    # Attempt up to 3 times to work around connection failures.
    for attempt in range(3):
        try:
            bug_job_map = utils.get_remote_json(bug_job_map_url)
            break
        except requests.exceptions.ConnectionError:
            logger.exception('get_bug_job_map_json attempt %s', attempt)
            if attempt != 2:
                time.sleep(30)
    if attempt == 2:
        logger.warning("Unable to get job_bug_map %s", bug_job_map_url)
        bug_job_map = None

    return bug_job_map


def get_failure_count_json(args, repo, bug_id, start_date, end_date):
    """get_failure_count_json

    Retrieve list of objects by repo/project, bug and date range.
    [
        {
            "date": "2019-07-10",
            "test_runs": 154,
            "failure_count": 0
        },
    ]

    """
    logger = logging.getLogger()

    if type(start_date) == datetime.datetime:
        start_date = start_date.strftime('%Y-%m-%d')
    if type(end_date) == datetime.datetime:
        end_date = end_date.strftime('%Y-%m-%d')

    failure_count_url = '%s/api/failurecount/?startday=%s&endday=%s&tree=%s&bug=%s' % (
        (args.treeherder, start_date, end_date, repo, bug_id))

    # Attempt up to 3 times to work around connection failures.
    for attempt in range(3):
        try:
            failure_count_json = utils.get_remote_json(failure_count_url)
            break
        except requests.exceptions.ConnectionError:
            logger.exception('get_failure_count_json attempt %s', attempt)
            if attempt != 2:
                time.sleep(30)
    if attempt == 2:
        logger.warning("Unable to get failure_count %s", failure_count_url)
        failure_count_json = None

    return failure_count_json


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
