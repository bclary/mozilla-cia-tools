#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import json
import logging
import time

import thclient
import requests

import cache
import utils


CLIENT = None
REPOSITORIES = None
URL = None

logger = logging.getLogger()


def init_treeherder(treeherder_url):
    global CLIENT, URL, REPOSITORIES

    if URL is None:
        URL = treeherder_url

    if CLIENT is None:
        CLIENT = thclient.client.TreeherderClient(server_url=URL)

    if REPOSITORIES is None:
        REPOSITORIES = {}
        repositories = CLIENT.get_repositories()
        for repository in repositories:
            REPOSITORIES[repository['id']] = repository


def get_repository_by_id(id):
    return REPOSITORIES[id]


def get_treeherder_push_params(args):
    """
    get_treeherder_push_params
    """
    params = {}
    if args.date_range:
        params = dict(zip(('startdate', 'enddate'), args.date_range.split()))
    elif args.revision:
        params = {'revision': args.revision}
    elif args.revision_range:
        (fromchange, tochange) = args.revision_range.split('-')
        params = {'fromchange': fromchange, 'tochange': tochange}
    elif args.commit_revision:
        params = {'commit_revision': args.commit_revision}
    if args.author:
        params['author'] = args.author
    # limit the response if no arguments given.
    if not params:
        params['count'] = 1
    else:
        params['count'] = None
    return params


def get_pushes_json(args, repo, update_cache=False):
    """get_pushes_json

    Retrieve pushes matching args set via the pushes_parser.
    """
    cache_attributes = ['treeherder', repo, 'push']

    push_params = get_treeherder_push_params(args)

    all_pushes = []
    # CLIENT.MAX_COUNT is 2000 but for pushes, the maximum is 1000.
    # We need to fudge this.
    max_count = CLIENT.MAX_COUNT
    CLIENT.MAX_COUNT = 1000
    while True:
        try:
            all_pushes = CLIENT.get_pushes(repo, **push_params)
            break
        except requests.HTTPError as e:
            if '503 Server Error' not in str(e):
                raise
            logger.exception('get_pushes_json: retrying in 30 seconds.')
        except requests.ConnectionError:
            logger.exception("get_pushes_json: retrying in 30 seconds")
        time.sleep(30)
    CLIENT.MAX_COUNT = max_count
    for push in all_pushes:
        cache.save(cache_attributes, push['id'], json.dumps(push, indent=2))

    if not args.push_filters or not 'comments' in args.push_filters:
        pushes = all_pushes
    else:
        pushes = []
        for push in all_pushes:
            include = True
            for filter_name in args.push_filters:
                for revision in push['revisions']:
                    include &= args.push_filters[filter_name].search(revision[filter_name]) is not None
            if include:
                pushes.append(push)
    return pushes


def get_push_json(args, repo, push_id, update_cache=False):
    """get_pushes_json

    Retrieve push by push_id.
    """
    cache_attributes = ['treeherder', repo, 'push']

    push_params = get_treeherder_push_params(args)
    push_params['id'] = push_id

    push = None
    if not update_cache:
        push_data = cache.load(cache_attributes, push_params['id'])
        if push_data:
            push = json.loads(push_data)
            return push
    while True:
        try:
            pushes = CLIENT.get_pushes(repo, **push_params)
            break
        except requests.HTTPError as e:
            if '503 Server Error' not in str(e):
                raise
            logger.exception('get_push_json: retrying in 30 seconds.')
        except requests.ConnectionError:
            logger.exception("get_push_json: retrying in 30 seconds")
        time.sleep(30)
    if pushes:
        return pushes[0]
    return None


def get_pushes_jobs_json(args, repo, update_cache=False):
    """get_pushes_jobs_json

    Retrieve nested pushes, jobs matching args set via push_args
    parser and job_args parser.

    """
    cache_attributes_push_jobs = ['treeherder', repo, 'push_jobs']

    pushes = get_pushes_json(args, repo, update_cache=update_cache)

    for push in pushes:
        push_jobs_data = cache.load(cache_attributes_push_jobs, push['id'])
        if push_jobs_data and not update_cache:
            jobs = json.loads(push_jobs_data)
        else:
            while True:
                try:
                    jobs = CLIENT.get_jobs(repo, push_id=push['id'], count=None)
                    break
                except requests.HTTPError as e:
                    if '503 Server Error' not in str(e):
                        raise
                    logger.exception('get_pushes_jobs_json: retrying in 30 seconds.')
                except requests.ConnectionError:
                    logger.exception("get_pushes_jobs_json: retrying in 30 seconds")
                time.sleep(30)
            cache.save(cache_attributes_push_jobs, push['id'], json.dumps(jobs, indent=2))

        if not args.job_filters:
            push['jobs'] = jobs
        else:
            push['jobs'] = []
            for job in jobs:
                include = True
                for filter_name in args.job_filters:
                    include &= args.job_filters[filter_name].search(job[filter_name]) is not None
                if include:
                    push['jobs'].append(job)
        if args.add_bugzilla_suggestions:
            for job in push['jobs']:
                if job['result'] != 'testfailed':
                    job['bugzilla_suggestions'] = []
                    continue
                job['bugzilla_suggestions'] = get_job_bugzilla_suggestions_json(args, repo, job['id'], update_cache=update_cache)
    return pushes


