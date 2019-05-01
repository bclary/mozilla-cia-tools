"""
standardized argparse parser for log-level
"""

import argparse


def get_parser():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("--log-level",
                        default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR",
                                 "CRITICAL"],
                        help="Logging level.")
    return parser

