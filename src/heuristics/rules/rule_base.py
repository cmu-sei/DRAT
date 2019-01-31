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

from base.logger import LogConfig
from typing import List
from base.enums import FileOrigin
from heuristics import heuristic_utils as hutils
from utils.session import State
from db.tables import (
    FileDetail,
    System,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql import (
    update,
)


class RuleBase(object):
    """
    Base class for heuristic rules.

    Defines required methods and logging. All direct database access is
    hidden in this base class - child rules operate only on source file
    system paths.

    Attributes:
        _rule_name: A human-friendly string that names the rule. We'll use this
            for INFO logging.

    """
    _rule_name = None       # Set in child class __init__
    _package_name = 'none'

    def __init__(self):
        self.__init_logger()
        self.__set_session()
        r = hutils.package_installed(self._package_name)
        self._rpm_info = None if len(r) == 0 else r[0]

    def __init_logger(self):
        """
        Factor this out now so it can be replaced by a global application
        logger later on.
        """
        self.logger = LogConfig.get_logger(__name__)

    def __set_session(self):
        """
        Get session from global context
        """
        self._db_session = State.get_db_session()

    def _log(self, message):
        """
        Helper method. Avoids subclasses from having to import logging.
        """
        self.logger.info('Rule: ' + self._rule_name + ' ' + message)

    def _log_start(self):
        self._log('Starting rule execution')

    def _log_stop(self):
        self._log('Stopping (early) rule execution')

    def _log_complete(self):
        self._log('Completed (normal) rule execution')

    def _should_run(self):
        """
        Override to implement logic to decide if the rule should run, based
        on state of target files.
        """
        raise NotImplementedError(
            '_should_run() not implemented on subclass of RuleBase')

    def _run(self):
        """
        Override to do the analysis and change the state of target
        file origins.
        """
        raise NotImplementedError(
            '_run() not implemented on subclass of RuleBase')

    def register(self):
        """
        Override and return the pass when this rule should be fired.
        """
        raise NotImplementedError(
            'register() not implemented on subclass of RuleBase')

    def fire(self):
        self._log('Firing rule')
        if self._should_run():
            self._log('Will run')
            self._run()
        else:
            self._log('Will not run')
        self._log('Finished rule')
        self._log('Unmarked files: %d' % hutils.unknown_count())

    def _mark_as_content(self, path_spec):
        """
        Link file to package and mark origin as package content.

        path_spec can be a file or a directory. We want to match a regex like:
        path_spec + r'|' + pathspec + r'/.*'
        """

        # db query to find matches and populate list of files to mark
        system: System = State.get_system()
        session: Session = State.get_db_session()

        base: List[FileDetail] = session.query(
            FileDetail
        ).filter(
            (FileDetail.system_id == system.system_id)
            & (FileDetail.file_location.like(path_spec))
        ).all()

        dirs: List[FileDetail] = session.query(
            FileDetail
        ).filter(
            (FileDetail.system_id == system.system_id)
            & (FileDetail.file_location.like(path_spec + '/%'))
        ).all()

        files = base + dirs

        for f in files:
            # ...update file_origin for each file.
            update_origin = update(FileDetail).values(
                origin=FileOrigin.PackageContent.name,
                rpm_info_id=self._rpm_info.rpm_info_id
                ).where(
                    FileDetail.file_detail_id == f.file_detail_id
                )
            result = session.execute(update_origin)
            session.flush()
            session.commit()
            self._log(
                'Linked to package '
                + self._package_name + ': ' + f.file_location)
            self._log('Marked as PackageContent ' + f.file_location)

    def _mark_as_other_exe(self, path_spec):
        """
        TODO: Link to 'special' package?

        path_spec can be a file or a directory. We want to match a regex like:
        path_spec + r'|' + pathspec + r'/.*'
        """

        # db query to find matches and populate list of files to mark
        system: System = State.get_system()
        session: Session = State.get_db_session()

        base: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec))
        ).all()

        dirs: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec + '/%'))
        ).all()

        files = base + dirs

        for f in files:
            # update file_origin for each file.
            # ...update file_origin for each file.
            update_origin = update(FileDetail).values(
                origin=FileOrigin.OtherExecutable.name,
                ).where(
                    FileDetail.file_detail_id == f.file_detail_id
                )
            result = session.execute(update_origin)
            session.flush()
            session.commit()
            self._log('Marked as OtherExecutable ' + f.file_location)

    def _mark_as_ephemeral(self, path_spec):
        """
        path_spec can be a file or a directory. We want to match a regex like:
        path_spec + r'|' + pathspec + r'/.*'
        """

        # db query to find matches and populate list of files to mark
        system: System = State.get_system()
        session: Session = State.get_db_session()

        base: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec))
        ).all()

        dirs: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec + '/%'))
        ).all()

        files = base + dirs

        for f in files:
            # update file_origin for each file.
            # ...update file_origin for each file.
            update_origin = update(FileDetail).values(
                origin=FileOrigin.EphemeralContent.name,
                ).where(
                    FileDetail.file_detail_id == f.file_detail_id
                )
            result = session.execute(update_origin)
            session.flush()
            session.commit()
            self._log('Marked as Ephemeral Content ' + f.file_location)

    def _mark_as_user_data(self, path_spec):
        """
        path_spec can be a file or a directory. We want to match a regex like:
        path_spec + r'|' + pathspec + r'/.*'
        """

        # db query to find matches and populate list of files to mark
        system: System = State.get_system()
        session: Session = State.get_db_session()

        base: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec))
        ).all()

        dirs: List[FileDetail] = session.query(
            FileDetail
        ).filter(
          (FileDetail.system_id == system.system_id)
          & (FileDetail.file_location.like(path_spec + '/%'))
        ).all()

        files = base + dirs

        for f in files:
            # update file_origin for each file.
            # ...update file_origin for each file.
            update_origin = update(FileDetail).values(
                origin=FileOrigin.UserData.name,
                ).where(
                    FileDetail.file_detail_id == f.file_detail_id
                )
            result = session.execute(update_origin)
            session.flush()
            session.commit()
            self._log('Marked as UserData ' + f.file_location)
