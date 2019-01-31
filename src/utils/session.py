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

from psycopg2 import Error as PsycopgError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from db.tables import make_engine, System
from utils import ssh
from paramiko import SSHClient


class StateException(Exception):
    pass


class NoSystemState(StateException):
    pass


class NoSshSessionState(StateException):
    pass


class State(object):
    __state = {}

    @staticmethod
    def get_db_session() -> Session:
        if (
            "session" not in State.__state or
            State.__state["session"] is None
        ):
            State.__state["session"] = sessionmaker(bind=make_engine())()

        return State.__state.get("session")

    @staticmethod
    def get_ssh_session(**kwargs) -> ssh.SshConnector:
        if not kwargs:
            if not "ssh_session" in State.__state:
                raise NoSshSessionState(
                    "You must pass in arguments to connect to the system"
                )

            return State.__state.get("ssh_session")

        hostname = kwargs.get("hostname")
        username = kwargs.get("username")
        port = kwargs.get("port", 22)
        key_file = kwargs.get("key_file")

        if not hostname:
            raise NoSshSessionState(
                "You must pass in \"hostname\" to connect to the system"
            )

        connector = State.__state["ssh_session"] = ssh.SshConnector(
            hostname=hostname,
            username=username,
            port=port,
            key_file=key_file
        )
        return State.get_ssh_session()


    @staticmethod
    def get_system(**kwargs):

        gather = kwargs.get("gather", False)

        if not kwargs:
            if not State.__state.get("system"):
                raise NoSystemState("You must specify a system to load")
        else:

            system = None

            try:
                session = State.get_db_session()

                id = kwargs.get("id")
                name = kwargs.get("name")

                if id:
                    system = session.query(
                        System
                    ).filter_by(
                        system_id=id
                    ).one()
                else:
                    system = session.query(
                        System
                    ).filter_by(
                        name=name
                    ).one()

            except NoResultFound as e:
                if not gather:
                    raise NoSystemState(
                        "System could not be loaded from the database"
                    ) from e

            State.__state["system"] = system

        return State.__state.get("system")

    @staticmethod
    def startup(**kwargs):
        ssh_session = None
        action = kwargs.pop("action")

        if not action:
            raise SystemExit("Null action, unable to start;.", 1)

        action_kwargs = kwargs.pop("action_kwargs", {})
        ssh_kwargs = kwargs.pop("ssh_kwargs", {})

        db_session = State.get_db_session()

        try:
            if ssh_kwargs:
                with State.get_ssh_session(**ssh_kwargs) as sess:
                    action(**action_kwargs)
            else:
                action(**action_kwargs)

            db_session.commit()
        except Exception as e:
            try:
                db_session.rollback()
            except (SQLAlchemyError, PsycopgError):
                pass
            raise
        finally:
            try:
                db_session.close()
            except (SQLAlchemyError, PsycopgError):
                pass
