# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

"""
parsers module
"""

import argparse

from .log_level import get_parser
from .push_selection import get_parser
from .urls import get_parser


class ArgumentFormatter(argparse.ArgumentDefaultsHelpFormatter,
                        argparse.RawTextHelpFormatter):
    """
    myformatter docstring
    """
    def __init__(self, prog, **kwargs):
        super(ArgumentFormatter, self).__init__(prog, **kwargs)


