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
    get_client,
    get_job_by_repo_job_id_json,
    get_pushes_jobs_json,
    get_failure_count_json,
    get_repositories,
    get_repository_by_id,
)


BUGZILLA_URL = 'https://bugzilla.mozilla.org/rest/'


def get_test_isolation_bugzilla_data(args):
    """Query Bugzilla for bugs marked with [test isolation] in the
    whiteboard.  Return a dictionary keyed by revision url containing
    the bug id and summary.

    """

    logger = logging.getLogger()

    # Load the bugzilla data from cache if it exists.
    bugzilla_cache = os.path.join(args.cache, 'bugzilla.json')
    if os.path.exists(bugzilla_cache):
        with open(bugzilla_cache) as cache:
            return json.loads(cache.read())

    now = datetime.datetime.now()

    data = {}

    client = get_client(args)

    re_logview = re.compile(r'https://treeherder.mozilla.org/logviewer.html#\?job_id=([0-9]+)&repo=([a-z-]+)')
    query = BUGZILLA_URL + 'bug?'
    query_terms = {
        'include_fields': 'id,creation_time',
        'creator': 'intermittent-bug-filer@mozilla.bugs',
        'creation_time': args.bug_creation_time,
        'status_whiteboard': '[test isolation]',
        'limit': 100,
        'offset': 0,
        }

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

            if bug['id'] <= args.bugs_after:
                continue

            query2 = BUGZILLA_URL + 'bug/%s' % bug['id']
            response2 = utils.get_remote_json(query2)
            if 'error' in response2:
                logger.error('Bugzilla({}): {}'.format(query2, response2))
                return

            bug_summary = response2['bugs'][0]['summary'].replace('Intermittent ', '')

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
                job = get_job_by_repo_job_id_json(args, repo, job_id)
                push_id = job['push_id']
                push = client.get_pushes(repo, id=push_id)[0]
                repository = get_repository_by_id(push['revisions'][0]['repository_id'])
                revision = push['revisions'][0]['revision']
                revision_url = '%s/rev/%s' % (repository['url'], revision)

                data[revision_url] = {
                    'bug_id': bug['id'],
                    'bug_summary': bug_summary
                }

                # Get failure counts for trunk for this bug for the two weeks following
                # the creation of the bug. Ignore failure counts for bugs who are less
                # than 2 weeks old.
                # TODO: Allow in place updating of bugzilla.json so that we can reprocess
                # the failure counts without having to query the full set of bugs.
                start_date = datetime.datetime.strptime(
                    bug['creation_time'].rstrip('Z'), '%Y-%m-%dT%H:%M:%S')
                end_date = start_date + datetime.timedelta(weeks=2)
                failure_count_json = get_failure_count_json(args, 'trunk', bug['id'], start_date, end_date)
                if now - start_date < datetime.timedelta(weeks=2):
                    failure_count = None
                else:
                    failure_count = 0
                    for failures in failure_count_json:
                        failure_count += failures['failure_count']
                data[revision_url]['failure_count'] = failure_count

    with open(bugzilla_cache, mode='w+b') as cache:
        cache.write(bytes(json.dumps(data, indent=2), encoding='utf-8'))

    return data


