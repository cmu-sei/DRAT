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
import os
from dateutil import parser
from io import StringIO
from csv import DictReader
from utils.session import State
from sqlalchemy.engine.result import ResultProxy
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql import (
    select,
    insert,
    update,
    func,
    exists,
    alias,
    delete,
)
from utils import ssh
from db.analysis import FileDifference
from base.enums import FileOrigin
from base.logger import LogConfig
from db.tables import (
    System,
    RpmInfo,
    RpmDetail,
    FileDetail,
    RpmFileDetailLink,
)
from db.views import ResolvedSymlinks

log = LogConfig.get_logger(__name__)


class StorageBase(object):

    def __init__(self, **kwargs):

        name = kwargs.get("name")
        gather = kwargs.get("gather", False)

        self.system: System = State.get_system(name=name, gather=gather)
        if not gather:
            self.system_id: int = self.system.system_id

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):

        if exception_value:
            log.error('Rolling back transaction.')
            State.get_db_session().rollback()
        else:
            log.info('Committing transaction.')
            State.get_db_session().commit()
            log.info('Transaction committed.')

        return False

    def analyze_database(self):
        State.get_db_session().execute("ANALYZE;")


class StorageBaseSystem(StorageBase):
    """
    Base storage object that defines the system_id
    """

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        if self.system is None:
            raise ValueError('Need a valid system to locate detail.')


class FlagModifiedFiles(StorageBaseSystem):
    """
    Creates linkage between files in the RPM files and files located on
    the system.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.file_difference = FileDifference(
            system=self.system,
        )

    def fetch_modified_rpms(self) -> ResultProxy:
        return self.file_difference.fetch_modified_rpms()

    def fetch_modified_rpm_details(self) -> ResultProxy:
        return self.file_difference.fetch_modified_rpm_details()

    def fetch_modified_files_in_rpm(self, rpm_info_id) -> ResultProxy:
        return self.file_difference.fetch_modified_files(
            rpm_info_id=rpm_info_id
        )

    def process_modified_files(
            self,
            modified_rpm_files: ResultProxy
    ) -> int:
        self.file_difference.clear_changed_flags()

        log.info("Flagging modified files")

        rpm: RpmInfo

        count = 0

        for rpm_file in modified_rpm_files:
            rpm_file.file_changed = True
            State.get_db_session().add(rpm_file)
            count += 1

        log.info(f"Flagged {count} files as modified.")

        State.get_db_session().flush()

        return count


class StorePackageResults(StorageBase):
    """
    Stores the package results in the database
    """

    def refresh_mviews(self):
        log.info("Refreshing the symlink materialized view.")

        State.get_db_session().execute(
            """
