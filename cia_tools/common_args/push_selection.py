"""
standardized argparse parser for push_selection
see PushViewSet in https://github.com/mozilla/treeherder/blob/master/treeherder/webapp/api/push.py
"""

import argparse


def get_parser():

    parser = argparse.ArgumentParser(
        description="push selection parser description",
        epilog="push selection parser epilog",
        add_help=False)

    parser.add_argument(
        "--repo",
        default='mozilla-central',
        choices=['mozilla-central',
                 'autoland',
                 'inbound',
                 'try',
                 'mozilla-beta',
                 'mozilla-release'],
        help="repository name to query.")

    parser.add_argument(
        "--author",
        default=None,
        help="Push author email. Should be specified if --repo is try and more\n"
        "than one revision is selected.")

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
