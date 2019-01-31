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

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    Integer,
    String,
    BigInteger,
    DateTime,
    Table,
    MetaData,
    LargeBinary,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
    Index,
    ForeignKey,
    PrimaryKeyConstraint
)
from sqlalchemy.schema import DDL


Base = declarative_base()

engine_uri = 'postgresql+psycopg2://iac:ia-code@%s:%s/iacode'


def get_db_uri():

    """
    Set this environment variable in the Dockerfile or docker-compose.yml to use the
    Docker user-defined network to reach the database.
    """

    pg_host = os.environ.get(
        "PGHOSTADDR",
        os.environ.get(
            "PGHOST",
            "localhost")
    )
    pg_port = os.environ.get("PGPORT", "5432")
    is_docker = os.environ.get("DOCKER")

    engine = "localhost"

    if is_docker:
        engine = "db"
    else:
        engine = pg_host

    return engine_uri % (engine, pg_port)


def make_engine():

    return create_engine(get_db_uri())


class System(Base):

    schema = 'iac'
    __tablename__ = 'systems'

    system_id = Column(Integer, primary_key=True)
    name = Column(String(length=128), nullable=False)
    hostname = Column(String(length=253), nullable=False)
    username = Column(String(length=32))
    key_file = Column(String(length=4096))
    port = Column(Integer, default=22, nullable=False)
    use_tty = Column(
        Boolean,
        default=False,
        server_default='f',
        nullable=False,
    )
    remote_name = Column(String(length=128), nullable=False)
    os_distro = Column(String(length=24))
    os_major_ver = Column(Integer)
    os_minor_ver = Column(Integer)
    os_revision = Column(Integer)
    kernel_version = Column(String(length=256))

    __table_args__ = (
        UniqueConstraint(
            'name',
            name='{}_u01'.format(__tablename__)
        ),
    )

    def __repr__(self):
        return (
            '<System(system_id="{}", name="{}", remote_name="{}", '
            'kernel_version="{}", os_distro="{}", os_major_ver="{}", '
            'os_minor_ver="{}")>'
        ).format(
            self.system_id,
            self.name,
            self.remote_name,
            self.kernel_version,
            self.os_distro,
            self.os_major_ver,
            self.os_minor_ver,
        )


class RpmInfo(Base):

    schema = 'iac'
    __tablename__ = 'rpm_info'

    rpm_info_id = Column(Integer, primary_key=True)
    name = Column(String(48), nullable=False)
    version = Column(String(24))
    release = Column(String(128))
    architecture = Column(String(24))
    filename = Column(String(256))
    installation_tid = Column(Integer)
    installation_date = Column(
        DateTime(timezone=True),
    )
    system_id = Column(
        Integer,
        ForeignKey('systems.system_id'),
        nullable=False,
    )

    system = relationship(
        'System',
        back_populates='rpms',
    )

    __table_args__ = (
        UniqueConstraint(
            'system_id',
            'name',
            'version',
            'architecture',
            name='{}_u01'.format(__tablename__)
        ),
        Index(
            '{}_i01'.format(__tablename__),
            'installation_tid',
        )
    )

    def __repr__(self):
        return (
            '<RpmInfo(rpm_info_id="{}", name="{}", version="{}", '
            'release="{}", filename="{}", system_id="{}")>'.format(
                self.rpm_info_id,
                self.name,
                self.version,
                self.release,
                self.filename,
                self.system_id,
            )
        )


System.rpms = relationship(
    'RpmInfo',
    back_populates='system',
)


class RpmDetail(Base):

    schema = 'iac'
    __tablename__ = 'rpm_detail'

    rpm_detail_id = Column(BigInteger, primary_key=True)
    rpm_info_id = Column(
        Integer,
        ForeignKey('rpm_info.rpm_info_id'),
        nullable=False
    )

    system_id = Column(
        Integer,
        ForeignKey('systems.system_id'),
        nullable=False,
    )

    file_location = Column(String(length=256))
    file_size = Column(BigInteger)
    digest = Column(String(length=64))
    file_info = Column(String(length=1024))
    file_flag = Column(String(length=64))
    file_changed = Column(Boolean())
    file_exists = Column(Boolean())

    rpm_info = relationship(
        'RpmInfo',
        back_populates='rpm_details',
    )

    system = relationship(
        'System',
        back_populates='rpm_details',
    )

    def __repr__(self):
        return (
            '<RpmDetail(rpm_detail_id="{}", rpm_info_id="{}", '
            'file_location="{}", file_size="{}", digest="{}", '
            'file_info="{}", file_flag="{}")>'.format(
                self.rpm_detail_id,
                self.rpm_info_id,
                self.file_location,
                self.file_size,
                self.digest,
                self.file_info,
                self.file_flag,
            )
        )

    __table_args__ = (
        Index(
            '{}_i01'.format(__tablename__),
            'system_id',
            'file_location',
        ),
        Index(
            '{}_i02'.format(__tablename__),
            'rpm_info_id',
        ),
        Index(
            '{}_i03'.format(__tablename__),
            'system_id',
        ),
    )


