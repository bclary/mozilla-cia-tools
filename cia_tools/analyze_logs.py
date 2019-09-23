#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
docstring
"""

import argparse
import glob
import json
import logging
import os
import re

from numbers import Number

from common_args import ArgumentFormatter, log_level_args


def combine_dict(left, right, **kwargs):
    """Modeled on dict.update([E, ], **F)
    Help on method_descriptor:

    update(...)
        D.update([E, ]**F) -> None.  Update D from dict/iterable E and F.
        If E present and has a .keys() method, does:     for k in E: D[k] = E[k]
        If E present and lacks .keys() method, does:     for (k, v) in E: D[k] = v
        In either case, left is followed by: for k in F: D[k] = F[k]
    """
    if right:
        if hasattr(right, 'keys'):
            for k in right:
                right_type = type(right[k])
                if k in left:
                    if right_type == str:
                        left[k] += ';' + right[k]
                    elif right_type == dict:
                        combine_dict(left[k], right[k])
                    else:
                        left[k] += right[k]
                else:
                    left[k] = right[k]
        else:
            for (k, v) in right:
                right_type = type(v)
                if k in left:
                    if right_type == str:
                        left[k] += ';' + v
                    elif right_type == dict:
                        combine_dict(left[k], v)
                    else:
                        left[k] += v
                else:
                    left[k] = v
    if kwargs:
        for k in kwargs:
            right_type = type(kwargs[k])
            if k in left:
                if right_type == str:
                    left[k] += ';'
                left[k] += kwargs[k]
            else:
                left[k] = kwargs[k]

    return left


def analyze_logs(args):
    logger = logging.getLogger()

    re_taskcluster_wall_time = re.compile(r"\[taskcluster.*Wall Time: (?:([.\d]+)h)?(?:([.\d]+)m)?(?:([.\d]+)s)")
    re_taskcluster_taskId = re.compile(r"\[taskcluster.*Task ID: (.*)")
    re_taskcluster_completed = re.compile(r"\[taskcluster.*(Unsuccessful|Successful) task run with exit code: (\d+) completed in ([0-9.]+) seconds")
    re_revision_env = re.compile(r"(MOZ_SOURCE_CHANGESET|GECKO_HEAD_REV)(=|': ')([\w-]+)")
    re_revision_checkout = re.compile(r"'--revision', '([\w-]+)'")
    re_tinderbox_summary = re.compile(r"TinderboxPrint: ([^<]+)<br/>(.*)")
    re_perfherder_data = re.compile(r"PERFHERDER_DATA: (.*)")
    #
    # webpagetest
    re_test_status = re.compile(r"(TEST-[A-Z-]+|PROCESS-CRASH) \| (.*)")

    # mochitest tinderbox prints do not agree with the number of TEST- lines.
    # mochitest tinderbox print pass = TEST-OK + TEST-SKIP
    # mochitest activedata pass = TEST-OK + TEST-SKIP
    # mochitest-browser-chrome          INFO\b-\b(.*)
    # INFO - Passed:  40
    # INFO - Failed:  0
    # INFO - Todo:    0
    # mochitest-browser-chrome totals   INFO\b-\b\b\t(.*)
    # INFO -      Passed: 6673
    # INFO -      Failed: 2
    # INFO -      Todo: 1
    # mochitest
    # INFO -  54 INFO Passed:  2329
    # INFO -  55 INFO Failed:  0
    # INFO -  56 INFO Todo:    2
    # mochitest totals
    # INFO -  1 INFO Passed:  4363
    # INFO -  2 INFO Failed:  0
    # INFO -  3 INFO Todo:    37
    re_mochitest_totals = re.compile(r"INFO - ( \t|\s+[123] INFO )(Passed|Failed|Todo):\s+(\d+)")

    # python source tests
    re_source_test = re.compile(r'========================== (.*) in ([0-9.]+) seconds ===========================$')

    re_unittest_totals = re.compile(r'TinderboxPrint: (geckoview-junit|jittest|cppunittest|cppunittest-cppunittest|gtest|gtest-gtest)<br/>([0-9]+)/(.*)')

    ### test isolation ###
    re_isolation_jobsymbol = re.compile(r'(.*)-(it|id)$')
    ######################

    data = {}
    tinderbox_print_keys = set()
    test_suite_status = {}
    path = os.path.join(os.path.expanduser(args.path), "**", "*" + args.filename)
    filepaths = glob.glob(path, recursive=True)
    # sort the filepaths so we skip files with later runs.
    filepaths.sort()
    nfilepaths = len(filepaths)
    re_runs = re.compile(r'.*/runs/([0-9])/.*')
    regx_value = re.compile(r'[^0-9]*$')
    for i in range(nfilepaths):
        # Note the filepath looks like
        # output directory/revision/job_guid/job_guid_run/path_dir/file_name
        # and it created in treeherder.py job_details. path_dir also contains
        # the run in the form runs/<run>/ so we need to deal with a comparison
        # where the run appears twice.

        if i + 1 < nfilepaths:
            match = re_runs.search(filepaths[i])
            if not match:
                logger.error("file does not have a run encoded in name: %s", filepaths[i])
            else:
                current_run = match.group(1)
                match = re_runs.search(filepaths[i+1])
                if not match:
                    logger.error("file does not have a run encoded in name: %s", filepaths[i+1])
                else:
                    next_run = match.group(1)
                    if (re.split('/[0-9]/', filepaths[i+1]) == re.split('/[0-9]/', filepaths[i])
                        and next_run > current_run):
                        logger.debug("run replaced by later run: %s, %s", filepaths[i], filepaths[i+1])
                        continue
        filepath = filepaths[i]
        logger.debug("%s\nBegin processing %s", "=" * 80, filepath)
        revision = None
        # metadata (test|build)-osplatform,buildtype,testsuite-(e10s)?-chunk,jobsymbol
        metadata = dict(zip(
            ('testplatform', 'buildtype', 'testsuite', 'jobsymbol'),
            os.path.basename(filepath).split(",")[:-1]))

        # Collect test status by test suite for debug output
        # categorizing the detected test status by test suite.
        test_suite = re.sub('(-e10s|-1proc)?(-[0-9]+)?$', '', metadata['testsuite'])
        if test_suite.startswith('awsy'):
            test_suite = 'awsy'
        elif test_suite.startswith('crashtest'):
            test_suite = 'crashtest'
        elif test_suite.startswith('jsreftest'):
            test_suite = 'jsreftest'
        elif test_suite.startswith('mochitest'):
            test_suite = 'mochitest'
        elif test_suite.startswith('reftest'):
            test_suite = 'reftest'
        elif test_suite.startswith('web-platform-tests'):
            test_suite = 'web-platform-tests'
        elif test_suite.startswith('xpcshell'):
            test_suite = 'xpcshell'

        if test_suite not in test_suite_status:
            test_suite_status[test_suite] = set()

        job_type_name = metadata['testplatform'] + '/' + metadata['buildtype'] + '-'
        if not args.dechunk:
            job_type_name += metadata['testsuite']
        else:
            job_type_name += re.sub('(-[0-9]+)?$', '', metadata['testsuite'])
            jobsymbol = metadata['jobsymbol']
            isolation_match = re_isolation_jobsymbol.match(jobsymbol)
            if isolation_match:
                # If we are processing a test isolation job, add the isolation type to the
                # "job_type_name" to distinguish from normal builds.
                (jobsymbol, isolation_type) = isolation_match.groups()
                jobsymbol = re.sub('(-?[0-9]+)?$', '', jobsymbol)
                if jobsymbol:
                    jobsymbol += '-' + isolation_type
                else:
                    jobsymbol = isolation_type
                job_type_name += '/' + jobsymbol

        data_revision = {
            job_type_name: {},
        }

        # cppunit log count of TEST-START == ActiveData pass count
        # crashtest log count TEST-PASS == ActiveData pass count
        # geckoview log count TEST-START == ActiveData pass count
        #                     TEST-PASS, TEST-FAIL not accounted for in ActiveData
        # jsreftest log count TEST-START == ActiveData pass count
        #                     TEST-PASS,...
        # web-platform-tests
        # have json results in the wptreport.json job-detail file.

        with open(filepath) as logfile:
            for line in logfile:
                line = line.strip()

                # Collect taskcluster data
                if line.startswith('[taskcluster'):
                    if "taskcluster" not in data_revision[job_type_name]:
                        data_revision[job_type_name]["taskcluster"] = []
                    taskcluster_message = line
                    data_revision[job_type_name]["taskcluster"].append(taskcluster_message)

                    match = re_taskcluster_wall_time.match(line)
                    if match:
                        (hours, minutes, seconds) = match.groups()
                        if "taskcluster_wall_time" not in data_revision[job_type_name]:
                            data_revision[job_type_name]["taskcluster_walltime"] = 0
                            if hours:
                                data_revision[job_type_name]["taskcluster_walltime"] += 3600*float(hours)
                            if minutes:
                                data_revision[job_type_name]["taskcluster_walltime"] += 60*float(minutes)
                            if seconds:
                                data_revision[job_type_name]["taskcluster_walltime"] += float(seconds)
                    else:
                        match = re_taskcluster_taskId.match(line)
                        if match:
                            taskId = match.groups(1)
                            data_revision[job_type_name]["taskcluster_taskId"] = taskId
                        else:
                            match = re_taskcluster_completed.match(line)
                            if match:
                                (taskcluster_status, taskcluster_exitcode, taskcluster_runtime) = match.groups()
                                data_revision[job_type_name]["taskcluster_status"] = taskcluster_status
                                data_revision[job_type_name]["taskcluster_exitcode"] = taskcluster_exitcode
                                try:
                                    data_revision[job_type_name]["taskcluster_runtime"] = float(taskcluster_runtime)
                                except ValueError:
                                    data_revision[job_type_name]["taskcluster_runtime"] = 0
                    continue

                # Next Collect the revision. It will appear before any tests or the summary.
                if not revision:
                    match = re_revision_env.search(line)
                    if match:
                        revision = match.group(3)
                        logger.debug("found revision %s in %s", revision, line)
                        if not revision in data:
                            data[revision] = {}
                        continue
                    match = re_revision_checkout.search(line)
                    if match:
                        revision = match.group(1)
                        logger.debug("found revision %s in %s", revision, line)
                        if not revision in data:
                            data[revision] = {}
                        continue

                # Check if this is a python source test
                # ===================== 53 passed, 2 skipped in 9.37 seconds =====================
                match = re_source_test.search(line)
                if match:
                    source_test_summary = match.group(1)
                    source_test_parts = source_test_summary.split(', ')
                    if "sourcetest_data" not in data_revision[job_type_name]:
                        data_revision[job_type_name]["sourcetest_data"] = {}
                    for source_test_part in source_test_parts:
                        (count, test_status) = source_test_part.split()
                        if test_status not in data_revision[job_type_name]["sourcetest_data"]:
                            data_revision[job_type_name]["sourcetest_data"][test_status] = 0
                        data_revision[job_type_name]["sourcetest_data"][test_status] += int(count)
                    continue
                # Look for TEST- lines
                match = re_test_status.search(line)
                if match:
                    (test_status, test_remainder) = match.groups()
                    test_suite_status[test_suite].add(test_status)
                    test_line = ' | '.join((test_status, test_remainder))
                    if "test_data" not in data_revision[job_type_name]:
                        data_revision[job_type_name]["test_data"] = {}
                    if test_status not in data_revision[job_type_name]["test_data"]:
                        data_revision[job_type_name]["test_data"][test_status] = {"counts": 0}
                        if args.include_tests:
                            data_revision[job_type_name]["test_data"][test_status]["list"] = []
                    data_revision[job_type_name]["test_data"][test_status]["counts"] += 1
                    if args.include_tests:
                        data_revision[job_type_name]["test_data"][test_status]["list"].append(test_line)
                    continue
                # Look for mochitest pass/fail/todo summaries
                match = re_mochitest_totals.search(line)
                if match:
                    test_status = match.group(2)
                    count = int(match.group(3))
                    if "mochitest_data" not in data_revision[job_type_name]:
                        data_revision[job_type_name]["mochitest_data"] = {}
                    data_revision[job_type_name]["mochitest_data"][test_status] = count
                    continue
                # Look for geckoview_junit , jittest pass/fail summaries
                match = re_unittest_totals.search(line)
                if match:
                    unittest_suite = match.group(1)
                    unittest_pass = int(match.group(2))
                    value = match.group(3)
                    if '<em class=\"testfail\">' in value:
                        value = value.replace('<em class=\"testfail\">', '').replace('</em>', '')
                    value = regx_value.sub('', value)
                    unittest_fail = int(value)
                    if unittest_suite not in data_revision[job_type_name]:
                        # Support multiple geckoview_junit / jittest summary lines per file.
                        data_revision[job_type_name][unittest_suite] = {'passed': 0, 'failed': 0}
                    data_revision[job_type_name][unittest_suite]['passed'] += unittest_pass
                    data_revision[job_type_name][unittest_suite]['failed'] += unittest_fail
                    continue

                # Look for Perfherder
                match = re_perfherder_data.search(line)
                if match:
                    if 'perfherder_data' not in data_revision[job_type_name]:
                        data_revision[job_type_name]["perfherder_data"] = []
                    perfherder_data = match.group(1)
                    #data_revision[job_type_name]["perfherder_data"].update(
                    #    json.loads(perfherder_data))
                    #combine_dict(data_revision[job_type_name]["perfherder_data"],
                    #             json.loads(perfherder_data))
                    data_revision[job_type_name]["perfherder_data"].append(json.loads(perfherder_data))
                # Look for the TinderboxPrint summary line.
                match = re_tinderbox_summary.search(line)
                if not match:
                    continue
                if 'tinderbox_data' not in data_revision[job_type_name]:
                    tinderbox_data = data_revision[job_type_name]["tinderbox_data"] = {}
                key = match.group(1)
                tinderbox_print_keys.add(key)
                value = match.group(2)
                if '<em class=\"testfail\">' in value:
                    value = value.replace('<em class=\"testfail\">', '').replace('</em>', '')
                if ' / ' in key:
                    # Convert key I/O write bytes / time
                    # into two subkeys IO write bytes and IO write time
                    subkeys = key.split(' / ')
                    subkey_prefix = ' '.join(subkeys[0].split(' ')[0:-1])
                    subkeys[0] = subkeys[0].replace(subkey_prefix, '').strip()
                    subvalues = list(map(str.strip, value.split('/')))
                    for i in range(len(subvalues)):
                        subvalues[i] = cast_to_numeric(subvalues[i])
                        tinderbox_data_subkeys = dict(zip(subkeys, subvalues))
                        data_revision[job_type_name]["tinderbox_data"][subkey_prefix] = tinderbox_data_subkeys
                elif len(re.findall('/', value)) == 2:
                    tinderbox_data = dict(zip(['pass', 'fail', 'skip'],
                                              list(map(str.strip, value.split('/')))))
                    if '&nbsp;CRASH' in tinderbox_data["skip"] and 'PROCESS-CRASH' in data_revision[job_type_name]["test_data"]:
                        tinderbox_data["skip"] = tinderbox_data["skip"].replace('&nbsp;CRASH', '')
                    for subkey in tinderbox_data:
                        tinderbox_data[subkey] = cast_to_numeric(tinderbox_data[subkey])
                    #data_revision[job_type_name]["tinderbox_data"].update(tinderbox_data)
                    combine_dict(data_revision[job_type_name]["tinderbox_data"], tinderbox_data)
                elif 'T-FAIL' in value:
                    T_FAIL = tinderbox_data.get('T-FAIL', 0) + 1
                    data_revision[job_type_name]["tinderbox_data"]['T-FAIL'] = T_FAIL
                else:
                    tinderbox_data = {key: cast_to_numeric(value.strip())}
                    #data_revision[job_type_name]["tinderbox_data"].update(tinderbox_data)
                    combine_dict(data_revision[job_type_name]["tinderbox_data"], tinderbox_data)
                logger.debug("match %s, metadata %s, tinderbox_data %s",
                             match.group(0), metadata, tinderbox_data)
        logger.debug("data_revision %s", data_revision)
        if (job_type_name.startswith('test-') and
            'tinderbox_data' not in data_revision[job_type_name]):
            if 'warnings' not in data_revision[job_type_name]:
                data_revision[job_type_name]['warnings'] = []
            warning = "missing tinderbox_data in %s %s" % (job_type_name, filepath)
            data_revision[job_type_name]["warnings"].append(warning)
            logger.warning(warning)
        if revision:
            data[revision] = combine_data_revisions(job_type_name, data[revision], data_revision)
        else:
            if 'warnings' not in data_revision[job_type_name]:
                data_revision[job_type_name]['warnings'] = []
            warning = "missing revision in %s, %s" % (job_type_name, filepath)
            data_revision[job_type_name]["warnings"].append(warning)
            logger.warning(warning)
    logger.debug('tinderbox_print_keys %s', tinderbox_print_keys)
    if logger.getEffectiveLevel() == logging.DEBUG:
        test_suites = list(test_suite_status.keys())
        test_suites.sort()
        for test_suite in test_suites:
            logger.debug("test suite %s had statuses %s",
                         test_suite, list(test_suite_status[test_suite]))

    return data


def cast_to_numeric(value):
    value = value.replace(',', '')
    re_value = re.compile(r'([\d.]+)')
    match = re_value.search(value)
    if match:
        value = match.group(1)
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            pass
    return value


def combine_data_revisions(label, left, right):
    logger = logging.getLogger()
    combination = {}

    if left is None and right is None:
        pass
    elif right is None or right == {}:
        combination = left
    elif left is None or left == {}:
        combination = right
    else:
        def is_tuple_or_list(v):
            return type(v) == list or type(v) == tuple

        for key in left.keys():
            left_value = left[key]
            right_value = right.get(key, None)
            if type(left_value) == dict or type(right_value) == dict:
                key_combination = combine_data_revisions(label, left_value, right_value)
                if key_combination and list(key_combination.values()) != [{}]:
                    combination[key] = combine_data_revisions(label, left_value, right_value)
            elif isinstance(left_value, Number) and isinstance(right_value, Number):
                combination[key] = left_value + right_value
            elif isinstance(left_value, Number):
                logger.debug("Discarding non numeric value %s: %s: %s", key, label, right_value)
                combination[key] = left_value
            elif isinstance(right_value, Number):
                logger.debug("Discarding non numeric value %s: %s: %s", key, label, left_value)
                combination[key] = right_value
            elif is_tuple_or_list(left_value) and is_tuple_or_list(right_value):
                if len(left_value) == 0 or len(right_value) == 0:
                    combination[key] = list(left_value) + list(right_value)
                else:
                    left_value_types = set( [ type(i) for i in left_value ] )
                    right_value_types = set( [ type(i) for i in right_value ] )
                    if left_value_types == right_value_types:
                        if left_value_types == set([type(dict)]):
                            combination[key] = []
                            ###
                            while left_value:
                                left_value_item = left_value.pop(0)
                                # See combine_logs.py:generate_difference for similar issue.
                                # XXX general solution.
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
                                if not left_value_item_name:
                                    combination[key].append(left_value_item_name)
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
                                        left_right_combined = combine_data_revisions(key, left_value_item, right_value_item)
                                        if left_right_combined:
                                            combination[key].append(left_right_combined)
                            while right_value:
                                right_value_item = right_value.pop(0)
                                combination[key].append(right_value_item)
                            ###
                        else:
                            combination[key] = list(left_value) + list(right_value)
                    else:
                        logger.warning("Mismatched lists items types: %s, %s", left_value_types, right_value_types)
                        combination[key] = list(left_value) + list(right_value)
            elif is_tuple_or_list(left_value):
                logger.debug("Discarding non list value %s: %s: %s", key, label, right_value)
                combination[key] = list(left_value)
            elif is_tuple_or_list(right_value):
                logger.debug("Discarding non list value %s: %s: %s", key, label, left_value)
                combination[key] = list(right_value)
            elif type(left_value) != type(right_value):
                combination[key] = "%s, %s" % (left_value, right_value)
            elif left_value != right_value:
                combination[key] = "%s, %s" % (left_value, right_value)
            else:
                combination[key] = left_value

        for key in right.keys():
            if key in left:
                continue
            combination[key] = right[key]

    return combination


def main():
    """main"""

    log_level_parser = log_level_args.get_parser()

    parser = argparse.ArgumentParser(
        description="""Analyze downloaded Test Log files producing json summaries..

""",
        formatter_class=ArgumentFormatter,
        epilog="""

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.

""",
        parents=[log_level_parser],
        fromfile_prefix_chars='@'
    )

    parser.add_argument("--path",
                        required=True,
                        help="Log.")

    parser.add_argument("--filename",
                        default="live_backing.log",
                        help="Base log filename suffix.")

    parser.add_argument("--include-tests",
                        action='store_true',
                        default=False,
                        help="Include TEST- lines.")

    parser.add_argument("--dechunk",
                        action='store_true',
                        default=False,
                        help="Combine chunks.")

    parser.add_argument(
        "--raw",
        action='store_true',
        default=False,
        help="Do not reformat/indent json.")

    parser.set_defaults(func=analyze_logs)

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()
    logger.debug("main %s", args)

    data = args.func(args)

    if args.raw:
        print(data)
    else:
        print(json.dumps(data, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
