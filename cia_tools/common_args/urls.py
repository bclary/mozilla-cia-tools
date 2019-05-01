"""
standardized argparse parser for treeherder, activedata, ... urls.
"""

import argparse


def get_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "--treeherder",
        default='https://treeherder.mozilla.org',
        help="Treeherder url.")

    parser.add_argument(
        "--activedata",
        dest="activedata",
        default='https://activedata.allizom.org/query',
        help="ActiveData url.")

    return parser