RpmInfo.rpm_details = relationship(
    'RpmDetail',
    back_populates='rpm_info',
)


System.rpm_details = relationship(
    'RpmDetail',
    back_populates='system',
)


class FileDetail(Base):

    schema = 'iac'
    __tablename__ = 'file_detail'

    file_detail_id = Column(BigInteger, primary_key=True)

    system_id = Column(
        Integer,
        ForeignKey('systems.system_id'),
        nullable=False,
    )

    system = relationship(
        'System',
        back_populates='file_details',
    )

    file_location = Column(String(1024), nullable=False)
    file_type = Column(String(1), nullable=False)
    owner_uid = Column(Integer, nullable=False)
    owner_gid = Column(Integer, nullable=False)
    owner_name = Column(String(32))
    owner_group = Column(String(32))
    file_mode = Column(String(6))
    file_perm_mode = Column(String(6))
    file_target = Column(String(1024))
    target_type = Column(String(1))
    file_info = Column(String(1024))
    md5_digest = Column(String(32))
    sha256_digest = Column(String(64))
    origin = Column(String(20))
    fetch_file = Column(Boolean)
    rpm_info_id = Column(
        BigInteger,
        ForeignKey("rpm_info.rpm_info_id"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "system_id",
            "file_location",
            name="{}_u01".format(__tablename__)
        ),
        Index(
            "{}_i01".format(__tablename__),
            "file_type",
        ),
        Index(
            "{}_i02".format(__tablename__),
            "system_id",
        ),
        Index(
            "%s_i03" % __tablename__,
            "origin",
        ),
    )

    def __repr__(self):
        return (
            '<FileDetail('
            'file_detail_id="%s", '
            'system_id="%s", '
            'file_location="%s", '
            'file_type="%s", '
            'owner_uid="%s", '
            'owner_gid="%s", '
            'owner_name="%s", '
            'owner_group="%s", '
            'file_mode="%s", '
            'file_perm_mode="%s", '
            'file_target="%s", '
            'target_type="%s", '
            'file_info="%s", '
            'md5_digest="%s", '
            'sha256_digest="%s", '
            'origin="%s", '
            'fetch_file="%s"'
            'rpm_info_id="%s'
            ')>' % (
                self.file_detail_id,
                self.system_id,
                self.file_location,
                self.file_type,
                self.owner_uid,
                self.owner_gid,
                self.owner_name,
                self.owner_group,
                self.file_mode,
                self.file_perm_mode,
                self.file_target,
                self.target_type,
                self.file_info,
                self.md5_digest,
                self.sha256_digest,
                self.origin,
                self.fetch_file,
                self.rpm_info_id,
            )
        )


System.file_details = relationship(
    'FileDetail',
    back_populates='system'
)


class RpmFileDetailLink(Base):
    """
    Links the rpm_detail and the file_detail tables together
    """
    schema = 'iac'
    __tablename__ = 'rpm_file_detail_link'

    rpm_file_detail_link_id = Column(BigInteger, primary_key=True)
    file_detail_id = Column(
        BigInteger,
        ForeignKey('file_detail.file_detail_id'),
        nullable=False
    )
    rpm_detail_id = Column(
        BigInteger,
        ForeignKey('rpm_detail.rpm_detail_id'),
        nullable=False
    )

    file_detail = relationship(
        'FileDetail',
        back_populates='rpm_detail_link'
    )

    rpm_detail = relationship(
        'RpmDetail',
        back_populates='file_detail_link'
    )

    __table_args__ = (
        UniqueConstraint(
            'file_detail_id',
            'rpm_detail_id',
            name='{}_u01'.format(__tablename__)
        ),
        Index(
            '{}_i01'.format(__tablename__),
            'rpm_detail_id',
        ),
    )

    def __repr__(self):
        return (
            '<RpmFileDetailLink('
            'rpm_file_detail_link_id="{}", '
            'file_detail_id="{}", '
            'rpm_detail_id="{}"'
            ')>'.format(
                self.rpm_file_detail_link_id,
                self.file_detail_id,
                self.rpm_detail_id
            )
        )


FileDetail.rpm_detail_link = relationship(
    'RpmFileDetailLink',
    back_populates='file_detail'
)

RpmDetail.file_detail_link = relationship(
    'RpmFileDetailLink',
    back_populates='rpm_detail'
)


class FileStorage(Base):
    """
    Table contains patches and configuration files needed
    to recreate specific files from the
    default configuration.
    """

    schema = 'iac'
    __tablename__ = 'file_storage'

    id = Column(BigInteger, primary_key=True)
    file_type = Column(String(1), default="P", nullable=False)
    file_data = Column(LargeBinary)

    __table_args__ = (
        CheckConstraint(
            "file_type in ('P', 'C', 'B')",
            name='{}_c01'.format(__tablename__),
        ),
    )

    def __repr__(self):
        return (
            '<FileStorage('
            'id="{}", '
            'file_data="{}"'
            ')>'.format(
                self.id,
                self.file_data,
            )
        )


