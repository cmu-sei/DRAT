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

import warnings
import sqlalchemy.exc

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
        MetaData,
        Table,
        Column,
        Integer,
        BigInteger,
        ForeignKey,
        PrimaryKeyConstraint,
)

from .tables import make_engine


Base = declarative_base()
metadata = MetaData()


class ResolvedSymlinksView(Base):
    """
    db view loaded from database metadata.
    Resolves file symlinks
    """
    schema = "iac"
    __table__ = Table(
        "resolved_symlinks_vw",
        metadata,
        Column(
            "system_id",
            Integer,
            ForeignKey("systems.system_id"),
        ),
        Column(
            "file_detail_id",
            BigInteger,
            ForeignKey("file_detail.file_detail_id")
        ),
        PrimaryKeyConstraint(
            "system_id",
            "file_detail_id"
        ),
        autoload=True,
        autoload_with=make_engine(),
    )

    def __repr__(self):
        return (
            "<ResolvedSymlinksView("
            "system_id=\"{}\", "
            "file_detail_id=\"{}\""
            ")>".format(
                self.system_id,
                self.file_detail_id,
            )
        )


with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=(
            "Skipped unsupported reflection of expression-based "
            "index resolved_symlinks_f01"
        ),
        category=sqlalchemy.exc.SAWarning,
    )

    class ResolvedSymlinks(Base):
        """
        db view loaded from database metadata.
        Resolves file symlinks
        """
        schema = "iac"
        __table__ = Table(
            "resolved_symlinks",
            metadata,
            Column(
                "system_id",
                Integer,
                ForeignKey("systems.system_id"),
            ),
            Column(
                "file_detail_id",
                BigInteger,
                ForeignKey("file_detail.file_detail_id")
            ),
            PrimaryKeyConstraint(
                "system_id",
                "file_detail_id"
            ),
            autoload=True,
            autoload_with=make_engine(),
        )

        def __repr__(self):
            return (
                "<ResolvedSymlinks("
                "system_id=\"{}\", "
                "file_detail_id=\"{}\""
                ")>".format(
                    self.system_id,
                    self.file_detail_id,
                )
            )


