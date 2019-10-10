#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import re
import sys

re_pattern = re.compile(r'([^/]+)/(opt|pgo)-(.*)')
opt = set()
pgo = set()

if len(sys.argv) == 1:
    input = sys.stdin
else:
    input = open(sys.argv[1])

tasks = json.load(input)

keys = list(tasks.keys())
keys.sort()

for key in keys:
    match = re_pattern.match(key)
    if not match:
        continue

    (platform, buildtype, test) = match.groups()
    #if 'android' not in platform or 'raptor' not in test:
    #    continue
    if 'attributes' not in tasks[key]:
        continue
    if 'run_on_projects' not in tasks[key]['attributes']:
        continue
    run_on_projects = tasks[key]['attributes']['run_on_projects']
    try:
        run_on_projects.remove('try')
    except ValueError:
        pass
    if not run_on_projects:
        continue

    s = opt if buildtype == 'opt' else pgo
    s.add('%s/%s' % (platform, test))

all = opt.union(pgo)
duplicates = opt.intersection(pgo)

opt_list = list(opt)
opt_list.sort()

pgo_list = list(pgo)
pgo_list.sort()

duplicates_list = list(duplicates)
duplicates_list.sort()

all_list = list(all)
all_list.sort()

print('counts: opt %s, pgo: %s, duplicates: %s' % (len(opt), len(pgo), len(duplicates)))
print()

print('test|opt|pgo')
print('----|---|---')
for t in all:
    print('%s | %s | %s' % (t, t in opt, t in pgo))

print('\nduplicates\n')
print('\n'.join(duplicates_list))

