#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import copy
import datetime
import json
import logging
import os
import re

import cache
import utils

from common_args import (
    ArgumentFormatter,
    jobs_args,
    log_level_args,
    pushes_args,
    treeherder_urls_args,
)

from treeherder import (
    get_bug_job_map_json,
    get_failure_count_json,
    get_job_bugzilla_suggestions_json,
    get_job_by_repo_job_id_json,
    get_push_json,
    get_pushes_jobs_json,
    get_repository_by_id,
    init_treeherder,
)


BUGZILLA_URL = 'https://bugzilla.mozilla.org/rest/'
ORIGINAL_SECTIONS = ('original',)
ISOLATION_SECTIONS = ('repeated', 'id', 'it')
TEST_FAILURE_PATTERN = 'TEST-|PROCESS-CRASH|REFTEST TEST-|Assertion failure:'


def convert_bug_summary_to_pattern(bug_summary):
    parts = munge_failure(bug_summary).split(' | ')
    for i in range(len(parts)):
        parts[i] = re.escape(parts[i])
    pattern = re.sub('<(test|random)>', '[^|]+', ' \\| '.join(parts))
    if r'\ ==\ ' in pattern and 'Assertion failure:' not in pattern:
        parts = pattern.split(r'\ ==\ ')
        parts[0] = '.*' + parts[0]
        parts[1] = '.*' + parts[1]
        pattern = r'\ ==\ '.join(parts)
    return pattern


