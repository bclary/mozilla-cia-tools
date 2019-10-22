#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import json
import logging

from statistics import mean, stdev

from scipy import stats

from common_args import ArgumentFormatter, log_level_args


logger = None


def load_json_data(filepath):
    with open(filepath) as f:
        data = json.load(f)
    return data


def extract_aliases(data):
    aliases = []

    for revision in data['aliases']:
        alias = data['aliases'][revision]
        aliases.append(alias)
    aliases.sort()
    return aliases


def extract_measurements(data):

    measurements = {}

    for job_type_name in data['combined']:

        measurements[job_type_name] = {}

        for alias in data['combined'][job_type_name]:

            measurements[job_type_name][alias] = {}

            taskcluster_runtimes = data['combined'][job_type_name][alias].get("taskcluster_runtime", [])
            if taskcluster_runtimes:
                none_list = [None for i in taskcluster_runtimes]
                measurements[job_type_name][alias]["taskcluster_runtimes"] = dict(
                    values=taskcluster_runtimes,
                    extraOptions=none_list,
                    alertChangeTypes=none_list,
                    alertThresholds=none_list,
                    alerts=none_list,
                )

            if "perfherder_data" in data['combined'][job_type_name][alias]:

                for framework in data['combined'][job_type_name][alias]["perfherder_data"]:

                    try:
                        framework_name = framework["framework"]["name"]
                        suites = framework["suites"]
                    except KeyError as e:
                        logger.warning("perfherder_data error: %s(%s) for job_type_name %s alias %s",
                                       e.__class__.__name__, e, job_type_name, alias)
                        continue

                    for suite in suites:
                        suite_name = suite.get("name", None)

                        value = suite.get("value", None)

                        if value is not None:
                            measurement_key = '%s %s' % (framework_name, suite_name)
                            if measurement_key not in measurements[job_type_name][alias]:
                                measurements[job_type_name][alias][measurement_key] = dict(
                                    values=[],
                                    extraOptions=[],
                                    alertChangeTypes=[],
                                    alertThresholds=[],
                                    alerts=[],
                                )
                            measurements[job_type_name][alias][measurement_key]['values'].append(value)

                            # These may not be needed, but collect them for now anyway.
                            extraOptions = ' '.join(suite.get("extraOptions", []))
                            alertChangeType = suite.get("alertChangeType", None)
                            alertThreshold = suite.get("alertThreshold", None)
                            alert = 1 if value and alertThreshold and value > alertThreshold else 0

                            measurements[job_type_name][alias][measurement_key]['extraOptions'].append(extraOptions)
                            measurements[job_type_name][alias][measurement_key]['alertChangeTypes'].append(alertChangeType)
                            measurements[job_type_name][alias][measurement_key]['alertThresholds'].append(alertThreshold)
                            measurements[job_type_name][alias][measurement_key]['alerts'].append(alert)

                        subtests = suite.get("subtests", [])
                        for subtest in subtests:
                            subtest_name = subtest.get("name", None)
                            value = subtest.get("value", None)
                            measurement_key = '%s %s %s' % (framework_name, suite_name, subtest_name)
                            if measurement_key not in measurements[job_type_name][alias]:
                                measurements[job_type_name][alias][measurement_key] = dict(
                                    values=[],
                                    extraOptions=[],
                                    alertChangeTypes=[],
                                    alertThresholds=[],
                                    alerts=[],
                                )
                            measurements[job_type_name][alias][measurement_key]['values'].append(value)

                            # These may not be needed, but collect them for now anyway.
                            extraOptions = ' '.join(suite.get("extraOptions", []))
                            alertChangeType = suite.get("alertChangeType", None)
                            alertThreshold = suite.get("alertThreshold", None)
                            alert = 1 if value and alertThreshold and value > alertThreshold else 0

                            measurements[job_type_name][alias][measurement_key]['extraOptions'].append(extraOptions)
                            measurements[job_type_name][alias][measurement_key]['alertChangeTypes'].append(alertChangeType)
                            measurements[job_type_name][alias][measurement_key]['alertThresholds'].append(alertThreshold)
                            measurements[job_type_name][alias][measurement_key]['alerts'].append(alert)
    return measurements


def generate_report(aliases, measurements):
    line = "job_type_name,"

    for alias in aliases:
        line += ("{alias} measurement,"
                 "{alias} mean,"
                 "{alias} stdev,"
                 "{alias} count,".format(alias=alias))
    line += 'ttest_ind_from_stats statistic, ttest_ind_from_stats pvalue'

    print(line)

    for job_type_name in measurements:

        if set(aliases) != set(measurements[job_type_name].keys()):
            # Only report on job_type_names which have measurements
            # from both aliases.
            continue

        measurement_names = set()
        for alias in aliases:
            measurement_names.update(set(measurements[job_type_name][alias].keys()))

        for measurement_name in sorted(measurement_names):

            line = job_type_name + ','

            # save the values lists for each alias for use in calculating the t-test
            alias_values = {}
            alias_means = {}
            alias_counts = {}
            alias_stdevs = {}

            for alias in aliases:
                if measurement_name not in measurements[job_type_name][alias]:
                    alias_values[alias] = []
                    alias_means[alias] = 0
                    alias_counts[alias] = 0
                    alias_stdevs[alias] = 0
                    count_values = None
                    mean_values = None
                    stdev_values = None
                else:
                    alias_values[alias] = measurements[job_type_name][alias][measurement_name]['values']

                    count_values = len(measurements[job_type_name][alias][measurement_name]['values'])
                    if count_values == 0:
                        continue

                    if count_values == 1:
                        mean_values = measurements[job_type_name][alias][measurement_name]['values'][0]
                        stdev_values = 0
                    else:
                        mean_values = mean(measurements[job_type_name][alias][measurement_name]['values'])
                        stdev_values = stdev(measurements[job_type_name][alias][measurement_name]['values'])

                    alias_means[alias] = mean_values
                    alias_counts[alias] = count_values
                    alias_stdevs[alias] = stdev_values

                line += "%s,%s,%s,%s," % (measurement_name,
                                          mean_values,
                                          stdev_values,
                                          count_values)
            #ttest = stats.ttest_ind(alias_values[aliases[0]], alias_values[aliases[1]])
            alias0 = aliases[0]
            alias1 = aliases[1]
            try:
                ttest = stats.ttest_ind_from_stats(alias_means[alias0], alias_stdevs[alias0], alias_counts[alias0],
                                                   alias_means[alias1], alias_stdevs[alias1], alias_counts[alias1],
                                                   equal_var=False)
                statistic = ttest.statistic
                pvalue = ttest.pvalue
            except ZeroDivisionError:
                statistic = None
                pvalue = None
            line += "%s, %s" % (statistic, pvalue)
            print(line)


def main():
    global logger

    log_level_parser = log_level_args.get_parser()

    parser = argparse.ArgumentParser(
        description="""Analyze Log Summary.

Consumes the output of combine_log_summaries.py to produce either a
summary report in csv format comparing the different summaries in the
combination.

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

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    logger = logging.getLogger()

    data = load_json_data(args.file)
    measurements = extract_measurements(data)
    aliases = extract_aliases(data)
    generate_report(aliases, measurements)


main()
