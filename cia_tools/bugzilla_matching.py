#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import copy
import logging
import re

logger = logging.getLogger(__name__)


def match_bug_summary_to_mozharness_failure(bug_summary, initial_comment):
    """We have seveal scenarios here.

    We start with a bug filed by a sheriff or someone using the
    Treeherder bug filing system.

    The bug's summary may contain a munged version of the test failure.

    1. We want to use this bug summary to search the first comment made by
    the bug filer looking for the actual failure in the included
    mozharness logs lines.

    We don't need to filter the variable items in the summary since the
    mozharness log lines in the bug will be exact matches even for the
    variable parts of the failure message.

    From this we want to find the exact failure from the original
    mozharness log and then determine the test name if possible and then
    create a reduced failure message that can be used to search for the
    same failure in different jobs. In this case we will need to deal with
    the variable aspects of the failure message.

    Strategy:

    1. bug summary is a " | " delimited list.

    break summary into parts.

    find matches in the mozharness output for each of the parts.

    If a part has no matches, then remove either a leading word or
    trailing word and look for matches again until we get a non-empty set.

    # See treeherder/model/error_summary.py for info on bug suggestions

    """
    # bug summary usually contains an edited version of the failure
    # bugs/635373-3.html == bugs/635373-3-ref.html | ...
    # convert this to bugs/635373-3.html | ...
    REFTEST_RE = re.compile(r'\s+[=!]=\s+[^|]+')


    # Patterns used to remove or replace text in the bug summary.
    # which might have been edited by the bug filer.
    bugzilla_summary_munge_res = [
        (re.compile(r'Intermittent '), ''),
        (REFTEST_RE, ' '),
        (re.compile(r'/TEST'), 'TEST'),
        (re.compile(r'/PROCESS'), 'PROCESS'),
        (re.compile(r'<[^>]*>(<[^>]*>)?(\.js)?'), ''),
        (re.compile(r'Tier 2 ', flags=re.IGNORECASE), ''),
        (re.compile(r'fission '), ''),
    ]
    munged_bug_summary = bug_summary
    for regx, replacement in bugzilla_summary_munge_res:
        match = regx.search(munged_bug_summary)
        if match:
            munged_bug_summary = munged_bug_summary.replace(match.group(0), replacement)

    # Collect the mozharness lines from the comment and
    # remove the  mozharness and taskcluster prefixes
    MOZHARNESS_RE = re.compile(
        r'.*\d+:\d+:\d+[ ]+(?:DEBUG|INFO|WARNING|ERROR|CRITICAL|FATAL) - [ ]?'
    )

    OUTPUT_RE = re.compile(r'\s*(?:GECKO\(\d+\)|PID \d+)\s*$')
    RESULT_RE = re.compile(r'(TEST|PROCESS)-')

    # Check for the case where [task does not start a new line
    # and insert a newline prior to [task.
    INTERIOR_TASK_RE = re.compile(r'([^\n])\[task', re.MULTILINE)
    interior_task_match = INTERIOR_TASK_RE.search(initial_comment)
    while interior_task_match:
        initial_comment = INTERIOR_TASK_RE.sub(interior_task_match.group(1) + '\n[task',
                                               initial_comment)
        interior_task_match = INTERIOR_TASK_RE.search(initial_comment)

    mozharness_lines = []
    for raw_line in initial_comment.split('\n'):
        if MOZHARNESS_RE.match(raw_line):
            mozharness_lines.append(MOZHARNESS_RE.sub('', raw_line))

    tokens = munged_bug_summary.split(' | ')
    if OUTPUT_RE.search(tokens[0]):
        tokens = tokens[1:]

    # result | test | message implies at most 3 elements unless
    # the bug filer has added additonal clauses to the summary.
    # Convert the last token into the join of the extra tokens
    # so that they are not considered independently.
    # test | message implies at most 2 elements unless additional
    # clauses were added. Again convert the last token.
    # This will result in preferentially matching the first clause
    # over other clauses added at the end.
    # An exception to this is when we have a crash-check failure
    # REFTEST TEST-UNEXPECTED-FAIL | file:///Z:/task_1562891058/build/tests/reftest/tests/image/test/reftest/downscaling/downscale-moz-icon-1.html == file:///Z:/task_1562891058/build/tests/reftest/tests/image/test/reftest/downscaling/downscale-moz-icon-1-ref.html | crash-check | This test left crash dumps behind, but we weren't expecting it to!
    # but we will handle this case ok.

    if RESULT_RE.search(tokens[0]):
        if len(tokens) > 3:
            tokens = tokens[:2] + [' | '.join(tokens[2:])]
    else:
        if len(tokens) > 2:
            tokens = tokens[:1] + [' | '.join(tokens[1:])]

    # Create a list of strings to hold the tokens which matched mozharness lines
    match_tokens = [None for i in range(len(tokens))]

    # Create a list of sets to hold matching mozharness lines for each of the tokens
    token_match_sets = [set() for i in range(len(tokens))]

    # We operate in two phases: Forwards and Backwards.
    # Forwards is when we are removing words from front of the token.
    # Backwards is when we are removing words from the back of the token.

    for phase in ('backward', 'forward', ):
        if phase == 'backward':
            slice_start = 0
            slice_stop = -1
        else:
            slice_start = 1
            slice_stop = None

        for itoken in range(len(tokens)):
            token = tokens[itoken]
            token_match_set = token_match_sets[itoken]

            while token and not token_match_set:
                token_match_set = set([line for line in mozharness_lines if token in line])
                if not token_match_set:
                    token = ' '.join(token.split(' ')[slice_start:slice_stop:1])
                    # Ignore short tokens
                    if len(token) < 10:
                        token = ''
                else:
                    match_tokens[itoken] = token
                    token_match_sets[itoken] = token_match_set

    candidate_sets = copy.deepcopy(token_match_sets)

    # Sort the list of candidated sets by descending count of
    # their elements.
    candidate_sets.sort(key=len, reverse=True)

    result_set = candidate_sets[0]
    for iset in range(1, len(candidate_sets)):
        candidate_set = candidate_sets[iset]
        # Clean the candidate set of extraneous TEST- messages
        lines_to_be_removed = set()
        for candidate_line in candidate_set:
            if 'TEST-' in candidate_line and not 'UNEXPECTED' in candidate_line:
                lines_to_be_removed.add(candidate_line)
        candidate_set.difference_update(lines_to_be_removed)
        if candidate_set:
            # Ignore empty sets.
            result_set.intersection_update(candidate_set)

    if len(result_set) == 1:
        match = result_set.pop()
    else:
        # Multiple matches. Iterate through the matches returning the
        # first to contain the bug summary.
        match = None
        while result_set:
            candidate_match = result_set.pop()
            if munged_bug_summary in candidate_match:
                match = candidate_match
                break
    if match:
        match = match.strip()
    return match

