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

from hashlib import sha512
from pathlib import Path
import pytest
from db.tables import RpmInfo
from utils.session import State
from heuristics import heuristic_utils


def test_package_installed(test_database):
    packages = heuristic_utils.package_installed("bash")

    assert packages[0].name == "bash"


def test_path_not_modified(test_database):
    assert not heuristic_utils.path_modified("/etc/profile")


def test_path_modified(test_database):
    session = State.get_db_session()

    session.execute(
        """
update iac.rpm_detail set file_changed = TRUE
where file_location = '/etc/profile'
  and system_id = 1;
        """)

    assert heuristic_utils.path_modified("/etc/profile")
    session.rollback()


def test_path_exists(test_database):
    assert heuristic_utils.path_exists("/etc/profile")


def test_path_not_exists(test_database):
    assert not heuristic_utils.path_exists("/etc/profiles")


@pytest.mark.parametrize(
    "path_spec",
    [
        ("/etc/rc.d"),
        ("/etc/rc.d/"),
    ],
)
def test_get_directory_contents(path_spec):
    expected_files = (
        "/etc/rc.d/init.d",
        "/etc/rc.d/rc0.d",
        "/etc/rc.d/rc1.d",
        "/etc/rc.d/rc2.d",
        "/etc/rc.d/rc3.d",
        "/etc/rc.d/rc4.d",
        "/etc/rc.d/rc5.d",
        "/etc/rc.d/rc6.d",
        "/etc/rc.d/rc.local"
    )

    results = heuristic_utils.get_directory_contents(path_spec)
    files = [f.file_location for f in results]
    assert (
        len(expected_files) == len(files) and
        expected_files[0] in files and
        expected_files[1] in files and
        expected_files[2] in files and
        expected_files[3] in files and
        expected_files[4] in files and
        expected_files[5] in files and
        expected_files[6] in files and
        expected_files[7] in files and
        expected_files[8] in files
    )

@pytest.mark.parametrize(
    "rehydrate_method", [
        heuristic_utils.path_rehydrate,
        heuristic_utils.path_rehydrate_as_bytes,
    ]
)
def test_path_rehydrate(test_sshd, get_test_path: Path, rehydrate_method):
    test_file = rehydrate_method("/home/testssh/test_file.txt")
    remote_hash = sha512()
    if rehydrate_method == heuristic_utils.path_rehydrate_as_bytes:
        test_array = test_file.read()
    else:
        test_array = test_file.encode("utf-8")

    remote_hash.update(test_array)
    local_hash = sha512()

    with open(
            get_test_path.joinpath("testssh/test_file.txt").as_posix(),
            "rb"
    ) as f:
        local_hash.update(f.read())

    remote_digest = remote_hash.digest()
    local_digest = local_hash.digest()

    assert remote_digest == local_digest
