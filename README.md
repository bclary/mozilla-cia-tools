# mozilla-cia-tools

## Installation

We require python3 to get new library features and things and to cut ties with 2.7
since we are going to have to do it anyway EOY.

``` shell
pip3 install --user virtualenv
python3 -m virtualenv venv
. venv/bin/activate
pip install -r requirements.txt
```

## Tools

### activedata_compare_tests.py

``` shell
$ ./activedata_compare_tests.py --help
usage: activedata_compare_tests.py [-h]
                                   [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                   [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                   [--author AUTHOR]
                                   [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                                   [--treeherder TREEHERDER]
                                   [--activedata ACTIVEDATA]
                                   [--combine-chunks]
                                   [--output-push-differences-only]

ActiveData compare-tests

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --activedata ACTIVEDATA
                        ActiveData url. (default: https://activedata.allizom.org/query)
  --combine-chunks      Combine chunks (default: False)
  --output-push-differences-only
                        When loading multiple pushes, only output keys which have different
                                values for sub_keys across the
                                pushes. (default: False)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```

### activedata_query.py

``` shell
$ ./activedata_query.py --help
usage: activedata_query.py [-h]
                           [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                           [--activedata ACTIVEDATA] --file FILE [--raw]

Query ActiveData tests and write the result as json to stdout.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --activedata ACTIVEDATA
                        ActiveData url. (default: https://activedata.allizom.org/query)
  --file FILE           File containing ActiveData query as json.. (default: None)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```

writes results of ActiveData query in json format to stdout.

### activedata_query_tests.py

``` shell
$ ./activedata_query_tests.py --help
usage: activedata_query_tests.py [-h]
                                 [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                 [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                 [--author AUTHOR]
                                 [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                                 [--treeherder TREEHERDER]
                                 [--activedata ACTIVEDATA]
                                 [--include-passing-tests] [--raw]

ActiveData query tests.

Query ActiveData tests and write the result as json to stdout.

Errors will be written to stderr.

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --activedata ACTIVEDATA
                        ActiveData url. (default: https://activedata.allizom.org/query)
  --include-passing-tests
                        Query tests against ActiveData. (default: False)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```

### analyze_logs.py

``` shell
$ ./analyze_logs.py --help
usage: analyze_logs.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                       --path PATH [--filename FILENAME] [--include-tests]
                       [--dechunk] [--raw]

Analyze downloaded Test Log files producing json summaries..

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --path PATH           Log. (default: None)
  --filename FILENAME   Base log filename suffix. (default: live_backing.log)
  --include-tests       Include TEST- lines. (default: False)
  --dechunk             Combine chunks. (default: False)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### combine_logs_json.py

``` shell
$ ./combine_logs_json.py --help
usage: combine_logs_json.py [-h] [--file FILES] [--alias ALIASES]
                            [--differences] [--ignore IGNORE]
                            [--munge-test-data]

Combine analyzed Test Log json files.

