#!/usr/bin/env python3
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


import os
import sys
import logging
import utils.os
from utils.session import State
from db.tables import System
from db.storage import (
    StorePackageResults,
    UpdateFileDetail,
    FlagModifiedFiles,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class GetArguments(utils.os.GetArguments):
    """
    Base parameter class
    """
    def add_args(self):
        pass


def main():
    try:
        exec_path = os.path.realpath(os.path.expanduser(__file__))
    except NameError:
        exec_path = os.path.realpath(os.path.expanduser(sys.argv[0]))

    exec_path = os.path.dirname(exec_path)

    args = GetArguments().parse()

    log.info("Storing package results.")
    with StorePackageResults(name=args.name) as store:

        with open(f'{exec_path}/{args.name}_files.txt', 'r') as f:
            store.store_files(file_iter=f)

        with open(f'{exec_path}/{args.name}_packages.txt', 'r') as f:
            store.store_packages(pkg_data=f)

        # refresh the materialized view
        store.refresh_mviews()
        store.analyze_database()

    with UpdateFileDetail(name=args.name) as up:
        up.populate_rpm_detail()

    with FlagModifiedFiles(name=args.name) as linker:
        flagged = linker.process_modified_files(
            linker.fetch_modified_rpm_details()
        )



if __name__ == '__main__':

    State.startup(action=main)