def get_pushes_jobs_job_details_json(args, repo, update_cache=False):
    """get_pushes_jobs_job_details_json

    Retrieve nested pushes, jobs, job details matching args set via
    push_args parser and job_args parser.

    """
    cache_attributes = ['treeherder', repo, 'job_details']

    pushes = get_pushes_jobs_json(args, repo, update_cache=update_cache)

    for push in pushes:
        for job in push['jobs']:
            # job['job_guid'] contains a slash followed by the run number.
            # Convert this into a value which can be used a file name
            # by replacing / with _.
            job_guid_path = job['job_guid'].replace('/', '_')
            job_details_data = cache.load(cache_attributes, job_guid_path)
            if job_details_data and not update_cache:
                job['job_details'] = json.loads(job_details_data)
            else:
                job['job_details'] = []
                # We can get all of the job details from CLIENT.get_job_details while
                # get_job_log_url only gives us live_backing.log and live.log.
                # Attempt up to 3 times to work around connection failures.
                for attempt in range(3):
                    try:
                        job['job_details'] = CLIENT.get_job_details(job_guid=job['job_guid'])
                        break
                    except requests.HTTPError as e:
                        if '503 Server Error' not in str(e):
                            raise
                        logger.exception('get_job_details attempt %s', attempt)
                    except requests.ConnectionError:
                        logger.exception('get_job_details attempt %s', attempt)
                    if attempt != 2:
                        time.sleep(30)
                if attempt == 2:
                    logger.warning("Unable to get job_details for job_guid %s",
                                   job['job_guid'])
                    continue
                cache.save(cache_attributes, job_guid_path, json.dumps(job['job_details'], indent=2))

            if hasattr(args, 'add_resource_usage') and args.add_resource_usage:
                for attempt in range(3):
                    try:
                        for job_detail in job['job_details']:
                            if job_detail['value'] == 'resource-usage.json':
                                resource_usage_name = job_guid_path + '-' + job_detail['value']
                                job_detail_resource_usage_data = cache.load(cache_attributes, resource_usage_name)
                                if job_detail_resource_usage_data and not update_cache:
                                    job['resource_usage'] = json.loads(job_detail_resource_usage_data)
                                    job_detail_resource_usage_data = None
                                else:
                                    job['resource_usage'] = utils.get_remote_json(job_detail['url'])
                                    cache.save(cache_attributes, resource_usage_name, json.dumps(job['resource_usage'], indent=2))
                                break
                        break
                    except requests.HTTPError as e:
                        if '503 Server Error' not in str(e):
                            raise
                        logger.exception('get_job_details resource %s attempt %s', attempt)
                    except requests.ConnectionError:
                        logger.exception('get_job_details resource %s attempt %s', attempt)
                    if attempt != 2:
                        time.sleep(30)
                if attempt == 2:
                    logger.warning("Unable to get job_details for job_guid %s",
                                   job['job_guid'])
                    continue
    return pushes


def get_job_by_repo_job_id_json(args, repo, job_id, update_cache=False):
    """get_job_by_repo_job_id_json

    Retrieve job given args, repo and job_id

    """
    cache_attributes = ['treeherder', repo, 'jobs']

    while True:
        try:
            job_data = cache.load(cache_attributes, job_id)
            if job_data and not update_cache:
                jobs = [json.loads(job_data)]
            else:
                jobs = CLIENT.get_jobs(repo, id=job_id)
                for job in jobs:
                    cache.save(cache_attributes, job['id'], json.dumps(job, indent=2))
            break
        except requests.HTTPError as e:
            if '503 Server Error' not in str(e):
                raise
            logger.exception('get_job_by_repo_job_id_json: retrying in 30 seconds.')
        except requests.ConnectionError:
            logger.exception("get_job_by_repo_job_id_json: retrying in 30 seconds")
        time.sleep(30)

    return jobs[0]


def get_bug_job_map_json(args, repo, job_id, update_cache=False):
    """get_bug_job_map_json

    Retrieve bug_job_map given args, repo and job_id

    """
    cache_attributes = ['treeherder', repo, 'bug-job-map']

    bug_job_map_url = '%s/api/project/%s/bug-job-map/?job_id=%s' % (
        (URL, repo, job_id))

    bug_job_map_data = cache.load(cache_attributes, job_id)
    if bug_job_map_data and not update_cache:
        bug_job_map = json.loads(bug_job_map_data)
        bug_job_map_data = None
    else:
        bug_job_map = utils.get_remote_json(bug_job_map_url)
        cache.save(cache_attributes, job_id, json.dumps(bug_job_map, indent=2))

    return bug_job_map


def get_job_bugzilla_suggestions_json(args, repo, job_id, include_related_bugs=False, update_cache=False):
    """get_job_bugzilla_suggestions_json

    Retrieve job_bugzilla_suggestions given args, and job_id

    """
    cache_attributes = ['treeherder', repo, 'bugzilla_suggestions']

    suggestions_data = cache.load(cache_attributes, job_id)
    if suggestions_data and not update_cache:
        suggestions = json.loads(suggestions_data)
    else:
        bugzilla_suggestions_url = '%s/api/project/%s/jobs/%s/bug_suggestions/' % (
            (URL, repo, job_id))

        suggestions = utils.get_remote_json(bugzilla_suggestions_url)
        cache.save(cache_attributes, job_id, json.dumps(suggestions, indent=2))

    if args.test_failure_pattern:
        bugzilla_suggestions = [
            suggestion for suggestion in suggestions
            if args.test_failure_pattern.search(suggestion['search'])]
    else:
        bugzilla_suggestions = suggestions

    if not include_related_bugs:
        for bug_data in bugzilla_suggestions:
            del bug_data['bugs']

    return bugzilla_suggestions


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

    if type(start_date) == datetime.datetime:
        start_date = start_date.strftime('%Y-%m-%d')
    if type(end_date) == datetime.datetime:
        end_date = end_date.strftime('%Y-%m-%d')

    failure_count_url = '%s/api/failurecount/?startday=%s&endday=%s&tree=%s&bug=%s' % (
        (URL, start_date, end_date, repo, bug_id))

    failure_count_json = utils.get_remote_json(failure_count_url)

    return failure_count_json
