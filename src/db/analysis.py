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

import typing
from pprint import pformat
from sqlalchemy import bindparam
from sqlalchemy.orm.session import Session
from sqlalchemy.engine.result import ResultProxy
from sqlalchemy.sql.expression import (
    case,
    func,
    not_,
    and_,
    exists,
    select,
    join,
    alias,
    delete,
)
from sqlalchemy.sql.functions import coalesce
from sqlalchemy.orm import sessionmaker, aliased
from heuristics import is_file_excluded
from base.logger import LogConfig
from db.tables import (
    RpmInfo,
    RpmDetail,
    RpmFileDetailLink,
    FileDetail,
    System,
    FileStorage,
    RpmDetailPatchStorageLink,
    FileDetailStorageLink,
)
from base.enums import FileOrigin

log = LogConfig.get_logger(__name__)


class FileDifference(object):
    """
    Class loads file differences by system and
    """

    def __init__(
            self,
            system: System = None,
    ):
        if system is None:
            raise ValueError('system must not be None')

        self.system = system
        self._session: Session = Session.object_session(system)

    def clear_changed_flags(self):
        dml = RpmDetail.__table__.update().where(
            RpmDetail.system == self.system
        ).values(
            file_changed=False
        )

        result = self._session.execute(dml)
        log.info(f"Cleared file_changed attribute for {result.rowcount} rows.")

    def clear_data_for_current_system(self):
        p = alias(FileStorage)
        ps = alias(FileStorage)
        pl = alias(RpmDetailPatchStorageLink)
        pls = alias(RpmDetailPatchStorageLink)
        rd = alias(RpmDetail)
        s = alias(System)

        delete_links_sql = delete(pl).where(
            exists(
                select([1]).select_from(
                    pls.join(
                        rd, pls.c.rpm_detail_id == rd.c.rpm_detail_id
                    ).join(
                        s, rd.c.system_id == s.c.system_id
                    )
                ).where(
                    s.c.system_id == self.system.system_id
                ).where(
                    pl.c.id == pls.c.id
                )
            )
        )

        delete_patches_sql = delete(p).where(
            not_(
                exists(
                    select([1]).select_from(
                        pl.join(
                            ps, pl.c.file_storage_id == ps.c.id
                        )
                    ).where(
                        p.c.id == ps.c.id
                    )
                )
            )
        )

        result_links = self._session.execute(delete_links_sql)

        if result_links.rowcount:
            log.info(f"Removed {result_links.rowcount} previous patch links")

        result_patches = self._session.execute(delete_patches_sql)

        if result_patches.rowcount:
            log.info(f"Removed {result_patches.rowcount} previous patches")

    def fetch_flagged_rpms(self) -> typing.List[RpmInfo]:

        ri = aliased(RpmInfo)
        rd = aliased(RpmDetail)
        sub_query = self._session.query(
            rd
        ).filter(
            rd.file_changed
        ).filter(
            rd.rpm_info_id == ri.rpm_info_id
        )

        query = self._session.query(
            ri
        ).filter(
            ri.system == self.system,
            sub_query.exists()
        )

        return query.all()

    def fetch_flagged_file_details(
        self,
        rpm_info: RpmInfo
    ) -> typing.Iterable[FileDetail]:

        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        rdl: RpmFileDetailLink = aliased(RpmFileDetailLink)

        query = self._session.query(
            fd
        ).join(
            rdl
        ).join(
            rd
        ).filter(
            rd.rpm_info == rpm_info,
            rd.system == rpm_info.system,
            rd.file_changed,
            fd.file_info.startswith('text/'),
            fd.file_type == "F",
        )

        row: FileDetail
        for row in query.all():
            if not is_file_excluded(row.file_location):
                yield row

    def fetch_flagged_files(
            self,
            rpm_info: RpmInfo = None
    ) -> typing.List[RpmDetail]:

        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        rdl: RpmFileDetailLink = aliased(RpmFileDetailLink)

        query = self._session.query(
            rd
        ).join(
            rdl
        ).join(
            fd
        ).filter(
            rd.rpm_info == rpm_info,
            rd.system == rpm_info.system,
            rd.file_changed,
            fd.file_info.startswith("text/"),
            not_(fd.file_location.endswith(".py"))
        )

        row: RpmDetail
        for row in query.all():
            if not is_file_excluded(row.file_location):
                yield row

    def fetch_modified_files(self, rpm_info_id: int = None) -> ResultProxy:

        if rpm_info_id is None:
            raise ValueError('rpm_info_id cannot be null')

        ri = aliased(RpmInfo)
        rd = aliased(RpmDetail)
        fd = aliased(FileDetail)
        system = aliased(System)

        sub_rd = aliased(RpmDetail)

        sub_query = self._session.query(
            sub_rd
        ).join(
            RpmFileDetailLink
        ).join(
            fd
        ).join(
            system
        ).filter(
            system == self.system.system_id,
            rd.rpm_detail_id == sub_rd.rpm_detail_id,
            coalesce(sub_rd.digest, 'x') == case(
                {
                    32: fd.md5_digest,
                    64: fd.sha256_digest
                },
                value=func.length(rd.digest),
                else_='x'
            ),
        )

        query = self._session.query(
            rd
        ).join(
            ri
        ).filter(
            ri.rpm_info_id == rpm_info_id,
            not_(sub_query.exists()),
        )

        results: ResultProxy = query.all()

        return results

    def fetch_modified_rpm_details(self) -> ResultProxy:

        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        rdl: RpmFileDetailLink = aliased(RpmFileDetailLink)
        s: System = aliased(System)

        query = self._session.query(
            rd
        ).join(
            s,
            (s.system_id == rd.system_id),
        ).join(
            rdl,
            (rdl.rpm_detail_id == rd.rpm_detail_id),
        ).outerjoin(
            fd,
            (fd.file_type == "F") &
            (rdl.file_detail_id == fd.file_detail_id) &
            (
                rd.digest == case({
                        32: fd.md5_digest,
                        64: fd.sha256_digest,
                    },
                    value=func.length(
                        coalesce(
                            rd.digest,
                            ""
                        )
                    ),
                    else_=None,
                )
            )
        ).filter(
            (s.system_id == self.system.system_id) &
            (fd.file_detail_id == None) &
            (func.coalesce(rd.file_info, "") != "directory") &
            (~func.coalesce(rd.file_info, "").startswith("symbolic link"))
        ).distinct()

        result: ResultProxy = query.all()

        return result

    def fetch_modified_rpms(self) -> ResultProxy:

        ri: RpmInfo = aliased(RpmInfo)
        rd: RpmDetail = aliased(RpmDetail)
        fd: FileDetail = aliased(FileDetail)
        rdl: RpmFileDetailLink = aliased(RpmFileDetailLink)
        s: System = aliased(System)

        sub_query = self._session.query(
            rd
        ).join(
            s,
            (s.system_id == rd.system_id),
        ).join(
            rdl,
            (rdl.rpm_detail_id == rd.rpm_detail_id),
        ).outerjoin(
            fd,
            (rdl.file_detail_id == fd.file_detail_id) &
            (
                rd.digest == case(
                    {
                        32: fd.md5_digest,
                        64: fd.sha256_digest,
                    },
                    value=func.length(coalesce(rd.digest, "")),
                    else_=None,
                )
            )
        ).filter(
            (ri.rpm_info_id == rd.rpm_info_id) &
            (fd.file_detail_id == None) &
            (func.coalesce(rd.file_info, "") != "directory") &
            (~func.coalesce(rd.file_info, "").startswith("symbolic link"))
        )

        # fetch RpmInfo's for each RPM with a changed file
        query = self._session.query(
            ri
        ).join(
            System
        ).filter(
            sub_query.exists(),
        ).filter(
            System.system_id == self.system.system_id,
        )

        result: ResultProxy = query.all()

        return result

    def fetch_file_detail_record(self, rpm_detail: RpmDetail) -> FileDetail:

        query = self._session.query(
            FileDetail
        ).join(
            RpmFileDetailLink
        ).join(
            RpmDetail
        ).filter(
            RpmDetail == rpm_detail
        )

        result: FileDetail = query.one()

        return result

    def clear_system_file_storage(self):

        count = self._session.query(
            RpmDetailPatchStorageLink.file_storage_id
        ).filter(
            RpmDetail.system_id == self.system.system_id
        ).delete(
            synchronize_session=False,
        )

        log.debug("clear_system_file_storage_1: %s" % pformat(count))

        count += self._session.query(
            FileDetailStorageLink.file_storage_id
        ).filter(
            FileDetail.system_id == self.system.system_id
        ).delete(
            synchronize_session=False,
        )

        log.debug("clear_system_file_storage_2: %s" % pformat(count))

        self._session.commit()
        log.debug("clear_system_file_storage_3: commited")

        return count

    def _update_origin(
        self,
        file_detail: FileDetail,
        file_origin: FileOrigin
    ):

        file_detail.origin = file_origin.name
        self._session.add(file_detail)

    def store_file_data(
            self,
            file_detail: FileDetail,
            sys_file: typing.BinaryIO,
            new_origin: FileOrigin=None,
    ):

        if sys_file.tell():
            sys_file.seek(0)

        sys_file = FileStorage(
            file_type="C",
            file_data=sys_file.read()
        )

        detail_link = FileDetailStorageLink(
            file_storage=sys_file,
            file_detail=file_detail,
            file_type="C",
        )

        self._session.add_all((
            sys_file,
            detail_link,
        ))

        if new_origin:
            self._update_origin(file_detail, new_origin)

        self._session.flush()
        self._session.commit()