class RpmDetailPatchStorageLink(Base):
    """
    Table links RpmDetail records to their associated patches
    """
    schema = 'iac'
    __tablename__ = 'rpm_detail_patch_storage_link'

    id = Column(BigInteger, primary_key=True)

    file_storage_id = Column(
        Integer,
        ForeignKey(
            "file_storage.id",
            ondelete="CASCADE",
        )
    )
    rpm_detail_id = Column(Integer, ForeignKey('rpm_detail.rpm_detail_id'))

    __table_args__ = (
        UniqueConstraint(
            'file_storage_id',
            'rpm_detail_id',
            name='{}_u01'.format(__tablename__)
        ),
    )

    rpm_detail = relationship(
        "RpmDetail",
        back_populates="rpm_patch_link",
    )
    file_storage = relationship(
        "FileStorage",
        back_populates="rpm_patch_link",
    )

    def __repr__(self):
        return (
            '<RpmDetailPatchStorageLink('
            'id="{}", '
            'file_storage_id="{}", '
            'rpm_detail_id="{}"'
            ')>'.format(
                self.id,
                self.file_storage_id,
                self.rpm_detail_id,
            )
        )


RpmDetail.rpm_patch_link = relationship(
    "RpmDetailPatchStorageLink",
    back_populates="rpm_detail",
)

FileStorage.rpm_patch_link = relationship(
    "RpmDetailPatchStorageLink",
    back_populates="file_storage",
)


class FileDetailStorageLink(Base):
    """
    Table links FileDetail records to files
    """
    schema = "iac"
    __tablename__ = "file_detail_storage_link"

    id = Column(
        BigInteger,
        primary_key=True,
        comment="Primary key for FileDetailStorageLink",
    )

    file_storage_id = Column(
        Integer,
        ForeignKey(
            "file_storage.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="Foreign key to file_storage.file_storage_id",
    )
    file_detail_id = Column(
        Integer,
        ForeignKey(
            "file_detail.file_detail_id"
        ),
        nullable=False,
        comment="Foreign key to file_detail.file_detail_id",
    )

    # O=Original from Rpm; C=Current File
    file_type = Column(
        String(1),
        nullable=False,
        comment=(
            "Specifies file type; O=Original from rpm, "
            "C=Current from system."
        ),
    )

    __table_args__ = (
        UniqueConstraint(
            "file_storage_id",
            "file_detail_id",
            "file_type",
            name="{}_u01".format(__tablename__)
        ),
        CheckConstraint(
            "file_type in ('O', 'C')",
            name="{}_c01".format(__tablename__),
        ),
    )

    file_detail = relationship(
        "FileDetail",
        back_populates="file_detail_storage_link",
    )

    file_storage = relationship(
        "FileStorage",
        back_populates="file_detail_storage_link",
    )

    def __repr__(self):
        return (
            "<FileDetailStorageLink("
            "id='%d', "
            "file_storage_id='%d', "
            "file_detail_id='%d', "
            "file_type='%s'"
            ")>" % (
                self.id,
                self.file_storage_id,
                self.file_detail_id,
                self.file_type,
            )
        )


FileDetail.file_detail_storage_link = relationship(
    "FileDetailStorageLink",
    back_populates="file_detail",
)

FileStorage.file_detail_storage_link = relationship(
    "FileDetailStorageLink",
    back_populates="file_storage",
)


class ApplicationData(Base):
    """
    JSONB Document storage table used to store generic
    application data.  Since each application is a bit
    different, schema-less data make more sense.
    """

    schema = "iac"
    __tablename__ = "app_infomation"

    app_id = Column(BigInteger, primary_key=True)
    system_id = Column(
        Integer,
        ForeignKey('systems.system_id'),
        nullable=False,
    )

    system = relationship(
        'System',
        back_populates='app_data_link',
    )

    doc = Column(JSONB)


System.app_data_link = relationship(
    'ApplicationData',
    back_populates='system'
)


#class SystemServices(Base):
#    """
#    Table contains the list of defined system services and their start up
#    status
#    """
#
#    schema = "iac"
#    __tablename__ = "system_services"
#
#    service_id = Column(Integer, primary_key=True)
#    system_id = Column(
#        Integer,
#        ForeignKey("systems.system_id"),
#        nullable=False,
#    )
#    file_detail_id = Column(
#        BigInteger,
#        ForeignKey
#     )
#
#    unit_file = Column(String(128), nullable=False)
#    state = Column(String(12))
#
#    system = relationship(
#        "System",
#        back_populates="services"
#    )
#
#
#System.services = relationship(
#    "SystemServices",
#    back_populates="system"
#)