def summarize_isolation_pushes_jobs_json(args):
    failure_munge_res = [
        re.compile(r'GECKO[(]([\d]+)[)] [|] '),
        re.compile(r'PID ([\d]+) [|] '),
    ]
    def munge_failure(failure):
        for r in failure_munge_res:
            match = r.search(failure)
            if match:
                failure = failure.replace(match.group(1), '')
        return failure
    def get_test(failure):
        try:
            # Handle result | test | message and test | message
            parts = failure.split(' | ')
            return parts[len(parts) - 2]
        except IndexError:
            return failure

    pushes = []

    isolation_data = get_test_isolation_bugzilla_data(args)
    for revision_url in isolation_data:
        revision_data = isolation_data[revision_url]
        revision_data['bug_summary'] = munge_failure(revision_data['bug_summary'])
        new_args = copy.deepcopy(args)
        new_args.revision_url = revision_url
        (new_args.repo, _, new_args.revision) = new_args.revision_url.split('/')[-3:]
        new_args.add_bugzilla_suggestions = True
        new_args.state = 'completed'
        new_args.job_type_name = '^test-'

        if args.test_failure_pattern:
            new_args.test_failure_pattern = args.test_failure_pattern
        else:
            pattern_parts = revision_data['bug_summary'].split(' | ')
            for i in range(len(pattern_parts)):
                pattern_parts[i] = re.escape(pattern_parts[i])
            pattern = '|'.join(pattern_parts)
            new_args.test_failure_pattern = pattern
            revision_data['pattern'] = pattern
        jobs_args.compile_filters(new_args)
        # Load the pushes/jobs data from cache if it exists.
        pushes_jobs_cache_dir = os.path.join(args.cache, new_args.repo)
        if not os.path.isdir(pushes_jobs_cache_dir):
            os.makedirs(pushes_jobs_cache_dir)
        pushes_jobs_cache = os.path.join(pushes_jobs_cache_dir, new_args.revision)
        if os.path.exists(pushes_jobs_cache):
            with open(pushes_jobs_cache) as cache:
                new_pushes = json.loads(cache.read())
        else:
            new_pushes = get_pushes_jobs_json(new_args)
            with open(pushes_jobs_cache, mode='w+b') as cache:
                cache.write(bytes(json.dumps(new_pushes, indent=2), encoding='utf-8'))

        pushes.extend(new_pushes)

    data = convert_pushes_to_isolation_data(args, pushes)

    summary = {}

    for revision_url in data:

        if revision_url not in summary:
            summary[revision_url] = {}
        revision_summary = summary[revision_url]

        job_type_names = sorted(data[revision_url].keys())

        for job_type_name in job_type_names:
            if job_type_name not in revision_summary:
                revision_summary[job_type_name] = job_type_summary = {}
            job_type = data[revision_url][job_type_name]

            if 'bug' not in job_type_summary:
                job_type_summary['bug'] = isolation_data[revision_url]
                job_type_summary['bug']['reproduced'] = {
                    'original': 0,
                    'repeated': 0,
                    'id': 0,
                    'it': 0,
                }

            for section_name in ('original', 'repeated', 'id', 'it'):
                if section_name not in job_type_summary:
                    job_type_summary[section_name] = job_type_section_summary = {}
                    job_type_section_summary['failures'] = {}
                    job_type_section_summary['tests'] = {}
                    if section_name == 'original':
                        job_type_section_summary['job_bug_map'] = []
                section = job_type[section_name]
                run_time = 0
                number_jobs_testfailed = 0
                number_failures = 0

                for job in section:
                    if section_name == 'original':
                        job_type_section_summary['job_bug_map'].extend(job['job_bug_map'])
                    run_time += job['end_timestamp'] - job['start_timestamp']
                    number_jobs_testfailed += 1 if job['result'] == 'testfailed' else 0
                    number_failures += len(job['bugzilla_suggestions'])

                    for bugzilla_suggestion in job['bugzilla_suggestions']:
                        failure = munge_failure(bugzilla_suggestion['search'])
                        if failure not in job_type_section_summary['failures']:
                            job_type_section_summary['failures'][failure] = {
                                'count': 0,
                            }
                            if section_name != 'original':
                                job_type_section_summary['failures'][failure]['failure_reproduced'] = 0
                        job_type_section_summary['failures'][failure]['count'] += 1
                        if job_type_summary['bug']['bug_summary'] in failure:
                            job_type_summary['bug']['reproduced'][section_name] += 1

                for failure in job_type_section_summary['failures']:
                    test = get_test(failure)
                    if test not in job_type_section_summary['tests']:
                        job_type_section_summary['tests'][test] = {
                            'count': job_type_section_summary['failures'][failure]['count'],
                        }
                        if section_name != 'original':
                            job_type_section_summary['tests'][test]['test_reproduced'] = job_type_section_summary['failures'][failure]['failure_reproduced']
                job_type_section_summary['run_time'] = run_time
                job_type_section_summary['jobs_failed'] = number_jobs_testfailed
                job_type_section_summary['jobs_total'] = len(section)
                job_type_section_summary['tests_failed'] = number_failures
                if section_name != 'original':
                    job_type_section_summary['failure_reproduced'] = 0
                    job_type_section_summary['test_reproduced'] = 0

            job_type_original_summary = job_type_summary['original']

            for section_name in ('repeated', 'id', 'it'):
                job_type_section_summary = job_type_summary[section_name]

                for failure in job_type_section_summary['failures']:
                    if failure in job_type_original_summary['failures']:
                        count = job_type_section_summary['failures'][failure]['count']
                        job_type_section_summary['failures'][failure]['failure_reproduced'] += count
                        job_type_section_summary['failure_reproduced'] += count

                for test in job_type_section_summary['tests']:
                    if test in job_type_original_summary['tests']:
                        count = job_type_section_summary['tests'][test]['count']
                        job_type_section_summary['tests'][test]['test_reproduced'] += count
                        job_type_section_summary['test_reproduced'] += count

    if not args.include_failures:
        # Remove failures lists from sections
        for revision_url in summary:
            revision_summary = summary[revision_url]
            for job_type_name in revision_summary:
                for section_name in revision_summary[job_type_name]:
                    summary_section = revision_summary[job_type_name][section_name]
                    if 'failures' in summary_section:
                        del summary_section['failures']
                    if 'failure_reproduced' in summary_section:
                        del summary_section['failure_reproduced']

    if not args.include_tests:
        # Remove tests lists from sections
        for revision_url in summary:
            revision_summary = summary[revision_url]
            for job_type_name in revision_summary:
                for section_name in revision_summary[job_type_name]:
                    summary_section = revision_summary[job_type_name][section_name]
                    if 'tests' in summary_section:
                        del summary_section['tests']
                    if 'test_reproduced' in summary_section:
                        del summary_section['test_reproduced']
    return summary