REFRESH MATERIALIZED VIEW resolved_symlinks WITH DATA;
            """
        )

        log.info("Symlink materialized view refresh complete.")

    def store_system_info(self, **kwargs):
        try:
            system = State.get_db_session().query(System).filter(
                System.name == kwargs["name"]
            ).one()
        except NoResultFound:
            system = System(name=kwargs["name"])

        system.hostname = kwargs.get("hostname", kwargs["name"])
        system.username = kwargs.get("username", os.getlogin())
        system.key_file = kwargs.get("key_file")
        system.use_tty = kwargs.get("use_tty", False)
        system.port = kwargs.get("port", 22)
        system.remote_name = kwargs["remote_hostname"],
        system.kernel_version = kwargs["kernel_version"],
        system.os_distro = kwargs.get("distro"),
        system.os_major_ver = kwargs.get("major"),
        system.os_minor_ver = kwargs.get("minor"),
        system.os_revision = kwargs.get("revision"),

        State.get_db_session().add(system)
        State.get_db_session().flush()

        return system

    def store_files(self, **kwargs):
        file_iter = kwargs.get("file_iter")

        files = 0

        log.info("Storing files...")

        # Remove any existing records
        fdl = alias(RpmFileDetailLink)
        fd = alias(FileDetail)

        delete_fdl = delete(
            fdl
        ).where(
            exists(
                select([1]).where(
                    fd.c.system_id == self.system.system_id
                ).where(
                    fd.c.file_detail_id == fdl.c.file_detail_id
                )
            )
        )

        log.info(f"Pruned {State.get_db_session().execute(delete_fdl).rowcount} links.")

        # delete FileStorage links
        FileDifference(system=self.system).clear_system_file_storage()

        system_files = State.get_db_session().query(FileDetail).filter(
            FileDetail.system == self.system)

        system_files.delete()

        log.info("Pruned existing FileDetails.")

        State.get_db_session().flush()
        State.get_db_session().commit()

        objects = []

        for file_dict in self._convert_results(file_iter=file_iter):
            src = FileOrigin.UnknownSource
            file_path = file_dict.get("path", "")

            if (
                file_path.startswith("/dev/") or
                file_path.startswith("/tmp/") or
                file_path.startswith("/proc/") or (
                    file_path.startswith("/var/log/") and
                    file_path.endswith(".log")
                )
            ):
                src = FileOrigin.EphemeralContent

            file_rec = {
                "system_id": self.system.system_id,
                "file_location": file_path or None,
                "file_type": file_dict['type'],
                "owner_uid": file_dict['uid'],
                "owner_gid": file_dict['gid'],
                "owner_name": file_dict['user'] or None,
                "owner_group": file_dict['group'] or None,
                "file_mode": file_dict['mode'] or None,
                "file_target": file_dict['target'] or None,
                "target_type": file_dict['target_type'] or None,
                "md5_digest": file_dict['md5'] or None,
                "sha256_digest": file_dict['sha256'] or None,
                "file_info": file_dict['info'] or None,
                "file_perm_mode": file_dict['perm'] or None,
                "origin": src.name,
            }

            objects.append(file_rec)

            files += 1

            if files % 50000 == 0:
                log.info(f"{files}")
                State.get_db_session().bulk_insert_mappings(FileDetail, objects)
                State.get_db_session().flush()
                objects.clear()

        if objects:
            State.get_db_session().bulk_insert_mappings(FileDetail, objects)

        objects.clear()
        State.get_db_session().flush()
        State.get_db_session().commit()

        log.info('..done')

    def store_packages(self, **kwargs):

        pkg_data = kwargs.get("pkg_data")
        rpms = {}

        files = 0

        log.info("Storing packages...")

        # Remove any existing records
        fdl = alias(RpmFileDetailLink)
        rd = alias(RpmDetail)

        delete_fdl = delete(
            fdl
        ).where(
            exists(
                select([1]).where(
                    rd.c.system_id == self.system.system_id
                ).where(
                    rd.c.rpm_detail_id == fdl.c.rpm_detail_id
                )
            )
        )

        log.info(f"Pruned {State.get_db_session().execute(delete_fdl).rowcount} links.")

        system_rpm_detail = State.get_db_session().query(RpmDetail).filter(
            RpmDetail.system == self.system)

        system_rpm_detail.delete()
        log.info("Pruned existing RpmDetail records.")

        system_rpm_info = State.get_db_session().query(RpmInfo).filter(
            RpmInfo.system == self.system
        )
        system_rpm_info.delete()
        log.info("Pruned existing RpmInfo records.")

        State.get_db_session().flush()
        State.get_db_session().commit()

        fieldnames = (
            'package_name',
            'version',
            'release',
            'architecture',
            'installation_tid',
            'installation_date',
            'file_name',
            'file_size',
            'digest',
            'file_class',
            'flag',
            'source_rpm',
            'rpm_name',
        )

        objects = []
        for row in self._convert_results(
                file_iter=pkg_data,
                fieldnames=fieldnames
        ):

            file = {
                key: value if value != '(none)' else None
                for key, value in row.items()
            }

            rpm_key = '+'.join([
                file['package_name'] or 'none',
                file['version'] or 'none',
                file['architecture'] or 'none',
            ])

            rpm = rpms.get(rpm_key, None)

            if not rpm:

                try:
                    installation_tid = int(
                        file['installation_tid'] or ''.strip()
                    )
                except ValueError:
                    installation_tid = None

                try:
                    installation_date = parser.parse(file['installation_date'])
                except ValueError:
                    installation_date = None

                rpm = RpmInfo(
                    name=file['package_name'],
                    version=file['version'],
                    release=file['release'],
                    filename=file['rpm_name'],
                    architecture=file['architecture'],
                    installation_tid=installation_tid,
                    installation_date=installation_date,
                    system_id=self.system.system_id,
                )

                State.get_db_session().add(rpm)
                State.get_db_session().flush()

                rpms[rpm_key] = rpm

            try:
                file_size = int(file['file_size'] or ''.strip())
            except ValueError:
                file_size = None

            objects.append(
                {
                    "rpm_info_id": rpm.rpm_info_id,
                    "file_location": file['file_name'],
                    "file_size": file_size,
                    "digest": file['digest'] or None,
                    "file_info": file['file_class'],
                    "file_flag": file['flag'],
                    "system_id": self.system.system_id,
                    "file_changed": None,
                }
            )

            files += 1

            if files % 50000 == 0:
                log.info(f"{files}")
                State.get_db_session().bulk_insert_mappings(RpmDetail, objects)
                State.get_db_session().flush()
                objects.clear()

        if objects:
            State.get_db_session().bulk_insert_mappings(RpmDetail, objects)

        objects.clear()
        State.get_db_session().flush()
        State.get_db_session().commit()

        log.info('..done')

    def _convert_results(
            self,
            file_iter: ssh.StringIterator = None,
            fieldnames: tuple = None
    ):
        """
        Converts cataloged string data into a dictionary
        """

        # Seed the DictReader with the headers
        fake_io = StringIO(next(file_iter))

        csv = DictReader(
            fake_io,
            delimiter='\t',
            fieldnames=fieldnames,
        )

        # Force DictReader to fetch the fieldnames
        if not fieldnames and csv.fieldnames:
            pass

        # Seek to the beginning to overwrite the headers
        for line in file_iter:
            pos = fake_io.tell()
            fake_io.write(line)
            fake_io.seek(pos)

            row = next(csv)
            yield row

        return 'Conversion of results is completed.'


class UpdateFileDetail(StorageBaseSystem):
    """
    This class will do an inplace UPDATE in the database to add the
    file_detail_id, then it will manually update the ones that did not directly
    match the path.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def populate_rpm_detail(self):

        log.info("Updating file details")

        log.info("Clearing existing attributes")
        self._clear_existing()

        # Update direct file_location == file_location matches
        log.info(f"one-to-one match : executing...")
        one_to_one_count = self._run_update()
        log.info(f"one-to-one match : {one_to_one_count}")

        log.info(f"dir match        : executing...")
        dir_match_count = self._run_directory_match_update()
        log.info(f"dir match        : {dir_match_count}")

        log.info(f"link match       : executing...")
        link_match_count = self._run_link_match_update()
        log.info(f"link match       : {link_match_count}")

        total = one_to_one_count + link_match_count + dir_match_count
        log.info(f"total match      : {total}")

        log.info(f"flagging file and setting origin")
        self._flag_existing()
        log.info(f"complete")

    def _run_update(self):

        rd: RpmDetail = aliased(RpmDetail)
        rdu: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        lk: RpmFileDetailLink = aliased(RpmFileDetailLink)

        query = State.get_db_session().query(
            rd.rpm_detail_id,
            fd.file_detail_id
        ).join(
            fd,
            (rd.system_id == fd.system_id) &
            (rd.file_location == fd.file_location)
        ).outerjoin(
            lk,
            (lk.file_detail_id == fd.file_detail_id) &
            (lk.rpm_detail_id == rd.rpm_detail_id)
        ).filter(
            rd.system_id == self.system.system_id,
            lk.rpm_file_detail_link_id == None
        )

        insert_dml = insert(
            RpmFileDetailLink
        ).from_select(
            [
                rd.rpm_detail_id,
                fd.file_detail_id,
            ],
            query
        )

        result = State.get_db_session().execute(insert_dml)
        log.debug(f"{result.rowcount} files linked.")
        State.get_db_session().flush()
        State.get_db_session().commit()
        self.analyze_database()

        return result.rowcount

    def _run_directory_match_update(self):

        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        lk: RpmFileDetailLink = aliased(RpmFileDetailLink)

        query = State.get_db_session().query(
            rd.rpm_detail_id,
            fd.file_detail_id
        ).join(
            ResolvedSymlinks,
            (rd.system_id == ResolvedSymlinks.system_id) &
            (ResolvedSymlinks.target_type == "D") &
            (func.length(rd.file_location) > func.length(
                ResolvedSymlinks.file_location
            )) &
            (ResolvedSymlinks.file_location == func.substr(
                rd.file_location,
                1,
                func.length(ResolvedSymlinks.file_location)
            ))
        ).join(
            fd,
            (fd.system_id == ResolvedSymlinks.system_id) &
            (fd.file_location == (
                ResolvedSymlinks.resolved_location +
                func.substr(
                    rd.file_location,
                    func.length(ResolvedSymlinks.file_location) + 1
                )
            ))
        ).outerjoin(
            lk,
            (lk.file_detail_id == fd.file_detail_id) &
            (lk.rpm_detail_id == rd.rpm_detail_id)
        ).filter(
            (rd.system_id == self.system_id) &
            (lk.rpm_file_detail_link_id == None) &
            (func.coalesce(fd.file_type, "") != "S")
        ).distinct()

        insert_dml = insert(
            RpmFileDetailLink
        ).from_select(
            [
                rd.rpm_detail_id,
                fd.file_detail_id,
            ],
            query
        )

        result = State.get_db_session().execute(insert_dml)
        State.get_db_session().flush()
        State.get_db_session().commit()
        self.analyze_database()
        return result.rowcount

    def _run_link_match_update(self):

        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        lk: RpmFileDetailLink = aliased(RpmFileDetailLink)

        query = State.get_db_session().query(
            rd.rpm_detail_id,
            fd.file_detail_id,
        ).join(
            ResolvedSymlinks,
            (ResolvedSymlinks.system_id == rd.system_id) &
            (ResolvedSymlinks.file_location == rd.file_location)
        ).join(
            fd,
            (ResolvedSymlinks.system_id == fd.system_id) &
            (fd.file_location == ResolvedSymlinks.resolved_location)
        ).outerjoin(
            lk,
            (lk.file_detail_id == fd.file_detail_id) &
            (lk.rpm_detail_id == rd.rpm_detail_id)
        ).filter(
            rd.system_id == self.system_id,
            lk.rpm_file_detail_link_id == None
        )

        insert_dml = insert(
            RpmFileDetailLink
        ).from_select(
            [
                rd.rpm_detail_id,
                fd.file_detail_id,
            ],
            query
        )

        result = State.get_db_session().execute(insert_dml)
        State.get_db_session().flush()
        State.get_db_session().commit()
        self.analyze_database()
        return result.rowcount

    def _flag_existing(self):

        update_rpm = update(RpmDetail).values(
            file_exists=True,
        ).where(
            (RpmDetail.system_id == self.system_id) &
            (RpmDetail.rpm_detail_id == RpmFileDetailLink.rpm_detail_id) &
            (RpmFileDetailLink.file_detail_id != None)
        )

        update_result = State.get_db_session().execute(update_rpm)
        log.info(f"{update_result.rowcount} files flagged as existing.")

        update_file = update(FileDetail).values(
            origin=FileOrigin.PackageInstalled.name,
        ).where(
            (FileDetail.system_id == self.system_id) &
            (FileDetail.file_detail_id == RpmFileDetailLink.file_detail_id) &
            (RpmFileDetailLink.rpm_detail_id != None)
        )

        update_result = State.get_db_session().execute(update_file)
        log.info(f"{update_result.rowcount} files flagged as PackageInstalled.")

    def _clear_existing(self):
        dml = update(RpmDetail).where(
            RpmDetail.system_id == self.system.system_id
        ).values(
            file_exists=False
        )

        result = State.get_db_session().execute(dml)

        State.get_db_session().flush()
        State.get_db_session().commit()
        self.analyze_database()

        log.info(f"Cleared file_exists attribute for {result.rowcount} rows.")

    def _get_detail(
            self,
            rpm_detail: RpmDetail = None,
            symlink: ResolvedSymlinks = None,
            custom_path: str = None
    ):

        if not symlink:
            path = custom_path or rpm_detail.file_location
        else:
            path = symlink.resolved_path

        return State.get_db_session().query(
            FileDetail
        ).filter(
            FileDetail.file_location == path
        ).one_or_none()

    def _map_rpm_to_file(self, rpm_detail: RpmDetail = None):
        # Get by filename
        # happy path, no symlinks
        file_detail = self._get_detail(rpm_detail)
        if file_detail:
            return file_detail

        # try for a direct symlink match
        symlink = State.get_db_session().query(
            ResolvedSymlinks
        ).filter(
            ResolvedSymlinks.file_location == rpm_detail.file_location
        ).one_or_none()

        if symlink:
            file_detail = self._get_detail(rpm_detail=rpm_detail,
                                           symlink=symlink)
            if file_detail:
                return file_detail

        # no easy match here.  brute force by directory
        directories = State.get_db_session().query(
            ResolvedSymlinks
        ).filter(
            ResolvedSymlinks.target_type == 'D'
        ).all()

        for direct in directories:
            if rpm_detail.file_location.startswith(direct.file_location):
                path = (
                    f'{direct.resolved_location}'
                    f'{rpm_detail.file_location[len(direct.file_location):]}'
                )

                file_detail = self._get_detail(
                    rpm_detail=rpm_detail,
                    custom_path=path,
                )

                if file_detail:
                    return file_detail

        # TODO: What to do here? :)
        raise ValueError(
            'cant find file details for rpm_id '
            f'{rpm_detail.rpm_info}. {rpm_detail.file_location}'
        )


class Fetcher(StorageBase):

    @staticmethod
    def fetch_file_detail(rpm_detail: RpmDetail) -> FileDetail:
        db_session = State.get_db_session()

        system_id = State.get_system().system_id
        query = db_session.query(
            FileDetail
        ).join(
            RpmFileDetailLink
        ).join(
            RpmDetail
        ).filter(
            (RpmDetail.system_id == system_id) &
            (RpmDetail.rpm_detail_id == rpm_detail.rpm_detail_id)
        )

        file_details = query.all()

        if len(file_details) > 0:
            return file_details[0]
        else:
            raise ValueError("FileDetail cannot be loaded.")
