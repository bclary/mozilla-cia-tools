"""
standardized argparse parser for  activedata urls.
"""

import argparse


def get_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "--activedata",
        dest="activedata",
        default='https://activedata.allizom.org/query',
        help="ActiveData url.")

    return parser
