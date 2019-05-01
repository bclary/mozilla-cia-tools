
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import

import setuptools

PACKAGE_NAME = 'mozilla-cia-tools'
PACKAGE_VERSION = '0.0.1'

with open("README.md", "r") as fh:
    long_description = fh.read()

deps = ['treeherder-client']

setuptools.setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    description="A collection of tools for Mozilla Continous Integration Automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=['Programming Language :: Python :: 3.5'],
    keywords='mozilla, continuous integration, treeherder, activedata',
    author='Bob Clary',
    author_email='bob@bclary.com',
    url='https://github.com/bclary/mozilla-cia-tools',
    license='MPL',
    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=deps,
    entry_points="""
    # -*- Entry points: -*-
    """,
)
