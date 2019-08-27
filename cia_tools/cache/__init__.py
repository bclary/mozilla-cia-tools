"""This module implements a caching system for the data downloaded
from Bugzilla and Treeherder. It is mean to be transparent to callers.

Possible directory layout

cache_directory/
    bugzilla
    treeherder
        <repository>
            pushes
            jobs
            jobdetails

Whenever a request is made for a supported object, the caller will ask
the cache system if the object is already available and if so it will
be loaded from disk and returned to the caller. If it does not exist,
the caller will be responsible for requesting the object from its
source then calling the cache system to save it for later use.

The appropriate place for this caching check is in the get_ functions
which request specific objects. Thes functions can have the locations
of the potential cached objects encoded in them and they can pass
this information to the cache system in order to locate the requested
objects.
"""

import os
import json
import logging

CACHE_HOME = "/tmp/mozilla-cia-tools-cache"
CACHE_STATS = {}

def load(attributes, name):
    """Return the contents of the file located at the cached location for
    the object specified by the attributes and name if it exists
    otherwise return None.

    attributes: list of attributes of object to be used to create directory
                path to location of cached object.

    name:       string or int filename of object.

    """
    assert CACHE_HOME, 'CACHE location not set.'

    if type(name) != str:
        name = str(name)

    path = os.path.join(CACHE_HOME, *(attributes + [name]))
    if path not in CACHE_STATS:
        CACHE_STATS[path] = {'miss': 0, 'hit': 0}
    if os.path.isfile(path):
        if path in CACHE_STATS:
            CACHE_STATS[path]['hit'] += 1
        with open(path) as datafile:
            return datafile.read()
    if path in CACHE_STATS:
        CACHE_STATS[path]['miss'] += 1
    return None


def save(attributes, name, data):
    """Save data to the cache at the location specified by the attributes
    and name.

    attributes: list of attributes of object to be used to create directory
                path to location of cached object.

    name:       string or int filename of object.

    data:       string contents to be written to the cache file.
    """
    assert CACHE_HOME, 'CACHE location not set.'

    directory = os.path.join(CACHE_HOME, *attributes)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    if type(name) != str:
        name = str(name)
    path = os.path.join(directory, name)
    if path not in CACHE_STATS:
        CACHE_STATS[path] = {'miss': 0, 'hit': 0}
    with open(path, mode='w+b') as datafile:
        CACHE_STATS[path]['hit'] += 1
        datafile.write(bytes(data, 'utf-8'))


def stats():
    logger = logging.getLogger()
    logger.info('cache stats: %s' % json.dumps(CACHE_STATS, indent=2))
