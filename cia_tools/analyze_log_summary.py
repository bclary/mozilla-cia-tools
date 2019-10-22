#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging

from statistics import mean, stdev

from common_args import ArgumentFormatter, log_level_args


logger = None


def load_json_data(filepath):
    with open(filepath) as f:
        data = json.load(f)
    return data


def extract_measurements(data):

    measurements = {}

    for revision in data:

        measurements[revision] = {}

        for job_type_name in data[revision]:

            measurements[revision][job_type_name] = {}

            taskcluster_runtimes = data[revision][job_type_name].get("taskcluster_runtime", [])
            if taskcluster_runtimes:
                none_list = [None for i in taskcluster_runtimes]
                measurements[revision][job_type_name]["taskcluster_runtimes"] = dict(
                    values=taskcluster_runtimes,
                    extraOptions=none_list,
                    alertChangeTypes=none_list,
                    alertThresholds=none_list,
                    alerts=none_list,
                )

            if "perfherder_data" in data[revision][job_type_name]:

                for framework in data[revision][job_type_name]["perfherder_data"]:

                    try:
                        framework_name = framework["framework"]["name"]
                        suites = framework["suites"]
                    except KeyError as e:
                        logger.warning("perfherder_data error: %s(%s) for revision %s, job_type_name %s",
                                       e.__class__.__name__, e, revision, job_type_name)
                        continue

                    for suite in suites:
                        suite_name = suite.get("name", None)

                        value = suite.get("value", None)

                        if value is not None:
                            measurement_key = '%s %s' % (framework_name, suite_name)
                            if measurement_key not in measurements[revision][job_type_name]:
                                measurements[revision][job_type_name][measurement_key] = dict(
                                    values=[],
                                    extraOptions=[],
                                    alertChangeTypes=[],
                                    alertThresholds=[],
                                    alerts=[],
                                )
                            measurements[revision][job_type_name][measurement_key]['values'].append(value)

                            # These may not be needed, but collect them for now anyway.
                            extraOptions = ' '.join(suite.get("extraOptions", []))
                            alertChangeType = suite.get("alertChangeType", None)
                            alertThreshold = suite.get("alertThreshold", None)
                            alert = 1 if value and alertThreshold and value > alertThreshold else 0

                            measurements[revision][job_type_name][measurement_key]['extraOptions'].append(extraOptions)
                            measurements[revision][job_type_name][measurement_key]['alertChangeTypes'].append(alertChangeType)
                            measurements[revision][job_type_name][measurement_key]['alertThresholds'].append(alertThreshold)
                            measurements[revision][job_type_name][measurement_key]['alerts'].append(alert)

                        subtests = suite.get("subtests", [])
                        for subtest in subtests:
                            subtest_name = subtest.get("name", None)
                            value = subtest.get("value", None)
                            measurement_key = '%s %s %s' % (framework_name, suite_name, subtest_name)
                            if measurement_key not in measurements[revision][job_type_name]:
                                measurements[revision][job_type_name][measurement_key] = dict(
                                    values=[],
                                    extraOptions=[],
                                    alertChangeTypes=[],
                                    alertThresholds=[],
                                    alerts=[],
                                )
                            measurements[revision][job_type_name][measurement_key]['values'].append(value)

                            # These may not be needed, but collect them for now anyway.
                            extraOptions = ' '.join(suite.get("extraOptions", []))
                            alertChangeType = suite.get("alertChangeType", None)
                            alertThreshold = suite.get("alertThreshold", None)
                            alert = 1 if value and alertThreshold and value > alertThreshold else 0

                            measurements[revision][job_type_name][measurement_key]['extraOptions'].append(extraOptions)
                            measurements[revision][job_type_name][measurement_key]['alertChangeTypes'].append(alertChangeType)
                            measurements[revision][job_type_name][measurement_key]['alertThresholds'].append(alertThreshold)
                            measurements[revision][job_type_name][measurement_key]['alerts'].append(alert)
    return measurements


def generate_detailed_report(measurements):
    print("revision,job_type_name,measurement,value,"
          "extraOptions,alertChangeType,alertThreshold,alert")

    for revision in measurements:
        for job_type_name in measurements[revision]:

            for measurement_name in measurements[revision][job_type_name]:

                for i in range(len(measurements[revision][job_type_name][measurement_name]['values'])):
                    value = measurements[revision][job_type_name][measurement_name]['values'][i]
                    extraOptions = measurements[revision][job_type_name][measurement_name]['extraOptions'][i]
                    alertChangeType = measurements[revision][job_type_name][measurement_name]['alertChangeTypes'][i]
                    alertThreshold = measurements[revision][job_type_name][measurement_name]['alertThresholds'][i]
                    alert = measurements[revision][job_type_name][measurement_name]['alerts'][i]

                    print("%s,%s,%s,%s,%s,%s,%s,%s" % (revision,
                                                       job_type_name,
                                                       measurement_name,
                                                       value,
                                                       extraOptions,
                                                       alertChangeType,
                                                       alertThreshold,
                                                       alert))


def generate_summary_report(measurements):
    print("revision,job_type_name,measurement,mean,stdev,count")

    for revision in measurements:
        for job_type_name in measurements[revision]:

            for measurement_name in measurements[revision][job_type_name]:

                count_values = len(measurements[revision][job_type_name][measurement_name]['values'])
                if count_values == 0:
                    continue

                if count_values == 1:
                    mean_values = measurements[revision][job_type_name][measurement_name]['values'][0]
                    stdev_values = 0
                else:
                    mean_values = mean(measurements[revision][job_type_name][measurement_name]['values'])
                    stdev_values = stdev(measurements[revision][job_type_name][measurement_name]['values'])

                print("%s,%s,%s,%s,%s,%s" % (revision,
                                             job_type_name,
                                             measurement_name,
                                             mean_values,
                                             stdev_values,
                                             count_values))


def main():
    global logger

    log_level_parser = log_level_args.get_parser()

    parser = argparse.ArgumentParser(
        description="""Analyze Log Summary.

Consumes the output of analyze_log_summary.py to produce either a detailed report
or a summary report in csv format.

The detailed report contains the taskcluster_runtime and every field contained in
the PERFHERDER_DATA from the original log file.

The summary report contains the average and standard deviations of the PERFHERDER_DATA.
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
                        default=None,
                        required=True,
                        help='Path to summarized log file to analyze.')
    parser.add_argument('--report',
                        default='detailed',
                        choices=['detailed', 'summary'],
                        help='Choose the type of report to be generated. "detailed" will output '
                        'each measurement while "summary" will calculate the mean and sample '
                        'standard deviation of the measurements.')

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()

    data = load_json_data(args.file)
    measurements = extract_measurements(data)
    if args.report == 'detailed':
        generate_detailed_report(measurements)
    else:
        generate_summary_report(measurements)


main()
