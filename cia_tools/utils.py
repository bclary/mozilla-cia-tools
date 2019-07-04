# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
# https://treeherder.mozilla.org/docs
"""

import copy
import datetime
import json
import logging
import random
import time

from urllib.parse import urlparse

import requests

USER_AGENT = "mozilla-cia-tools"

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
    return params


def get_remote_text(url):
    """Return the string containing the contents of a url if the
    request is successful, otherwise return None. Works with remote
    and local files.

    :param url: url of content to be retrieved.
    """
    logger = logging.getLogger()

    try:
        parse_result = urlparse(url)
        if not parse_result.scheme or parse_result.scheme.startswith('file'):
            local_file = open(parse_result.path)
            with local_file:
                return local_file.read()

        while True:
            try:
                req = requests.get(url, headers={'user-agent': USER_AGENT})
                if req.ok:
                    return req.text
                if req.status_code != 503:
                    logger.warning("Unable to open url %s : %s",
                                   url, req.reason)
                    return None
                # Server is too busy.
                # See https://bugzilla.mozilla.org/show_bug.cgi?id=1146983#c10
                logger.warning("HTTP 503 Server Too Busy: url %s", url)
            except requests.exceptions.ConnectionError as err:
                logger.warning("ConnectionError: %s. Will retry...", err)

            # Wait and try again.
            time.sleep(60 + random.randrange(0, 30, 1))
    except requests.exceptions.RequestException:
        logger.exception('Unable to open %s', url)

    return None


def get_remote_json(url):
    """Return the json representation of the contents of a remote url if
    the HTTP response code is 200, otherwise return None.

    :param url: url of content to be retrieved.
    """
    logger = logging.getLogger()
    content = get_remote_text(url)
    if content:
        content = json.loads(content)
    logger.debug('get_remote_json(%s): %s', url, content)
    return content


# download_file() cloned from autophone's urlretrieve()

def download_file(url, dest, max_attempts=3):
    """Download file from url and save to dest.

    :param: url: string url to file to download.
                 Can be either http, https or file scheme.
    :param dest: string path where to save file.
    :max_attempts: integer number of times to attempt download.
                   Defaults to 3.
    """
    logger = logging.getLogger()
    parse_result = urlparse(url)
    if not parse_result.scheme or parse_result.scheme.startswith('file'):
        local_file = open(parse_result.path)
        with local_file:
            with open(dest, 'wb') as dest_file:
                while True:
                    chunk = local_file.read(10485760)
                    if not chunk:
                        break
                    dest_file.write(chunk)
            return

    for attempt in range(max_attempts):
        try:
            req = requests.get(url, stream=True)
            if not req.ok:
                req.raise_for_status()
            with open(dest, 'wb') as dest_file:
                for chunk in req.iter_content(chunk_size=10485760):
                    dest_file.write(chunk)
            break
        except requests.exceptions.HTTPError as http_error:
            logger.error("download_file(%s, %s) %s", url, dest, http_error)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as err:
            logger.warning("utils.download_file: %s: Attempt %s: %s",
                           url, attempt, err)
            if attempt == max_attempts - 1:
                logger.error("utils.download_file: %s: giving up", url)
                return
            # Wait and try again.
            time.sleep(60 + random.randrange(0, 30, 1))

def date_to_timestamp(dateval):
    """
    docstring
    """
    return time.mktime(dateval.timetuple())


def CCYY_MM_DD_to_date(strval):
    """
    docstring
    """
    return datetime.datetime.strptime(strval, '%Y-%m-%d')


def merge_dicts(left, right):
    """Return a dict by merging left and left where left and right are objects with two
    level keys containing numbers.

    dict schema  { 'key': {'sub_key': integer}}

    """
    logger = logging.getLogger()
    logger.debug("merge_dicts: left=%s, right=%s", left, right)
    result = copy.deepcopy(left)
    for key in right.keys():
        if key not in result:
            result[key] = copy.deepcopy(right[key])
        else:
            for sub_key in right[key].keys():
                if sub_key not in result[key]:
                    result[key][sub_key] = 0
                result[key][sub_key] += right[key][sub_key]
    logger.debug("merge_dicts: result=%s", result)
    return result


def query_active_data(args, query_json, limit=10):
    """
    docstring
    """
    logger = logging.getLogger()
    if "limit" not in query_json:
        query_json["limit"] = limit

    logger.debug("query_active_data\n%s",
                 json.dumps(query_json, indent=2, sort_keys=True))

    query = json.dumps(query_json)
    while True:
        try:
            req = requests.post(args.activedata, data=query, stream=True,
                                headers={'user-agent': USER_AGENT})
            if req.ok:
                try:
                    result_json = req.json()
                    if len(result_json["data"]) == limit:
                        logger.warning("query_active_data(%s,%s) returned limit.",
                                       query_json, limit)
                    return result_json
                except ValueError:
                    logger.error('ActiveData reponse not json %s', req.text)
                    return None
            elif req.status_code == 503:
                # Server is too busy.
                # See https://bugzilla.mozilla.org/show_bug.cgi?id=1146983#c10
                logger.warning("HTTP 503 Server Too Busy: url %s", args.activedata)
            else:
                logger.warning("Unable to open url %s : %s",
                               args.activedata, req.reason)
                return None
        except requests.exceptions.ConnectionError as err:
            logger.warning("ConnectionError: %s. Will retry...", err)
        except requests.exceptions.RequestException:
            logger.exception('Unable to open %s', args.activedata)
            break

        # Wait and try again.
        time.sleep(60 + random.randrange(0, 30, 1))

    return None


def query_tests(args, revision=""):
    """Retrieve tests from ActiveData for the specified
    branch and revision. If all is True, return
    all tests otherwise only return test failures.
    """
    logger = logging.getLogger()
    query_json = {
        "from": "unittest",
        "where": {
            "and":[
                {
                    "eq": {
                        "build.branch": args.repo,
                    }
                }
            ]
        },
        "format": "list",
    }
    if len(revision) == 12:
        query_json["where"]["and"].append({"eq":{"build.revision12":revision}})
    elif len(revision) == 40:
        query_json["where"]["and"].append({"eq":{"build.revision":revision}})
    else:
        raise ValueError("query_test_failures: revision must be 12 or 40 characters.")

    if not args.include_passing_tests:
        query_json["where"]["and"].append({"eq":{"result.ok":False}})

    j = query_active_data(args, query_json, limit=10000)
    if not j:
        logger.warning('query_tests(%s, %s, include_passing_tests=%s) returned None',
                       args.repo, revision, args.include_passing_tests)
        return None

    tests = []

    for active_data_test in j['data']:
        test = {}
        test_errors = []
        tests.append(test)

        logger.debug("active_data_test\n%s",
                     json.dumps(active_data_test, indent=2, sort_keys=True))

        task = active_data_test["task"]

        test["task_group_id"] = task["group"]["id"]
        test["task_parent_task_group_id"] = task["parent"]["id"]
        if "maxRunTime" in task:
            test["task_maxRunTime"] = task["maxRunTime"]
        else:
            test_errors.append("Does not contain task.maxRunTime")
            test["task_maxRunTime"] = None
        test["task_worker"] = dict(task["worker"])
        test["task_state"] = task["state"]
        test["task_scheduler"] = task["scheduler"]["id"]
        test["task_provisioner"] = task["provisioner"]["id"]
        test["task_dependencies"] = task["dependencies"]
        if not isinstance(test["task_dependencies"], list):
            test["task_dependencies"] = [test["task_dependencies"]]
        test["task_id"] = task["id"]

        test_run = active_data_test["run"]
        test["test_run_duration"] = test_run["stats"]["duration"]
        test["test_run_name"] = test_run["name"]
        test["test_run_chunk"] = test_run["chunk"]
        test["test_run_machine"] = dict(test_run["machine"])
        test["test_run_key"] = test_run["key"]
        if "type" in test_run:
            test["test_run_type"] = test_run["type"]
        else:
            test_errors.append("Does not contain run.type")
            test["test_run_type"] = None
        if not isinstance(test["test_run_type"], list):
            test["test_run_type"] = [test["test_run_type"]]
        test["test_run_suite_fullname"] = test_run["suite"]["fullname"]
        test["test_run_suite_name"] = test_run["suite"]["name"]
        if test["test_run_suite_fullname"] != test["test_run_suite_name"]:
            logger.info("test_run_suite_fullname != test_run_suite_name")

        repo = active_data_test["repo"]
        test["repo_url"] = repo["branch"]["url"]
        test["repo_push_date"] = repo["push"]["date"]
        test["repo_changeset_date"] = repo["changeset"]["date"]

        build = active_data_test["build"]
        test["build_platform"] = build["platform"]
        test["build_type"] = build["type"]
        test["build_branch"] = build["branch"]
        test["build_revision"] = build["revision"]

        treeherder = active_data_test["treeherder"]
        test["treeherder_group_symbol"] = treeherder.get("groupSymbol", None)
        test["treeherder_group_name"] = treeherder.get("groupName", None)
        test["treeherder_machine_platform"] = treeherder["machine"]["platform"]
        test["treeherder_symbol"] = treeherder["symbol"]

        etl = active_data_test["etl"]
        test["etl_name"] = etl["source"]["name"]
        test["etl_log"] = etl["source"]["url"]

        if "result" in active_data_test:
            result = active_data_test["result"]
            if result.get("status", None) != result.get("result", None):
                test_errors.append("result.status and result.result differ")
            test["result_status"] = result.get("status", None)
            test["result_ok"] = result["ok"]
            test["result_expected"] = result.get("expected", "missing")
            test["result_test"] = result["test"]
            test["result_result"] = result.get("result", None)

            subtests = result.get("subtests", None)
            if subtests is None and test["result_status"] != "SKIP":
                #if test["result_status"] != "OK" or not test["result_ok"]:
                if not test["result_ok"]:
                    test_errors.append("Does not include result.subtests")
                test["result_subtests"] = []
            elif isinstance(subtests, dict):
                test["result_subtests"] = [dict(subtests)]
            elif isinstance(subtests, list):
                test["result_subtests"] = copy.deepcopy(subtests)
        else:
            test_errors.append("Does not include result")
        if test_errors:
            logger.warning("ActiveDataTest contains errors: %s\n%s",
                           ", ".join(test_errors),
                           json.dumps(active_data_test, indent=2, sort_keys=True))

    return tests
