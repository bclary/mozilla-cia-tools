#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging
import re

from numbers import Number

from common_args import ArgumentFormatter, log_level_args

def compare_aliases(re_ignore, alias_names, data):
    combined_keys = list(data["combined"].keys())
    combined_keys.sort()

    naliases = len(alias_names)

    comparison = {
        "aliases": data["aliases"],
        "differences": {},
    }

    differences = comparison["differences"]

    for key in combined_keys:
        if re_ignore:
            match = re_ignore.search(key)
            if match:
                continue
        l = 0
        while l+1 < naliases:
            r = l + 1
            l_alias_name = alias_names[l]
            r_alias_name = alias_names[r]

            l_data = data["combined"][key].get(l_alias_name, None)
            r_data = data["combined"][key].get(r_alias_name, None)
            difference = generate_difference(re_ignore, l_data, r_data)
            if difference:
                if key not in differences:
                    differences[key] = {}
                lr_key = 'compare alias %s to %s' % (l_alias_name, r_alias_name)
                if lr_key in differences[key]:
                    raise ValueError("%s in differences[%s]: %s" %
                                     lr_key, key, differences[key])
                differences[key][lr_key] = difference
            l += 1

    return comparison


def _handle_simple_difference(difference, parent_key, re_ignore, left, right):
    """Handle the case where left == right or one of left or right is a
    dict and the other is None.

    Return True if the left and right values were completely handled,
    otherwise return False to indicate additional work must be done by
    generate_difference.

    """
    handled = True
    child_difference = {}

    if type(left) == list and type(right) == list:
        child_difference = []
        if parent_key == 'replicates':
            # Explicitly handle perfherder replicates.
            handled = True
            for i in range(len(left)):
                try:
                    child_difference.append(left[i] - right[i])
                except IndexError:
                    child_difference.append(left[i])
        else:
            try:
                left.sort()
                right.sort()
            except TypeError:
                pass  # XXX items in the list are not sortable.

    if left == right:
        pass
    elif right is None and type(left) == dict:
        right_value = None
        for key in left.keys():
            if re_ignore:
                match = re_ignore.search(key)
                if match:
                    continue
            left_value = left[key]
            if type(left_value) == dict:
                _handle_simple_difference(child_difference, key, re_ignore, left_value, right_value)
            elif type(left_value) == list:
                child_difference[key] = left_value
            else:
                child_difference[key] = "%s != %s" % (left_value, right_value)
    elif left is None and type(right) == dict:
        left_value = None
        for key in right.keys():
            if re_ignore:
                match = re_ignore.search(key)
                if match:
                    continue
            right_value = right[key]
            if type(right_value) == dict:
                _handle_simple_difference(child_difference, key, re_ignore, left_value, right_value)
            elif type(right_value) == list:
                child_difference[key] = ["!%s" % rval for rval in right_value]
            else:
                child_difference[key] = "%s != %s" % (left_value, right_value)
    else:
        handled = False

    if handled:
        if not child_difference:
            if parent_key == 'name':
                # keep name attributes to allow tracking of other
                # differences
                child_difference = left
        if child_difference:
            if parent_key is None:
                difference.update(child_difference)
            elif parent_key in difference:
                difference[parent_key].update(child_difference)
            else:
                difference[parent_key] = child_difference

    return handled


