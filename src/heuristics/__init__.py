#------------------------------------------------------------------------------
# DRAT Prototype Tool Source Code
# 
# Copyright 2019 Carnegie Mellon University. All Rights Reserved.
# 
# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING 
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.
# 
# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.
# 
# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for non-US
# Government use and distribution.
# 
# This Software includes and/or makes use of the following Third-Party
# Software subject to its own license:
# 
# 1. Python 3.7 (https://docs.python.org/3/license.html)
# Copyright 2001-2019 Python Software Foundation.
# 
# 2. SQL Alchemy (https://github.com/sqlalchemy/sqlalchemy/blob/master/LICENSE)
# Copyright 2005-2019 SQLAlchemy authors and contributor.
# 
# DM19-0055
#------------------------------------------------------------------------------

import re
import os.path
import enum
from collections import namedtuple


FILE_PATTERNS = {
}

RPM_PATTERNS = {
}

IGNORE_EXTS = (
    '.pyc',
    '.pyo',
    '.cache',
)

IGNORE_FILES = (
    '.cache'
)

IGNORE_PATTERNS = (
    '^/var/lib/rpm/',
    '^/run/',
    '^/var/log/',
)

IGNORE_REGEX = (
    [re.compile(p) for p in IGNORE_PATTERNS]
)

SearchPair = namedtuple('SearchPair', ['callback', 'mimetype'])


class PatternType(enum.Enum):
    """
    Enum for heuristic rule type
    """
    FILE = enum.auto()
    RPM = enum.auto()


def is_file_excluded(filename: str):
    return (
        _is_extension_excluded(filename) or
        _is_file_ignored(filename) or
        _is_file_in_patterns(filename)
    )


def _is_extension_excluded(filename: str):
    return os.path.splitext(filename)[-1] in IGNORE_EXTS


def _is_file_ignored(filename: str):
    return os.path.basename(filename) in IGNORE_FILES


def _is_file_in_patterns(filename: str):
    matches = [regex.match(filename) for regex in IGNORE_REGEX]
    return any(matches)


def add_patterns(pattern_type: PatternType, patterns: dict):

    if pattern_type == PatternType.FILE:
        global_patterns = FILE_PATTERNS
    else:
        global_patterns = RPM_PATTERNS

    for pattern, callback in patterns.items():
        fetched_pattern = global_patterns.get(pattern, None)
        if not fetched_pattern:
            global_patterns[pattern] = callback
        else:
            raise ValueError("Pattern conflict")


import heuristics.rules
