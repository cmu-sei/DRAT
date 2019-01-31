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

import sys
sys.path.insert(0, '../../')

import os
from utils.session import State
import utils.os
from sqlalchemy.orm.session import Session
from db.tables import (
    RpmInfo,
    RpmDetail,
    FileDetail,
    System,
)

def main():
    sys = utils.os.GetArguments().parse().name

    print('Path to analyze:')
    path = input()
    print('OK. Examining ' + path + ' on ' + sys)
    
    system: System = State.get_system(name=sys)
    session: Session = State.get_db_session()

    lookup = path
    if lookup.endswith(os.path.sep):
        lookup += "%"
    
    file_details: List[FileDetail] = session.query(
        FileDetail
    ).filter(
        (FileDetail.system_id == system.system_id) &
        (FileDetail.file_location.like(lookup))
    ).all()
    
    for f in file_details:
        print(f.file_location + ' is ' + f.origin)
    
if __name__ == '__main__':
    # Initialize the global database session
    State.startup(action=main)
