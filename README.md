# mozilla-cia-tools

## Installation

We require python3 to get new library features and things and to cut ties with 2.7
since we are going to have to do it anyway EOY.

```
pip3 install --user virtualenv
python3 -m virtualenv venv
. venv/bin/activate
pip install -r requirements.txt
```

## Tools

### activedata_compare_tests.py

```
./activedata_compare_tests.py --repo try --revision 43f213fc29c130997a7aa5b3fa370fe57bc35dad

$ ./activedata_compare_tests.py --help
usage: activedata_compare_tests.py [-h]
                                   [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                   [--treeherder TREEHERDER]
                                   [--activedata ACTIVEDATA]
                                   [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                   [--author AUTHOR]
                                   [--date-range DATE_RANGE | --revision REVISION | --revision-range REVISION_RANGE]
                                   [--combine-chunks]
                                   [--output-push-differences-only]

ActiveData compare-tests

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --activedata ACTIVEDATA
                        ActiveData url. (default: https://activedata.allizom.org/query)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange tochange. (default: None)
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

```
./activedata_query.py --file examples/activedata_query/query-test-summary.json

$ ./activedata_query.py --help
usage: activedata_query.py [-h]
                           [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                           [--file FILE]

Perform queries against ActiveData.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --file FILE           File containing ActiveData query as json.. (default: None)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```

writes results of ActiveData query in json format to stdout.

### activedata_query_tests.py

```
./activedata_query_tests.py --repo try --revision 43f213fc29c130997a7aa5b3fa370fe57bc35dad

$ ./activedata_query_tests.py --help
usage: activedata_query_tests.py [-h]
                                 [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                 [--treeherder TREEHERDER]
                                 [--activedata ACTIVEDATA]
                                 [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                 [--author AUTHOR]
                                 [--date-range DATE_RANGE | --revision REVISION | --revision-range REVISION_RANGE]
                                 [--include-passing-tests]

ActiveData query tests.

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --activedata ACTIVEDATA
                        ActiveData url. (default: https://activedata.allizom.org/query)
  --repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}
                        repository name to query. (default: mozilla-central)
  --author AUTHOR       Push author email. Should be specified if --repo is try and more
                        than one revision is selected. (default: None)
  --date-range DATE_RANGE
                        Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD. (default: None)
  --revision REVISION   Push Revision. (default: None)
  --revision-range REVISION_RANGE
                        Push revision range fromchange tochange. (default: None)
  --include-passing-tests
                        Query tests against ActiveData. (default: False)

You can save a set of arguments to a file and specify them later
using the @argfile syntax. The arguments contained in the file will
replace @argfile in the command line. Multiple files can be loaded
into the command line through the use of the @ syntax. Each argument
and its value must be on separate lines in the file.
```
### analyze_logs.py

```
./analyze_logs.py --path /run/media/bclary/wd1backup/treeherder-logs/gcp/gcp/ --filename live_backing.log --include-tests --dechunk > /tmp/gcp-tests-dechunk.json 2> /tmp/gcp-tests-dechunk.err

$ ./analyze_logs.py --help
usage: analyze_logs.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                       [--path PATH] [--filename FILENAME] [--include-tests]
                       [--dechunk]

Analyze downloaded Test Log files producing json summaries..

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Logging level. (default: INFO)
  --path PATH           Log. (default: None)
  --filename FILENAME   Base log filename suffix. (default: live_backing.log)
  --include-tests       Include TEST- lines. (default: False)
  --dechunk             Combine chunks. (default: False)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### combine_log_json.py

```
$ ./combine_log_json.py --help
usage: combine_log_json.py [-h] [--file FILES] [--alias ALIASES]
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

```
cia_tools/download_treeherder_jobdetails.py --log-level DEBUG --repo try --revision a54ad20ea2cf58b1dc75e4abdb116f6444c77128 --download-job-details '.*log' --output /tmp/dummy

$ ./download_treeherder_jobdetails.py --help
usage: download_treeherder_jobdetails.py [-h]
                                         [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                                         [--repo {mozilla-central,autoland,inbound,try,mozilla-beta,mozilla-release}]
                                         [--author AUTHOR]
                                         [--date-range DATE_RANGE | --revision REVISION | --revision-range REVISION_RANGE]
                                         [--treeherder TREEHERDER]
                                         [--download-job-details DOWNLOAD_JOB_DETAILS]
                                         [--output OUTPUT]

Download Test Log files from Treeherder/Taskcluster.

blah blah metadata encoded file names
examples blah blah

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
  --revision-range REVISION_RANGE
                        Push revision range fromchange tochange. (default: None)
  --treeherder TREEHERDER
                        Treeherder url. (default: https://treeherder.mozilla.org)
  --download-job-details DOWNLOAD_JOB_DETAILS
                        Regular expression matching Job details url basenames to be
                                downloaded.  Example:live_backing.log|logcat.*.log. Default
                                None. (default: None)
  --output OUTPUT       Directory where to save downloaded job details. (default: output)

You can save a set of arguments to a file and specify them later using
the @argfile syntax. The arguments contained in the file will replace
@argfile in the command line. Multiple files can be loaded into the
command line through the use of the @ syntax.

Each argument and its value must be on separate lines in the file.
```

### duplicate-opt-pgo-tasks.py

Compare opt and pgo tasks and flag duplicates.

```
./mach taskgraph tasks --json | ./duplicate-opt-pgo-tasks.py
./duplicate-opt-pgo-tasks.py tasks.json
```
