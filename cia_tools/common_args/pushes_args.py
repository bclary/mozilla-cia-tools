"""
standardized argparse parser for push_args
see PushViewSet in https://github.com/mozilla/treeherder/blob/master/treeherder/webapp/api/push.py
"""

import argparse
import re


def get_parser():

    parser = argparse.ArgumentParser(
        add_help=False,
        description="""Push Related Arguments

If a push isn't selected, the most recent push will be returned.
""")

    parser.add_argument(
        "--repo",
        default='mozilla-central',
        choices=['mozilla-central',
                 'autoland',
                 'mozilla-inbound',
                 'try',
                 'mozilla-beta',
                 'mozilla-release',
                 'mozilla-esr68'],
        help="repository name to query.")

    parser.add_argument(
        "--push_id",
        type=int,
        default=None,
        help="Push id.")

    parser.add_argument(
        "--author",
        default=None,
        help="Push author email. Should be specified if --repo is try and more\n"
        "than one revision is selected.")

    parser.add_argument(
        "--comments",
        default=None,
        help="Push comments pattern.")

    range_group = parser.add_mutually_exclusive_group(
        required=False)

    range_group.add_argument(
        "--date-range",
        default=None,
        help="Push date range startdate enddate CCYY-MM-DD CCYY-MM-DD.")

    range_group.add_argument(
        "--revision",
        default=None,
        help="Push Revision.")

    range_group.add_argument(
        "--commit-revision",
        default=None,
        help="Either Push Revision or any commit referenced in the push.")

    range_group.add_argument(
        "--revision-url",
        default=None,
        help="Url to push revision which can be used in place of --repo and --revision.")

    range_group.add_argument(
        "--revision-range",
        default=None,
        help="Push revision range fromchange-tochange.")

    return parser

def compile_filters(args):
    """compile_filters

    :param: args - argparse.Namespace returned from argparse parse_args.

    Convert push filter regular expression patterns to regular
    expressions and attach to a `push_filters` dict on the args object.

    """
    filter_names = ("comments",)
    if not hasattr(args, 'push_filters'):
        args.push_filters = {}
    if not hasattr(args, 'push_filters'):
        args.push_filters = {}
    for filter_name in filter_names:
        filter_value = getattr(args, filter_name)
        if filter_value:
            args.push_filters[filter_name] = re.compile(filter_value, flags=re.MULTILINE)
