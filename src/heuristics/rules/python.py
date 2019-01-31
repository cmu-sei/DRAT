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
import os
import json
import logging
from db.tables import FileDetail, ApplicationData
from utils.ssh import SshConnector
import heuristics
from typing import Pattern
import re
from sqlalchemy import Text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def match_python(
        client: SshConnector,
        file_detail: FileDetail
):
    session: Session = Session.object_session(file_detail)
    dir_name = os.path.dirname(file_detail.file_location)

    is_sys_py = dir_name == "/usr/bin"

    is_venv_py = not is_sys_py and session.query(
        FileDetail
    ).filter(
        FileDetail.system_id == file_detail.system_id
    ).filter(
        FileDetail.file_location == f"{dir_name}/activate"
    ).count() == 1

    has_pip = session.query(
        FileDetail
    ).filter(
        FileDetail.system_id == file_detail.system_id
    ).filter(
        FileDetail.file_location == f"{dir_name}/pip"
    ).count() == 1

    log.info(
        f"is in venv: {is_venv_py}, is sys py: {is_sys_py}, has_pip: {has_pip}"
    )

    py_info = session.query(ApplicationData).filter(
        ApplicationData.system_id == file_detail.system_id
    ).filter(
        ApplicationData.doc["name"].astext == "python"
    ).one_or_none()

    if not py_info:
        py_info = ApplicationData(system_id=file_detail.system_id)
    if not py_info.doc:
        py_info.doc = {"name": "python", "locations": {}}

    client
    py_info.doc[file_detail.file_location] = {
        "version": "",
        "system_python": is_sys_py,
        "venv_python": is_venv_py,
        "has_pip": has_pip,
        "requirements": [],
    }

    session.add(py_info)


FILE_PATTERNS = {
    re.compile(r".+\/bin\/python$"): heuristics.SearchPair(
        match_python,
        'application/x-executable',
    )
}