def get_test_isolation_bugzilla_data(args):
    """Query Bugzilla for bugs marked with [test isolation] in the
    whiteboard.  Return a dictionary keyed by revision url containing
    the bug id and summary.

    """
    cache_attributes = ['test-isolation']

    logger = logging.getLogger()

    bugzilla_data = cache.load(cache_attributes, 'bugzilla.json')
    if bugzilla_data and not args.update_cache:
        return json.loads(bugzilla_data)

    now = datetime.datetime.now()

    data = {}

    re_logview = re.compile(r'https://treeherder.mozilla.org/logviewer.html#\?job_id=([0-9]+)&repo=([a-z-]+)')
    re_pushlog_url = re.compile(r'(https://.*)$\n', re.MULTILINE)

    query = BUGZILLA_URL + 'bug?'
    query_terms = {
        'include_fields': 'id,creation_time',
        'creator': 'intermittent-bug-filer@mozilla.bugs',
        'creation_time': args.bug_creation_time,
        'status_whiteboard': args.whiteboard,
        'limit': 100,
        'offset': 0,
        }
    if args.bugs:
        query_terms['id'] = ','.join([str(id) for id in args.bugs])
    else:
        query_terms['creation_time'] = args.bug_creation_time

    if args.whiteboard != ['test-isolation']:
        # We aren't looking for bugs filed by the sheriff's
        # so delete the requirement that the bug be created
        # by the intermittent-bug-filer.
        del query_terms['creator']

    while True:
        response = utils.get_remote_json(query, params=query_terms)
        if 'error' in response:
            logger.error('Bugzilla({}, {}): {}'.format(query, query_terms, response))
            return

        if len(response['bugs']) == 0:
            break

        # update query terms for next iteration of the loop.
        query_terms['offset'] += query_terms['limit']

        for bug in response['bugs']:
            #https://bugzilla.mozilla.org/rest/bug/1559260/comment

            if args.bugs_after and bug['id'] <= args.bugs_after:
                continue

            if args.bugs and bug['id'] not in args.bugs:
                continue

            query2 = BUGZILLA_URL + 'bug/%s' % bug['id']
            response2 = utils.get_remote_json(query2)
            if 'error' in response2:
                logger.error('Bugzilla({}): {}'.format(query2, response2))
                return

            bug_summary = response2['bugs'][0]['summary']
            munged_bug_summary = munge_failure(bug_summary)
            test = get_test(munged_bug_summary)

            query3 = BUGZILLA_URL + 'bug/%s/comment' % bug['id']
            response3 = utils.get_remote_json(query3)
            if 'error' in response3:
                logger.error('Bugzilla({}): {}'.format(query, response3))
                return

            raw_text = response3['bugs'][str(bug['id'])]['comments'][0]['raw_text']
            match = re_logview.search(raw_text)
            if match:
                job_id = int(match.group(1))
                repo = match.group(2)
                job = get_job_by_repo_job_id_json(args, repo, job_id, update_cache=args.update_cache)
                push_id = job['push_id']
                push = get_push_json(args, repo, push_id, update_cache=args.update_cache)
                repository = get_repository_by_id(push['revisions'][0]['repository_id'])
                revision = push['revisions'][0]['revision']
                revision_url = '%s/rev/%s' % (repository['url'], revision)

                new_args = copy.deepcopy(args)
                new_args.revision_url = revision_url
                (new_args.repo, _, new_args.revision) = new_args.revision_url.split('/')[-3:]
                new_args.add_bugzilla_suggestions = True
                new_args.state = 'completed'
                new_args.job_type_name = '^test-'
                new_args.test_failure_pattern = TEST_FAILURE_PATTERN
                pushes_args.compile_filters(new_args)
                jobs_args.compile_filters(new_args)

                if revision_url not in data:
                    data[revision_url] = []

                bug_data = {
                    'bug_id': bug['id'],
                    'bug_summary': bug_summary,
                    'munged_bug_summary': munged_bug_summary,
                    'test': test,
                    'job_id': job_id,
                    'push_id': push_id,
                    'repository': repository['name'],
                    'revision_url': revision_url,
                    'bugzilla_suggestions': get_job_bugzilla_suggestions_json(new_args, new_args.repo, job_id, update_cache=args.update_cache),
                    'bug_job_map': get_bug_job_map_json(new_args, new_args.repo, job_id, update_cache=args.update_cache),
                    'pattern': convert_bug_summary_to_pattern(munged_bug_summary),
                }

                data[revision_url].append(bug_data)

                # Get failure counts for trunk for this bug for the two weeks following
                # the creation of the bug. Ignore failure counts for bugs who are less
                # than 2 weeks old.
                # TODO: Allow in place updating of bugzilla.json so that we can reprocess
                # the failure counts without having to query the full set of bugs.
                start_date = datetime.datetime.strptime(
                    bug['creation_time'].rstrip('Z'), '%Y-%m-%dT%H:%M:%S') - datetime.timedelta(days=1)
                end_date = start_date + datetime.timedelta(days=15)
                failure_count_json = get_failure_count_json(args, 'trunk', bug['id'], start_date, end_date)
                if now - start_date < datetime.timedelta(days=15):
                    failure_count = None
                else:
                    failure_count = 0
                    for failures in failure_count_json:
                        failure_count += failures['failure_count']
                bug_data['failure_count'] = failure_count

            elif args.whiteboard:
                # This run has specified the test or is this is a bug
                # that is not a Treeherder filed bug. If it was marked
                # via the whiteboad then we are interested in the
                # pushes for this bug.  Since we can't really tell
                # which is which, we can include all of the pushes
                # since only those with test isolation jobs will
                # matter.  The problem is this bug does not
                # necessarily have a bug_summary referencing a test
                # failure...
                comments = response3['bugs'][str(bug['id'])]['comments']
                for comment in comments:
                    if not comment['raw_text'].startswith('Pushed by'):
                        continue
                    # Get the last revision in the comment as the head of the push.
                    revision_url = None
                    pushlog_url_match = re_pushlog_url.search(comment['raw_text'])
                    while pushlog_url_match:
                        revision_url = pushlog_url_match.group(1)
                        pushlog_url_match = re_pushlog_url.search(comment['raw_text'], pushlog_url_match.end(1))
                    if revision_url:
                        # revision_url from Bugzilla has the 12 character revision.
                        new_args = copy.deepcopy(args)
                        new_args.revision_url = revision_url
                        (new_args.repo, _, new_args.revision) = new_args.revision_url.split('/')[-3:]
                        new_args.add_bugzilla_suggestions = True
                        new_args.state = 'completed'
                        new_args.job_type_name = '^test-'
                        new_args.test_failure_pattern = TEST_FAILURE_PATTERN
                        pushes_args.compile_filters(new_args)
                        jobs_args.compile_filters(new_args)

                        pushes = get_pushes_jobs_json(new_args, update_cache=args.update_cache)
                        if len(pushes):
                            # Convert the revision url to 40 characters.
                            push = pushes[0]
                            repository = get_repository_by_id(push['revisions'][0]['repository_id'])
                            revision = push['revisions'][0]['revision']
                            revision_url = '%s/rev/%s' % (repository['url'], revision)
                            new_args.revision_url = revision_url
                            (new_args.repo, _, new_args.revision) = new_args.revision_url.split('/')[-3:]

                            if revision_url not in data:
                                data[revision_url] = []

                            push_id = push['id']
                            repository = get_repository_by_id(push['revisions'][0]['repository_id'])
                            # Only the original job is of interest for collecting the bugzilla data.
                            # The others are the retriggers.
                            #  There shouldn't be a bug_job_map or bugzilla_suggestions for non-classified bugs.
                            job_id = push['jobs'][0]

                            bug_data = {
                                'bug_id': bug['id'],
                                'bug_summary': bug_summary,
                                'test': test,
                                'job_id': job_id,
                                'push_id': push_id,
                                'repository': repository['name'],
                                'revision_url': revision_url,
                                'bugzilla_suggestions': [],
                                'bug_job_map': [],
                                'pattern': convert_bug_summary_to_pattern(bug_summary),
                            }
                            data[revision_url].append(bug_data)

                            # Get failure counts for trunk for this bug for the two weeks following
                            # the creation of the bug. Ignore failure counts for bugs who are less
                            # than 2 weeks old. Use the previous day for the start date and 15 days
                            # to account for timezone issues.
                            # TODO: Allow in place updating of bugzilla.json so that we can reprocess
                            # the failure counts without having to query the full set of bugs.
                            start_date = datetime.datetime.strptime(
                                bug['creation_time'].rstrip('Z'), '%Y-%m-%dT%H:%M:%S') - datetime.timedelta(days=1)
                            end_date = start_date + datetime.timedelta(days=15)
                            failure_count_json = get_failure_count_json(args, 'trunk', bug['id'], start_date, end_date)
                            if now - start_date < datetime.timedelta(days=15):
                                failure_count = None
                            else:
                                failure_count = 0
                                for failures in failure_count_json:
                                    failure_count += failures['failure_count']
                            bug_data['failure_count'] = failure_count

    cache.save(cache_attributes, 'bugzilla.json', json.dumps(data, indent=2))

    return data