def generate_difference(re_ignore, left, right):
    logger = logging.getLogger()
    difference = {}
    if _handle_simple_difference(difference, None, re_ignore, left, right):
        return difference

    for key in left.keys():
        if re_ignore:
            match = re_ignore.search(key)
            if match:
                continue
        left_value = left[key]
        right_value = right.get(key, None)

        if _handle_simple_difference(difference, key, re_ignore, left_value, right_value):
            pass
        elif isinstance(left_value, Number) and isinstance(right_value, Number):
            if left != right:
                difference[key] = left_value - right_value
        elif type(left_value) != type(right_value):
            difference[key] = "%s != %s" % (left_value, right_value)
        elif type(left_value) == dict:
            key_difference = generate_difference(re_ignore, left_value, right_value)
            if not key_difference:
                if 'name' in left_value:
                    key_difference = left_value
            else:
                # do not include objects of the form {"key": {}} or {"key": []}
                difference_values = list(key_difference.values())
                if len(difference_values) > 1 or len(difference_values) == 1 and difference_values[0]:
                    difference[key] = key_difference
        elif type(left_value) == list:
            if key == 'replicates':
                # Explicitly handle perfherder replicates.
                key_difference = []
                for i in range(len(left_value)):
                    try:
                        key_difference.append(left_value[i] - right_value[i])
                    except IndexError:
                        key_difference.append(left_value[i])
            else:
                try:
                    left_set = set(left_value)
                    right_set = set(right_value)
                    key_difference = list(left_set - right_set)
                    both_set = left_set.intersection(right_set)
                    key_difference.extend(["!%s" % r for r in right_set - both_set])
                except TypeError:
                    # XXX items in the list are not hashable
                    key_difference = []
                    while left_value:
                        left_value_item = left_value.pop(0)
                        # assume the dicts are keyed by name which is the
                        # case for perfherder. First attempt to find the pair
                        # left_value_item['name'] == right_value[rindex]['name']
                        left_value_item_name = left_value_item.get('name', None)
                        # If name is not available, attempt framework...
                        if not left_value_item_name:
                            framework = left_value_item.get('framework', None)
                            if framework:
                                left_value_item_name = framework['name']
                        right_value_item_name = None
                        if left_value_item_name is None:
                            # Note we compare against None here since some perfherder data
                            # can contain an empty string for the name.
                            logger.warning("Could not get left_value_name")
                            key_difference.append(generate_difference(re_ignore, left_value_item, None))
                        else:
                            # find the right_value item which has the same name value
                            rindex = -1
                            for right_value_item in right_value:
                                rindex +=1
                                right_value_item_name = right_value_item.get('name', None)
                                if not right_value_item_name:
                                    framework = right_value_item.get('framework', None)
                                    if framework:
                                        right_value_item_name = framework['name']
                                if left_value_item_name == right_value_item_name:
                                    break
                            if left_value_item_name == right_value_item_name:
                                del right_value[rindex]
                                left_right_difference = generate_difference(re_ignore, left_value_item, right_value_item)
                                if left_right_difference:
                                    key_difference.append(left_right_difference)
                            #else:
                            #    # No name key, just do the list items in order
                            #    try:
                            #        right_value_item = right_value.pop(0)
                            #    except IndexError:
                            #        right_value_item = None
                    while right_value:
                        right_value_item = right_value.pop(0)
                        key_difference.append(generate_difference(re_ignore, None, right_value_item))
            if key_difference:
                difference[key] = key_difference
        else:
            difference[key] = "%s != %s" % (left_value, right_value)

    left_value = None
    for key in right.keys():
        if key in left:
            continue
        if re_ignore:
            match = re_ignore.search(key)
            if match:
                continue
        right_value = right[key]
        _handle_simple_difference(difference, key, re_ignore, left_value, right_value)

    return difference


