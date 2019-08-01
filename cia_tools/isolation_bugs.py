#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import re

import utils


from treeherder import get_client, get_job_by_repo_job_id_json, get_repositories, get_repository_by_id

BUGZILLA_URL = 'https://bugzilla.mozilla.org/rest/'

from common_args import (ArgumentFormatter,
                         log_level_args,
                         treeherder_urls_args)


def get_test_isolation_revisions(args, from_date=None, to_date=None):

    logger = logging.getLogger()

    revisions = []

    get_repositories(args)

    client = get_client(args)

    re_logview = re.compile(r'https://treeherder.mozilla.org/logviewer.html#\?job_id=([0-9]+)&repo=([a-z-]+)')
    query = BUGZILLA_URL + 'bug?'
    query_terms = {
        'include_fields': 'id',
        'creator': 'intermittent-bug-filer@mozilla.bugs',
        'creation_time': args.creation_time,
        'status_whiteboard': '[test isolation]',
        }

    response = utils.get_remote_json(query, params=query_terms)
    if 'error' in response:
        print('%s' % response)
        return

    for bug in response['bugs']:
        #https://bugzilla.mozilla.org/rest/bug/1559260/comment

        query = BUGZILLA_URL + 'bug/%s/comment' % bug['id']
        response = utils.get_remote_json(query)
        if 'error' in response:
            print('%s' % response)
            return

        raw_text = response['bugs'][str(bug['id'])]['comments'][0]['raw_text']
        match = re_logview.search(raw_text)
        if match:
            job_id = int(match.group(1))
            repo = match.group(2)
            job = get_job_by_repo_job_id_json(args, repo, job_id)
            push_id = job['push_id']
            push = client.get_pushes(repo, id=push_id)[0]
            repository = get_repository_by_id(push['revisions'][0]['repository_id'])
            revision = push['revisions'][0]['revision']
            revision_url = "%s/rev/%s" % (repository["url"], revision)
            revisions.append(revision_url)

            logger.debug('Bug %s, Revision %s' % (bug['id'], revision_url))

    return revisions


def main():
    parent_parsers = [log_level_args.get_parser(),
                      treeherder_urls_args.get_parser()]

    additional_descriptions = [parser.description for parser in parent_parsers
                               if parser.description]
    additional_epilogs = [parser.epilog for parser in parent_parsers if parser.epilog]

    parser = argparse.ArgumentParser(
        description="""Get revisions from bugs marked with whiteboard [test isolation].

%s
""" % '\n\n'.join(additional_descriptions),
        formatter_class=ArgumentFormatter,
        epilog="""
%s

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
"""  % '\n\n'.join(additional_epilogs),
        parents=parent_parsers,
        fromfile_prefix_chars='@'
        )

    parser.add_argument('--creation-time',
                        help="Starting creation time in YYYY-MM-DD or "
                        "YYYY-MM-DDTHH:MM:SSTZ format. "
                        "Example 2019-07-27T17:28:00PDT or 2019-07-28T00:28:00Z'",
                        default="2019-06-14")
    parser.set_defaults(func=get_test_isolation_revisions)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    revisions = sorted(set(args.func(args)))
    print('\n'.join(revisions))


if __name__ == '__main__':
    main()