failure_munge_res = [
    (re.compile(r'(/?(TEST|PROCESS)-[A-Z-]+ [|] )'), ''),
    (re.compile(r'<test>'), ''),
    (re.compile(r'<>random.js'), ' '),
    (re.compile(r'<anything>.js'), ''),
    (re.compile(r'<random>'), ''),
    (re.compile(r'GECKO[^ ]+ [|] '), ''),
    (re.compile(r'Intermittent '), ''),
    (re.compile(r'PID ([\d]+) [|] '), ''),
    (re.compile(r'Tier 2 ', flags=re.IGNORECASE), ''),
    (re.compile(r'Z:/+', flags=re.IGNORECASE), '/'),
    (re.compile(r'[\[]Exception.*'), ''),
    (re.compile(r'file:/+'), '/'),
    (re.compile(r'fission '), ''),
    (re.compile(r'task_[0-9]+'), 'task_1234'),
    (re.compile(r'xpcshell-remote.ini:'), ''),
]


def munge_failure(failure):
    for regx, replacement in failure_munge_res:
        match = regx.search(failure)
        if match:
            failure = failure.replace(match.group(0), replacement)
    return failure


re_test_failure_pattern = re.compile(r'(TEST-|PROCESS-CRASH)')
re_bad_test = re.compile(r'((Skipping|Finished|.*giving up)|'
                         r'Last test finished|'
                         r'Main app process exited normally|'
                         r'ShutdownLeaks|'
                         r'https?://localhost:\d+/\d+/\d+/.*[.]html|'
                         r'leakcheck|'
                         r'mozrunner-startup|'
                         r'pid: |'
                         r'remoteautomation.py|'
                         r'unknown test url)')
re_extract_tests = [
    re.compile(r'(?:^[^:]+:)?(?:https?|file):[^ ]+/reftest/tests/([^ ]+)'),
    re.compile(r'(?:^[^:]+:)?(?:https?|file):[^:]+:[0-9]+/tests/([^ ]+)'),
    re.compile(r'xpcshell-[^ ]+\.ini:(.*)'),
    re.compile(r'/tests/([^ ]+) - finished .*'),
]


def munge_test_path(test_path):
    if re_bad_test.search(test_path):
        return None
    for r in re_extract_tests:
        m = r.match(test_path)
        if m:
            test_path = m.group(1)
            break
    return test_path