#@profile
def munge_test_data(test_data):
    #re_test_remainder = re.compile(r'([\d]+ [\d]+ [(][\d]+[)]%|[\d]+ / [\d]+ [(][\d]+%[)]|took [\d]+ms|test completed [(]time: [\d]+ms[)]|\[[\d.]+ s\])$')
    re_test_remainder = re.compile(r'([\d]+ / [\d]+ [(][\d]+%[)]|took [\d]+ms|test completed [(]time: [\d]+ms[)]|\[[\d.]+ s\])$')
    re_ignorable_test_line = re.compile(r'started process GECKO|Main app process: exit 0')
    re_javascript_date = re.compile(r'Date[(][\d]+[)]')
    re_talos_process_1 = re.compile(r'[\d]+: exit ([\d]+)')
    re_talos_process_2 = re.compile(r'started process [\d]+')
    re_dom_media = re.compile(r'\[((?:started|finished).*)t=[\d.]+\]')
    re_mochitest_guid = re.compile(r'should have a guid - "[a-z0-9]+"')
    re_paths = re.compile(r'(file:///builds/worker/workspace/build/|z:\\build\\build\\src\\)')
    re_task = re.compile(r'task_[0-9]+')
    re_localhost = re.compile(r'http://localhost:[\d]+/[\d]+/[\d]+/')

    for test_status in test_data:
        if 'list' not in test_data[test_status]:
            continue

        new_list = []
        for test_line in test_data[test_status]['list']:
            match = re_ignorable_test_line.search(test_line)
            if match:
                continue
            # Remove the trailing stats on the line.
            test_line_parts = test_line.split(' | ')
            match = re_test_remainder.search(test_line_parts[-1])
            if match:
                test_line = ' | '.join(test_line_parts[:-1])

            # munge the test line
            test_line = re_paths.sub('', test_line)
            test_line = re_task.sub('task', test_line)
            test_line = re_localhost.sub('http://localhost:9999/9999/9/', test_line) # reftest
            test_line = 'Date(...)'.join(re_javascript_date.split(test_line)) # javascript tests.
            test_line = 'started process 9999'.join(re_talos_process_2.split(test_line)) # Talos
            match = re_talos_process_1.search(test_line)
            if match:
                test_line = test_line.replace(match.group(0), '9999: exit %s' % match.group(1))
            match = re_dom_media.search(test_line)
            if match:
                test_line = re.sub('t=[\d.]+', 't=...', test_line)
            match = re_mochitest_guid.search(test_line)
            if match:
                test_line = re_mochitest_guid.sub('should have a guid - "0123456789ab"', test_line)
            new_list.append(test_line)
        test_data[test_status]['list'] = new_list

def main():
    log_level_parser = log_level_args.get_parser()

    parser = argparse.ArgumentParser(
        description="""Combine analyzed Test Log json files.
""",
        formatter_class=ArgumentFormatter,
        epilog="""You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.""",
        parents=[log_level_parser],
        fromfile_prefix_chars='@'
        )

    parser.add_argument('--file',
                        dest='files',
                        action='append')

    parser.add_argument('--alias',
                        dest='aliases',
                        action='append')

    parser.add_argument('--differences',
                        action='store_true',
                        default=False,
                        help="Output only differences in data.")

    parser.add_argument('--ignore',
                        default=None,
                        help="Ignore keys matching regular expression when calculating differences.")

    parser.add_argument('--munge-test-data',
                        action='store_true',
                        default=False,
                        help="Modify TEST- lines in output to improve comparibility.")

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()

    combined_data = {
        "aliases": {},
        "combined": {}
    }

    alias_list = []
    for aliasmap in args.aliases:
        (key, alias) = aliasmap.split(':')
        alias_list.append(alias)
        combined_data["aliases"][key] = alias

    if args.ignore:
        re_ignore = re.compile(args.ignore)
    else:
        re_ignore = None

    for input_file_path in args.files:
        with open(input_file_path) as input_file:
            input_json = json.loads(input_file.read())
            for key in input_json.keys():
                data = input_json[key]
                alias_key = combined_data["aliases"][key]

                sub_keys = data.keys()

                for sub_key in sub_keys:
                    if args.munge_test_data and 'test_data' in data[sub_key]:
                        munge_test_data(data[sub_key]['test_data'])

                    if sub_key not in combined_data["combined"]:
                        combined_data["combined"][sub_key] = {}
                    combined_data["combined"][sub_key][alias_key] = data[sub_key]

    if not args.differences:
        output_data = combined_data
    else:
        output_data = compare_aliases(re_ignore, alias_list, combined_data)

    print("%s" % json.dumps(output_data, indent=2, sort_keys=True))


main()