optional arguments:
  -h, --help         show this help message and exit
  --file FILES
  --alias ALIASES
  --differences      Output only differences in data. (default: False)
  --ignore IGNORE    Ignore keys matching regular expression when calculating differences. (default: None)
  --munge-test-data  Modify TEST- lines in output to improve comparibility. (default: False)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```

### download_treeherder_jobdetails.py

``` shell
usage: download_treeherder_jobdetails.py [-h]
                                         [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                         [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                         [--author AUTHOR]
                                         [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                                         [--add-bugzilla-suggestions]
                                         [--build-platform BUILD_PLATFORM]
                                         [--job-group-name JOB_GROUP_NAME]
                                         [--job-group-symbol JOB_GROUP_SYMBOL]
                                         [--job-type-name JOB_TYPE_NAME]
                                         [--job-type-symbol JOB_TYPE_SYMBOL]
                                         [--machine-name MACHINE_NAME]
                                         [--platform PLATFORM]
                                         [--platform-option PLATFORM_OPTION]
                                         [--result RESULT] [--state STATE]
                                         [--tier TIER]
                                         [--treeherder TREEHERDER]
                                         --download-job-details
                                         DOWNLOAD_JOB_DETAILS
                                         [--output OUTPUT] [--alias ALIAS]

Download Job Details files from Treeherder/Taskcluster.

--download-job-details specifies a regular expression which will be matched
against the base file name of the url to the file to select the files to be
downloaded. This is not a shell glob pattern, but a full regular expression.
Files will be saved to the output directory using the path to the job detail
and a file name encoded with meta data as:

output/revision/job_guid/job_guid_run/path/platform,buildtype,job_name,job_type_symbol,filename

if --alias is specified, a soft link will be created from
output/revision to output/alias.

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

Job Related Arguments

Job related pattern objects are used to select the jobs which will be
returned. All specified patterns must match to return a job.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --add-bugzilla-suggestions
                        Add bugzilla suggestions to job objects. (default: False)
  --build-platform BUILD_PLATFORM
                        Match job build platform regular expression. (default: None)
  --job-group-name JOB_GROUP_NAME
                        Match job group name regular expression. (default: None)
  --job-group-symbol JOB_GROUP_SYMBOL
                        Match job group symbol regular expression (default: None)
  --job-type-name JOB_TYPE_NAME
                        Match job type name regular expression. (default: None)
  --job-type-symbol JOB_TYPE_SYMBOL
                        Match job type symbol regular expression. (default: None)
  --machine-name MACHINE_NAME
                        Match job machine name regular expression. (default: None)
  --platform PLATFORM   Match job platform regular expression. (default: None)
  --platform-option PLATFORM_OPTION
                        Match job platform option regular expression: opt, debug, pgo,... (default: None)
  --result RESULT       Match job result regular expression: unknown, success, testfailed, .... (default: None)
  --state STATE         Match job state regular expression: pending, running, completed. (default: None)
  --tier TIER           Match job tier regular expression. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --download-job-details DOWNLOAD_JOB_DETAILS
                        Regular expression matching Job details url basenames to be
                                downloaded.  Example:live_backing.log|logcat.*.log. Default
                                None. (default: None)
  --output OUTPUT       Directory where to save downloaded job details. (default: output)
  --alias ALIAS         Alias (soft link) to revision subdirectory where the downloaded job details were saved. (default: None)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### get_pushes_jobs_job_details_json.py

``` shell
./get_pushes_jobs_job_details_json.py --help

usage: get_pushes_jobs_job_details_json.py [-h]
                                           [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                           [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                           [--author AUTHOR]
                                           [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                                           [--add-bugzilla-suggestions]
                                           [--build-platform BUILD_PLATFORM]
                                           [--job-group-name JOB_GROUP_NAME]
                                           [--job-group-symbol JOB_GROUP_SYMBOL]
                                           [--job-type-name JOB_TYPE_NAME]
                                           [--job-type-symbol JOB_TYPE_SYMBOL]
                                           [--machine-name MACHINE_NAME]
                                           [--platform PLATFORM]
                                           [--platform-option PLATFORM_OPTION]
                                           [--result RESULT] [--state STATE]
                                           [--tier TIER]
                                           [--treeherder TREEHERDER]
                                           [--add-resource-usage] [--raw]

Downloads pushes, jobs and job details data from Treeherder, writing results as
nested json to stdout.

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

Job Related Arguments

Job related pattern objects are used to select the jobs which will be
returned. All specified patterns must match to return a job.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --add-bugzilla-suggestions
                        Add bugzilla suggestions to job objects. (default: False)
  --build-platform BUILD_PLATFORM
                        Match job build platform regular expression. (default: None)
  --job-group-name JOB_GROUP_NAME
                        Match job group name regular expression. (default: None)
  --job-group-symbol JOB_GROUP_SYMBOL
                        Match job group symbol regular expression (default: None)
  --job-type-name JOB_TYPE_NAME
                        Match job type name regular expression. (default: None)
  --job-type-symbol JOB_TYPE_SYMBOL
                        Match job type symbol regular expression. (default: None)
  --machine-name MACHINE_NAME
                        Match job machine name regular expression. (default: None)
  --platform PLATFORM   Match job platform regular expression. (default: None)
  --platform-option PLATFORM_OPTION
                        Match job platform option regular expression: opt, debug, pgo,... (default: None)
  --result RESULT       Match job result regular expression: unknown, success, testfailed, .... (default: None)
  --state STATE         Match job state regular expression: pending, running, completed. (default: None)
  --tier TIER           Match job tier regular expression. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --add-resource-usage  Download resource-usage.json job detail and add to job object. (default: False)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### get_pushes_json.py

``` shell
./get_pushes_json.py --help

usage: get_pushes_json.py [-h]
                          [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                          [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                          [--author AUTHOR]
                          [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                          [--treeherder TREEHERDER] [--raw]

Downloads pushes data from Treeherder, writing results as
json to stdout.

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### get_pushes_jobs_json.py

``` shell
./get_pushes_jobs_json.py --help

usage: get_pushes_jobs_json.py [-h]
                               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                               [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                               [--author AUTHOR]
                               [--date-range DATE_RANGE | --revision REVISION | --commit-revision COMMIT_REVISION | --revision-url REVISION_URL | --revision-range REVISION_RANGE]
                               [--add-bugzilla-suggestions]
                               [--build-platform BUILD_PLATFORM]
                               [--job-group-name JOB_GROUP_NAME]
                               [--job-group-symbol JOB_GROUP_SYMBOL]
                               [--job-type-name JOB_TYPE_NAME]
                               [--job-type-symbol JOB_TYPE_SYMBOL]
                               [--machine-name MACHINE_NAME]
                               [--platform PLATFORM]
                               [--platform-option PLATFORM_OPTION]
                               [--result RESULT] [--state STATE] [--tier TIER]
                               [--treeherder TREEHERDER] [--raw]

Downloads pushes and jobs data from Treeherder, writing results as nested json to
stdout.

Push Related Arguments

If a push isn't selected, the most recent push will be returned.

Job Related Arguments

Job related pattern objects are used to select the jobs which will be
returned. All specified patterns must match to return a job.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --commit-revision COMMIT_REVISION
                        Either Push Revision or any commit referenced in the push. (default: None)
  --revision-url REVISION_URL
                        Url to push revision which can be used in place of --repo and --revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange-tochange. (default: None)
  --add-bugzilla-suggestions
                        Add bugzilla suggestions to job objects. (default: False)
  --build-platform BUILD_PLATFORM
                        Match job build platform regular expression. (default: None)
  --job-group-name JOB_GROUP_NAME
                        Match job group name regular expression. (default: None)
  --job-group-symbol JOB_GROUP_SYMBOL
                        Match job group symbol regular expression (default: None)
  --job-type-name JOB_TYPE_NAME
                        Match job type name regular expression. (default: None)
  --job-type-symbol JOB_TYPE_SYMBOL
                        Match job type symbol regular expression. (default: None)
  --machine-name MACHINE_NAME
                        Match job machine name regular expression. (default: None)
  --platform PLATFORM   Match job platform regular expression. (default: None)
  --platform-option PLATFORM_OPTION
                        Match job platform option regular expression: opt, debug, pgo,... (default: None)
  --result RESULT       Match job result regular expression: unknown, success, testfailed, .... (default: None)
  --state STATE         Match job state regular expression: pending, running, completed. (default: None)
  --tier TIER           Match job tier regular expression. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --raw                 Do not reformat/indent json. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### summarize_isolation_pushes_jobs_json.py

Summarize job json for Test Isolation

``` shell
$ ./summarize_isolation_pushes_jobs_json.py --help
usage: summarize_isolation_pushes_jobs_json.py [-h]
                                               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                               [--file FILE] [--raw] [--csv]
                                               [--include-failures]

Reads json produced by get_pushes_jobs_json.py either from stdin
or from a file and produces a summary of runtimes and test failures, writing
results as either csv text or json to stdout. By default, output is written
as formatted json.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --file FILE           Load the file produced previously by get_pushes_jobs_json. Leave empty or use - to specify stdin. (default: None)
  --raw                 Do not reformat/indent json. (default: False)
  --csv                 Output in csv format. Not compatible with --include-failures. (default: False)
  --include-failures    Include individual failures in output. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

#### Example

``` shell
$ ./get_pushes_jobs_json.py \
  --revision-url 'https://hg.mozilla.org/integration/autoland/rev/948869e38bce72ae635e1ab629ab42ce0af444cc' \
  --job-type-name test-windows10-64/debug-xpcshell-e10s-2 --add-bugzilla-suggestions | ./summarize_isolation_pushes_jobs_json.py
```

``` shell
{
  "test-windows10-64/debug-xpcshell-e10s-2": {
    "original": {
      "run_time": 8178,
      "jobs_failed": 1,
      "jobs_total": 5,
      "tests_failed": 5
    },
    "repeated": {
      "run_time": 163725,
      "jobs_failed": 6,
      "jobs_total": 100,
      "tests_failed": 25,
      "reproduced": 15
    },
    "id": {
      "run_time": 15116,
      "jobs_failed": 0,
      "jobs_total": 100,
      "tests_failed": 0,
      "reproduced": 0
    },
    "it": {
      "run_time": 11213,
      "jobs_failed": 7,
      "jobs_total": 100,
      "tests_failed": 35,
      "reproduced": 35
    }
  }
}
```

where each section contains

- `run_time` is the sum of `end_timestamp - start_timestamp` for each job.
- `jobs_failed` is the count of jobs with `result == 'testfailed` for each job.
- `jobs_total` is the total number of jobs.
- `tests_failed` is the total number of test failures as determined from the bugzilla_suggestions search terms for the jobs.
- `reproduced` is the number of the test failuress which reproduced a failure in the original section.

### duplicate-opt-pgo-tasks.py

Compare opt and pgo tasks and flag duplicates.

``` shell
./mach taskgraph tasks --json | ./duplicate-opt-pgo-tasks.py
./duplicate-opt-pgo-tasks.py tasks.json
```