def get_test(failure):
    parts = failure.split(' | ')
    if len(parts) == 3:
        # This matches what we expect from bugzilla_suggestions
        # for actual failure messages.
        # result | test | message
        offset = 2 if 'SimpleTest' in failure else 1
    elif len(parts) == 2 and ('TEST-' in failure or 'PROCESS-' in failure):
        # result | test
        offset = 1
    else:
        # test ...
        offset = 0
    test = munge_test_path(parts[offset])
    if (test is None or test == '<test>') and len(parts) > offset + 1:
        # Fake the test to be the message but really we
        # should be tracking the result, test and message
        # separately.
        test = parts[offset + 1]
        test = munge_test_path(test)
    if test:
        re_appcrashed = re.compile(r'application crash .*')
        match = re_appcrashed.search(test)
        if match:
            test = test.replace(match.group(0), '')
    #if not test:
    #    pass
    #elif ' ' in test:
    #    # reject any test with spaces
    #    test = None
    #elif '/' not in test and '\\' not in test:
    #    # reject any test_path without a separator
    #    test = None
    return test


def summarize_isolation_pushes_jobs_json(args):

    pushes = []

    test_isolation_bugzilla_data = get_test_isolation_bugzilla_data(args)
    for revision_url in test_isolation_bugzilla_data:
        revision_data = test_isolation_bugzilla_data[revision_url]
        for revision_bug_data in revision_data:
            if args.bugs and revision_bug_data['bug_id'] not in args.bugs:
                # Skip if we requested a specific bug and this is not it.
                continue
            if args.bugs and args.override_bug_summary:
                bug_summary = args.override_bug_summary
            else:
                bug_summary = revision_bug_data['bug_summary']
            revision_bug_data['bug_summary'] = munge_failure(bug_summary)
            new_args = copy.deepcopy(args)
            new_args.revision_url = revision_url
            (new_args.repo, _, new_args.revision) = new_args.revision_url.split('/')[-3:]
            new_args.add_bugzilla_suggestions = True
            new_args.state = 'completed'
            new_args.result = None
            new_args.job_type_name = '^test-'
            new_args.test_failure_pattern = TEST_FAILURE_PATTERN
            jobs_args.compile_filters(new_args)

            # Load the pushes/jobs data from cache if it exists.
            cache_attributes = ['test-isolation', new_args.repo]
            pushes_jobs_data = cache.load(cache_attributes, new_args.revision)
            if pushes_jobs_data and not args.update_cache:
                new_pushes = json.loads(pushes_jobs_data)
            else:
                new_pushes = get_pushes_jobs_json(new_args, new_args.repo, update_cache=args.update_cache)
                cache.save(cache_attributes, new_args.revision, json.dumps(new_pushes, indent=2))

            pushes.extend(new_pushes)

    pushes_jobs_data = None
    data = convert_pushes_to_test_isolation_bugzilla_data(args, pushes)

    summary = {}

    for revision_url in data:

        if revision_url not in summary:
            summary[revision_url] = {}
        summary_revision = summary[revision_url]

        job_type_names = sorted(data[revision_url].keys())

        for job_type_name in job_type_names:
            if job_type_name not in summary_revision:
                summary_revision[job_type_name] = summary_revision_job_type = {}
            job_type = data[revision_url][job_type_name]

            if 'bugzilla_data' not in summary_revision_job_type:
                summary_revision_job_type['bugzilla_data'] = copy.deepcopy(test_isolation_bugzilla_data[revision_url])
                for bug_data in summary_revision_job_type['bugzilla_data']:
                    # bug_data['failure_reproduced'][section_name] counts the
                    # number of times the original bug_summary failure
                    # was seen in that section of jobs.
                    bug_data['failure_reproduced'] = {
                        'original': 0,
                        'repeated': 0,
                        'id': 0,
                        'it': 0,
                    }
                    # bug_data['test_reproduced'][section_name] counts the
                    # number of times the original bug_summary test
                    # was seen in that section of jobs.
                    bug_data['test_reproduced'] = {
                        'original': 0,
                        'repeated': 0,
                        'id': 0,
                        'it': 0,
                    }

            for section_name in (ORIGINAL_SECTIONS + ISOLATION_SECTIONS):
                if section_name not in summary_revision_job_type:
                    summary_revision_job_type[section_name] = summary_revision_job_type_section = {}
                    summary_revision_job_type_section['failures'] = {}
                    summary_revision_job_type_section['tests'] = {}
                    summary_revision_job_type_section['failure_reproduced'] = 0
                    summary_revision_job_type_section['test_reproduced'] = 0
                    if section_name == 'original':
                        summary_revision_job_type_section['bug_job_map'] = []
                job_type_section = job_type[section_name]
                run_time = 0
                jobs_testfailed_count = 0
                bugzilla_suggestions_count = 0

                for job in job_type_section:
                    if section_name == 'original':
                        summary_revision_job_type_section['bug_job_map'].extend(job['bug_job_map'])
                    run_time += job['end_timestamp'] - job['start_timestamp']
                    jobs_testfailed_count += 1 if job['result'] == 'testfailed' else 0
                    bugzilla_suggestions_count += len(job['bugzilla_suggestions'])

                    for bugzilla_suggestion in job['bugzilla_suggestions']:

                        failure = munge_failure(bugzilla_suggestion['search'])
                        if failure not in summary_revision_job_type_section['failures']:
                            summary_revision_job_type_section['failures'][failure] = {
                                'count': 0,
                            }
                            summary_revision_job_type_section['failures'][failure]['failure_reproduced'] = 0

                        summary_revision_job_type_section['failures'][failure]['count'] += 1
                        for bug_data in summary_revision_job_type['bugzilla_data']:
                            if args.bugs and args.override_bug_summary:
                                pattern = convert_bug_summary_to_pattern(munge_failure(args.override_bug_summary))
                            else:
                                pattern = bug_data['pattern']
                            if re.compile(pattern).search(failure):
                                bug_data['failure_reproduced'][section_name] += 1
                                summary_revision_job_type_section['failures'][failure]['failure_reproduced'] += 1
                                summary_revision_job_type_section['failure_reproduced'] += 1

                            test = get_test(failure)

                            if test not in summary_revision_job_type_section['tests']:
                                summary_revision_job_type_section['tests'][test] = {
                                    'count': 0,
                                }
                                summary_revision_job_type_section['tests'][test]['test_reproduced'] = 0

                            summary_revision_job_type_section['tests'][test]['count'] += 1
                            if args.bugs and args.override_bug_summary:
                                bug_data_test = get_test(args.override_bug_summary)
                            else:
                                bug_data_test = bug_data['test']
                            if test and bug_data_test and test in bug_data_test:
                                bug_data['test_reproduced'][section_name] += 1
                                summary_revision_job_type_section['tests'][test]['test_reproduced'] += 1
                                summary_revision_job_type_section['test_reproduced'] += 1

                summary_revision_job_type_section['run_time'] = run_time
                summary_revision_job_type_section['jobs_testfailed'] = jobs_testfailed_count
                summary_revision_job_type_section['jobs_total'] = len(job_type_section)
                summary_revision_job_type_section['bugzilla_suggestions_count'] = bugzilla_suggestions_count

    return summary


