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
import os
from io import BytesIO
from typing import List
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import func
from utils.session import State
from base.exceptions import RpmFileNotFound
from db.tables import (
    RpmInfo,
    RpmDetail,
    FileDetail,
    System,
)
from base.enums import FileOrigin, OSDistro
from utils.ssh import SftpWrapper


def package_installed(package_name: str) -> List[RpmInfo]:
    """
    Check if package is installed on the source system.

    Mangle package name as needed for rpm or scl naming conventions.
    Check the rpm_details table for a match.
    Return None for no match, or an rpm_details object if found.
    """
    system: System = State.get_system()
    session: Session = State.get_db_session()

    rpm_info: List[RpmInfo] = session.query(
        RpmInfo
    ).filter(
        (RpmInfo.system_id == system.system_id)
        & (RpmInfo.name == package_name)
    ).all()

    return rpm_info


def path_modified(path_spec: str) -> bool:
    """
    Check if a source system file was modified after package installation.

    path_spec is a full pathname on the source file system. Look it up in
    file_details table. If origin is PKG_MODIFIED, return true.
    """

    system: System = State.get_system()
    session: Session = State.get_db_session()

    rpm_detail: RpmDetail = session.query(
        RpmDetail
    ).filter(
        (RpmDetail.system_id == system.system_id)
        & (RpmDetail.file_location == path_spec)
    ).one_or_none()

    if not rpm_detail:
        raise RpmFileNotFound("Unable to locate file in RpmDetails")

    return rpm_detail.file_changed


def get_directory_contents(path_spec: str) -> List[FileDetail]:
    system: System = State.get_system()
    session: Session = State.get_db_session()

    lookup = path_spec
    if not lookup.endswith(os.path.sep):
        lookup += os.path.sep
    lookup += "%"

    file_details: List[FileDetail] = session.query(
        FileDetail
    ).filter(
        (FileDetail.system_id == system.system_id)
        & (FileDetail.file_location.like(lookup))
        & (func.strpos(
            func.substr(FileDetail.file_location, len(lookup)),
            os.path.sep,
        ) == 0)
    ).all()

    return file_details


def path_exists(path_spec: str) -> bool:
    """
    Return boolean if the path exists in the source file system.
    """
    system: System = State.get_system()
    session: Session = State.get_db_session()

    file_detail: FileDetail = session.query(
        FileDetail
    ).filter(
        (FileDetail.system_id == system.system_id)
        & (FileDetail.file_location == path_spec)
    ).one_or_none()

    return file_detail is not None


def system_OS(distro: OSDistro) -> bool:
    system: System = State.get_system()

    if system.os_distro == 'centos':
        return OSDistro.CentOS
    else:
        return OSDistro.Other


def origin_unknown(path_spec: str) -> bool:
    """
    Return True if FileOrigin is UnknownSource, else False.
    """
    system: System = State.get_system()
    session: Session = State.get_db_session()

    file_detail: FileDetail = session.query(
        FileDetail
    ).filter(
        (FileDetail.system_id == system.system_id)
        & (FileDetail.file_location == path_spec)
        & (FileDetail.origin == FileOrigin.UnknownSource.name)
    ).one_or_none()

    return file_detail is not None


def unknown_count() -> int:
    """
    Count the number of files where FileOrigin is UnknownSource for the
    current system.
    """
    system: System = State.get_system()
    session: Session = State.get_db_session()

    return session.query(
        FileDetail
    ).filter(
        (FileDetail.system_id == system.system_id)
        & (FileDetail.origin == FileOrigin.UnknownSource.name)
    ).count()


def path_rehydrate_as_bytes(path_spec) -> BytesIO:
    """
    Return the contents of a modified file.
    """
    with SftpWrapper(State.get_ssh_session().get_sftp_client()) as sftp:
        fh = sftp.get_file_handle(remote_name=path_spec)

        return fh


def path_rehydrate(path_spec) -> str:
    """
    Return a string containing the contents of a modified text file.
    """
    return path_rehydrate_as_bytes(path_spec).getvalue().decode('utf-8')


def conf_file_field(conf_file, field_name):
    """
    Return a field value from a Linux configuration file

    conf files in /etc have structure <ws><fieldname><ws><fieldvalue>

    Search for the fieldname at the start of a newline with trailing space.
    If the field is not found, return empty string.
    If the field is found, strip quotes or traling ; off the value (if any),
    strip any trailing whitespace, and return it.
    """
    m = re.findall(r'^\s*' + field_name + r'\s.*', conf_file, re.M)
    vals = []
    for s in m:
        # strip leading/trailing whitespace, grab the last token, and
        # strip any quotes or ; around it.
        vals.append((s.strip().split()[-1]).strip('";'))
    val = ''
    if not len(vals) == 0:
        val = vals[0]
    return val


def conf_file_fields(conf_file, field_name):
    """
    Return a list of field value from a Linux configuration file

    conf files in /etc have structure <ws><fieldname><ws><fieldvalue>

    Some fields can appear multiple times (eg Include, or DocumentRoot if there
    are Virtual Hosts.

    Search for the fieldname at the start of a newline with trailing space.
    If the field is not found, return empty list
    If the field is found, strip quotes or trailing ; off the value (if any),
    strip any trailing whitespace, and add it to the list.
    """

    m = re.findall(r'^\s*' + field_name + r'\s.*', conf_file, re.M)
    vals = []
    for s in m:
        # strip leading/trailing whitespace, grab the last token, and
        # strip any quotes or ; around it.
        vals.append((s.strip().split()[-1]).strip('";'))
    return vals