def convert_pushes_to_isolation_data(args, pushes):
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

        # Find the job_type_names associated with test isolation jobs
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
                # Add the job_bug_map object to the original job
                # in order to track which bug was "isolated".
                job['job_bug_map'] = get_bug_job_map_json(args, repository['name'], job['id'])
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
    line = 'revision;job_type_name;bug;summary;failure_count;'

    for section_name in ('original', 'repeated', 'id', 'it'):
        line += 'reproduced.%s;' % section_name

    line += 'bugmap;'

    properties = ('run_time', 'jobs_total', 'jobs_failed', 'tests_failed')

    for section_name in ('repeated', 'id', 'it'):
        for property_name in properties:
            line += '%s.%s;' % (section_name, property_name)
        if args.include_failures:
            line += '%s.failure_reproduced;' % section_name
        if args.include_tests:
            line += '%s.test_reproduced;' % section_name

    line = line[0:-1]
    print(line)

    for revision_url in summary:
        revision_summary = summary[revision_url]
        for job_type_name in revision_summary:
            job_type_summary = revision_summary[job_type_name]
            bug_id = job_type_summary['bug']['bug_id']
            bug_summary = job_type_summary['bug']['bug_summary'].replace(';', ' ')
            failure_count = job_type_summary['bug']['failure_count']
            job_bug_map = revision_summary[job_type_name]['original']['job_bug_map']
            bugs = ' '.join(sorted(set([ str(job_bug['bug_id']) for job_bug in job_bug_map ])))
            line = '%s;%s;%s;%s;%s;' % (
                revision_url, job_type_name, bug_id, bug_summary, failure_count)

            for section_name in ('original', 'repeated', 'id', 'it'):
                line += '%s;' % job_type_summary['bug']['reproduced'][section_name]

            line += '%s;' % bugs

            for section_name in ('repeated', 'id', 'it'):
                job_type_section = job_type_summary[section_name]
                for property_name in properties:
                    line += '%s;' % job_type_section[property_name]
                if section_name != 'original':
                    if args.include_failures:
                        line += '%s;' % job_type_section['failure_reproduced']
                    if args.include_tests:
                        line += '%s;' % job_type_section['test_reproduced']
            line = line[0:-1]
            print(line)


def output_csv_results(args, summary):
    print('revision;job_type_name;section;result_type;result_name;count;reproduced')

    for revision_url in summary:
        revision_summary = summary[revision_url]
        for job_type_name in revision_summary:
            job_type_summary = revision_summary[job_type_name]

            for section_name in ('repeated', 'id', 'it'):
                job_type_section = job_type_summary[section_name]
                if args.include_failures:
                    for failure_message in job_type_section['failures']:
                        failure = job_type_section['failures'][failure_message]
                        print('%s;%s;%s;%s;%s;%s;%s' % (
                            revision_url,
                            job_type_name,
                            section_name,
                            'failure',
                            failure_message,
                            failure['count'],
                            failure['failure_reproduced']))
                if args.include_tests:
                    for test_name in job_type_section['tests']:
                        test = job_type_section['tests'][test_name]
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
Analyze pushes from bugs marked with whiteboard [test isolation].

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
        '--cache',
        default='/tmp/test_isolation_cache/',
        help='Directory used to store cached objects retrieved from Bugzilla '
        'and Treeherder.')

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
        default=0)

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

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug('main %s', args)

    if not os.path.isdir(args.cache):
        os.makedirs(args.cache)

    get_repositories(args)

    summary = args.func(args)

    if args.raw:
        print(summary)
    elif args.csv_summary:
        output_csv_summary(args, summary)
    elif args.csv_results:
        output_csv_results(args, summary)
    else:
        print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