def convert_pushes_to_test_isolation_bugzilla_data(args, pushes):
    """Take the push/job data, collecting the jobs which are related to
    test isolation (group symbol suffix -I) and organizing them in a
    dict according to.

    data = {
        '<revision_url>': {
            '<job-type-name>': {
                'original': [],
                'repeated': [],
                'id': [],
                'it': [],
            },
        },
        ...
    }

    """
    re_job_group_symbol = re.compile(r'-I$')
    re_job_type_symbol = re.compile(r'-(id|it)$')

    def is_isolation_job_group_symbol(job_group_symbol):
        return re_job_group_symbol.search(job_group_symbol)

    def is_isolation_job_type_symbol(job_type_symbol):
        match = re_job_type_symbol.search(job_type_symbol)
        if match:
            return match.group(1)
        return None

    data = {}

    for push in pushes:
        repository = get_repository_by_id(push['revisions'][0]['repository_id'])
        revision = push['revisions'][0]['revision']
        revision_url = '%s/rev/%s' % (repository['url'], revision)

        if revision_url not in data:
            data[revision_url] = {}
        revision_data = data[revision_url]

        # Find the job_type_names associated with test isolation jobs.
        # It may seem that this loop is redundant with the next loop,
        # however we want to process not only the isolation jobs but
        # the original jobs as well. To do this, we first iterate over
        # the jobs and initialize the revision_data to include a
        # job_type_name property for job types which have isolation
        # jobs. We can then use this information in the next loop to
        # discard jobs which were not isolated and to distinguish
        # original from repeated, id and it isolation jobs.
        for job in push['jobs']:
            job_type_symbol = job['job_type_symbol']
            job_group_symbol = job['job_group_symbol']
            isolation_group = is_isolation_job_group_symbol(job_group_symbol)
            isolation_type = is_isolation_job_type_symbol(job_type_symbol)
            if isolation_group or isolation_type:
                job_type_name = job['job_type_name']
                if job_type_name not in data:
                    revision_data[job_type_name] = {
                        'original': [],
                        'repeated': [],
                        'id': [],
                        'it': [],
                    }

        # Collect the test isolation jobs
        for job in push['jobs']:
            job_type_name = job['job_type_name']
            if job_type_name not in revision_data:
                continue
            data_job_type = revision_data[job_type_name]
            job_type_symbol = job['job_type_symbol']
            job_group_symbol = job['job_group_symbol']
            isolation_type = is_isolation_job_type_symbol(job_type_symbol)
            isolation_group = is_isolation_job_group_symbol(job_group_symbol)
            if isolation_type is None and isolation_group is None:
                data_job_type['original'].append(job)
                # Add the bug_job_map object to the original job
                # in order to track which bug was "isolated".
                job['bug_job_map'] = get_bug_job_map_json(args, repository['name'], job['id'], update_cache=args.update_cache)
            elif isolation_type == 'id':
                data_job_type['id'].append(job)
            elif isolation_type == 'it':
                data_job_type['it'].append(job)
            elif isolation_group:
                data_job_type['repeated'].append(job)
            else:
                pass

    return data


