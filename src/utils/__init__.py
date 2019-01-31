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

import logging
from typing import List
from os.path import splitext

logging.getLogger(__name__).addHandler(logging.NullHandler())


def generate_alt_rpm_filenames(rpm_filename: str) -> List[str]:
    """
    The release section of the RPM can vary from the release tag on the
    actual rpm filename that exists at the
    :param rpm_filename: rpm filename
    :return: alternative names of rpm filename, base on the release tag
    """

    # kernel-devel-3.10.0-327.28.3.el7
    base_rpm = splitext(rpm_filename)[0]

    split_by_periods = base_rpm.split('.')

    # x86_64
    arch = ''.join(split_by_periods[-1:])
    name_no_arch = '.'.join(split_by_periods[:-1])

    split_by_dash = name_no_arch.split('-')

    # kernel-devel
    name = '-'.join(split_by_dash[:-2])
    # 3.10.0
    version = split_by_dash[-2]
    # 327.28.3.el7
    release_info = split_by_dash[-1]

    split_release = release_info.split('.')

    result = []

    # mangle release; remove versions between 327 and el7
    indexer = None
    for indexer in range(len(split_release) - 1, 0, -1):

        result.append(
            '-'.join([
                name,
                version,
                '.'.join(
                    split_release[0:indexer] + split_release[-1:] + [arch],
                ),
            ])
        )

    if indexer is None:
        result.append(base_rpm)

    return result
