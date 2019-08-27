"""
standardized argparse parser for treeherder urls.
"""

import argparse


def get_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "--treeherder-url",
        default='https://treeherder.mozilla.org',
        help="Treeherder url.")
    return parser