def output_csv_summary(args, summary):
    properties = ('jobs_total', 'jobs_testfailed', 'run_time',)

    line = 'revision;job_type_name;bug;bugmap;summary;failure_count;'

    for section_name in (ORIGINAL_SECTIONS + ISOLATION_SECTIONS):
        for property_name in properties:
            line += '%s.%s;' % (section_name, property_name)

    for section_name in (ORIGINAL_SECTIONS + ISOLATION_SECTIONS):
        line += '%s.bug_data.failure_reproduced;' % section_name
        line += '%s.bug_data.test_reproduced;' % section_name

    line = line[0:-1]
    print(line)

    for revision_url in summary:
        summary_revision = summary[revision_url]
        for job_type_name in summary_revision:
            summary_revision_job_type = summary_revision[job_type_name]
            for bug_data in summary_revision_job_type['bugzilla_data']:
                bug_id = bug_data['bug_id']
                if args.override_bug_summary:
                    bug_summary = munge_failure(args.override_bug_summary)
                else:
                    bug_summary = bug_data['bug_summary'].replace(';', ' ')
                failure_count = bug_data['failure_count']
                bug_job_map = summary_revision_job_type['original']['bug_job_map']
                bugs = ','.join(sorted(set([ str(job_bug['bug_id']) for job_bug in bug_job_map ])))
                if bugs and str(bug_id) not in bugs:
                    # Ignore other bugs filed for this revision if they are not in the
                    # current job bug map but only if there are other bugs filed.
                    continue
                line = '%s;%s;%s;%s;%s;%s;' % (
                    revision_url, job_type_name, bug_id, bugs, bug_summary, failure_count)

                for section_name in (ORIGINAL_SECTIONS + ISOLATION_SECTIONS):
                    summary_revision_job_type_section = summary_revision_job_type[section_name]
                    for property_name in properties:
                        line += '%s;' % summary_revision_job_type_section[property_name]

                for section_name in (ORIGINAL_SECTIONS + ISOLATION_SECTIONS):
                    line += '%s;' % bug_data['failure_reproduced'][section_name]
                    line += '%s;' % bug_data['test_reproduced'][section_name]

                line = line[0:-1]
                print(line)


