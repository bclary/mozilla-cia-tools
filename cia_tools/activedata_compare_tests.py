#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
docstring
"""

#params = {
#    'push_startdate': utils.date_to_timestamp(utils.CCYY_MM_DD_to_date(args.start_date)),
#    'push_enddate': utils.date_to_timestamp(utils.CCYY_MM_DD_to_date(args.end_date))
#}

import argparse
import copy
import json
import logging
import re

import thclient

import common_args
import utils


def compare_tests_load_push_tests(data, args, push, filters=None, push_label=None,
                                  count_label=None):
    """
    data is an object passed from the caller which collects the tests to be compared.

    load tests from the push, limited by the activedata test filters while
    changing the "count" label in the response to the new count_label.
    """
    #logger = logging.getLogger()

    query_json = {
        "format":"list",
        "from":"unittest",
        "groupby":"run.key",
        "limit":10000,
        "where":{"and":[
            {"eq":{"build.branch":args.repo}},
            {"eq":{"build.revision":push['revision']}}
        ]}
    }
    if filters:
        query_json['where']['and'].extend(filters)

    push_data = {}
    push_label = "{}-{}".format(args.repo, push['revision'][:12])
    if push_label not in data:
        data[push_label] = {}

    response = utils.query_active_data(query_json, limit=10000)

    for item in response['data']:
        # item contains {u'count': 14181, u'run': {u'key': u'test-linux64/opt-jsreftest-e10s-2'}}
        item[count_label] = item['count']
        del item['count']
        key = item['run']['key']
        del item['run']
        sub_key = list(item.keys())[0]

        if key not in push_data:
            push_data[key] = {}
        push_data[key] = utils.merge_dicts(push_data[key], item)

    if args.combine_chunks:
        old = copy.deepcopy(push_data)
        push_data = {}
        for key in old.keys():
            new_key = re.sub('-[0-9]+$', '', key)

            if new_key not in push_data:
                push_data[new_key] = {}
                for sub_key in old[key]:
                    push_data[new_key][sub_key] = 0
            for sub_key in old[key]:
                push_data[new_key][sub_key] += old[key][sub_key]

    for key in push_data:
        if key not in data[push_label]:
            data[push_label][key] = {}
        data[push_label][key] = utils.merge_dicts(data[push_label][key], push_data[key])


def compare_tests(args):
    """
    compare tests
    """
    logger = logging.getLogger()
    logger.debug('compare_tests args %s', args)

    data = {}
    push_params = utils.get_treeherder_push_params(args)

    client = thclient.client.TreeherderClient(server_url=args.treeherder)
    pushes = client.get_pushes(args.repo, **push_params)
    logger.debug('compare_tests pushes\n:%s', pushes)

    if not pushes:
        logger.warning("compare_tests: no pushes found.")
        return

    for push in pushes:
        logger.debug("compare_tests push:\n%s", json.dumps(push, indent=2, sort_keys=True))

        compare_tests_load_push_tests(data, args, push,
                                      filters=None,
                                      count_label='all')
        compare_tests_load_push_tests(data, args, push,
                                      filters=[{"eq":{"result.ok":False}}],
                                      count_label='failed')
        compare_tests_load_push_tests(data, args, push,
                                      filters=[{"eq":{"result.ok":True}}],
                                      count_label='passed')

    keys_set = set()
    sub_keys_set = set()
    # Collect the keys and subkeys.
    for push_label in data.keys():
        push_label_keys = list(data[push_label].keys())
        keys_set.update(set(push_label_keys))
        for key in push_label_keys:
            push_label_key_sub_keys = list(data[push_label][key].keys())
            sub_keys_set.update(set(push_label_key_sub_keys))

    for push_label in data.keys():
        for key in keys_set:
            if key not in data[push_label]:
                data[push_label][key] = {}
            for sub_key in sub_keys_set:
                if sub_key not in data[push_label][key]:
                    data[push_label][key][sub_key] = 0

    columns = 'key'
    push_labels = list(data.keys())
    push_labels.sort()
    push_label = list(data.keys())[0]

    keys = list(data[push_label].keys())
    keys.sort()

    sub_keys = list(sub_keys_set)
    sub_keys.sort()

    for sub_key in sub_keys:
        for push_label in push_labels:
            columns += ',' + push_label + '-' + sub_key
        for i in range(len(push_labels)-1):
            lpush_label = push_labels[i]
            rpush_label = push_labels[i+1]
            columns += ',' + lpush_label + '-' + sub_key + ' - ' + rpush_label + '-' + sub_key

    print(columns)
    for key in keys:
        total_differences = 0
        line = key
        for sub_key in sub_keys:
            for push_label in push_labels:
                line += ",%s" % data[push_label][key][sub_key]
            for i in range(len(push_labels)-1):
                lpush_label = push_labels[i]
                rpush_label = push_labels[i+1]
                diff = (data[lpush_label][key][sub_key] -
                        data[rpush_label][key][sub_key])
                total_differences += abs(diff)
                line += ",%s" % diff
        if (args.output_push_differences_only and total_differences > 0 or not
                args.output_push_differences_only):
            print(line)


def main():
    log_level_parser = common_args.log_level.get_parser()
    push_selection_parser = common_args.push_selection.get_parser()
    urls_parser = common_args.urls.get_parser()

    parser = argparse.ArgumentParser(
        description="""ActiveData compare-tests""",
        formatter_class=common_args.ArgumentFormatter,
        epilog="""You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.""",
        parents=[log_level_parser, urls_parser, push_selection_parser],
        fromfile_prefix_chars='@'
        )

    parser.add_argument("--combine-chunks",
                                      action="store_true",
                                      default=False,
                                      help="Combine chunks")

    parser.add_argument(
        "--output-push-differences-only",
        action="store_true",
        default=False,
        help="""When loading multiple pushes, only output keys which have different
        values for sub_keys across the
        pushes.""")

    parser.set_defaults(func=compare_tests)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    args.func(args)


main()