def output_csv_results(args, summary):
    print('revision;job_type_name;section;result_type;result_name;count;reproduced')

    for revision_url in summary:
        summary_revision = summary[revision_url]
        for job_type_name in summary_revision:
            summary_revision_job_type = summary_revision[job_type_name]

            for section_name in ISOLATION_SECTIONS:
                summary_revision_job_type_section = summary_revision_job_type[section_name]
                if args.include_failures:
                    for failure_message in summary_revision_job_type_section['failures']:
                        failure = summary_revision_job_type_section['failures'][failure_message]
                        print('%s;%s;%s;%s;%s;%s;%s' % (
                            revision_url,
                            job_type_name,
                            section_name,
                            'failure',
                            failure_message,
                            failure['count'],
                            failure['failure_reproduced']))
                if args.include_tests:
                    for test_name in summary_revision_job_type_section['tests']:
                        test = summary_revision_job_type_section['tests'][test_name]
                        print('%s;%s;%s;%s;%s;%s;%s' % (
                            revision_url,
                            job_type_name,
                            section_name,
                            'test',
                            test_name,
                            test['count'],
                            test['test_reproduced']))


def main():
    """main"""

    parent_parsers = [
        log_level_args.get_parser(),
        treeherder_urls_args.get_parser(),
        pushes_args.get_parser(),
        jobs_args.get_parser(),
    ]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""
Analyze pushes from bugs marked with whiteboard [test isolation] or a
value specified from the command options.

Queries Bugzilla for bugs marked with [test isolation] in the whiteboard,
determines the bug number, bug summary and revision from the bug then reads
push and job data from Treeherder and produces a summary of runtimes and
test failures, writing results as either csv text or json to stdout. By
default, output is writtenas formatted json.

Intermediate results are stored in a cache directory to re-used on subsequent
runs. When changing options, it is safest to delete the cache directory and
start over.

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
        '--whiteboard',
        default='[test isolation]',
        help='Bugzilla whiteboard value used to select the appropriate bugs. '
        'Should only be used with --bug.')

    parser.add_argument(
        '--override-bug-summary',
        default=None,
        help='When reprocessing a bug with a problematic bug summary '
        'or when using --whiteboard to select a bug not filed by '
        'intermittent-bug-filer, specify an override bug summary '
        'to mimic an intermittent bug summary to be used to determine '
        'if a failure or test is reproduced. Otherwise the original bug '
        'summary will be used. Should only be used with --bug.')

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
        '--bug-creation-time',
        help='Starting creation time in YYYY-MM-DD or '
        'YYYY-MM-DDTHH:MM:SSTZ format. '
        'Example 2019-07-27T17:28:00PDT or 2019-07-28T00:28:00Z',
        default='2019-06-14')

    parser.add_argument(
        '--bugs-after',
        type=int,
        help='Only returns bugs whose id is greater than this integer.',
        default=None)

    parser.add_argument(
        '--bug',
        dest='bugs',
        type=int,
        action='append',
        default=[],
        help='Only returns results for bug the specified bug.')

    parser.add_argument(
        '--raw',
        action='store_true',
        default=False,
        help='Do not reformat/indent json.')

    parser.add_argument(
        '--csv-summary',
        action='store_true',
        default=False,
        help='Output summary data in csv format. Does not include individual failures or tests.')

    parser.add_argument(
        '--csv-results',
        action='store_true',
        default=False,
        help='Output test data in csv format. Does not include individual failures.')

    parser.add_argument(
        '--include-failures',
        action='store_true',
        default=False,
        help='Include individual failures in output.')

    parser.add_argument(
        '--include-tests',
        action='store_true',
        default=False,
        help='Include individual tests in output.')

    parser.set_defaults(func=summarize_isolation_pushes_jobs_json)

    args = parser.parse_args()

    args.cache = os.path.expanduser(args.cache)

    pushes_args.compile_filters(args)
    jobs_args.compile_filters(args)

    if args.test_failure_pattern:
        args.test_failure_pattern = re.compile(args.test_failure_pattern)

    if (args.whiteboard != '[test isolation]' or args.override_bug_summary) and not args.bugs:
        parser.error('--bug must be specified if either --whiteboard or '
                     '--override-test are specified.')

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug('main %s', args)

    if not os.path.isdir(args.cache):
        os.makedirs(args.cache)
    cache.CACHE_HOME = args.cache

    init_treeherder(args.treeherder_url)

    summary = args.func(args)

    if args.raw:
        print(summary)
    elif args.csv_summary:
        output_csv_summary(args, summary)
    elif args.csv_results:
        output_csv_results(args, summary)
    else:
        print(json.dumps(summary, indent=2))

    if args.dump_cache_stats:
        cache.stats()


if __name__ == '__main__':
    main()
