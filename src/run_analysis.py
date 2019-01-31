#!/usr/bin/env python
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


from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.exc import NoResultFound
from base.exceptions import ApiExceptionBase
from base.logger import LogConfig
from utils.ssh import SshConnector
from db.tables import (
    make_engine,
    System,
    FileDetail,
    RpmInfo,
)
from base.reflection import GetModifiedFilesFromRemoteHost
import run_rules
import utils.os
from utils.session import State

log = LogConfig.get_logger(__name__)


def main(args):

    # Find modified files and make a patch to create
    # the new file.

    fetch_files = GetModifiedFilesFromRemoteHost(
        handler_route="http://localhost:5001/api",
    )

    fetch_files.process_modified_packages()

    # All of the pattern matching, etc. has been pushed down into the rules
    run_rules.main()

    fetch_files.process_user_content()


if __name__ == '__main__':
    try:
        arguments = utils.os.GetMinimumSshArguments().parse()

        LogConfig.initialize(
            path="logs/run_analysis.log",
            level=arguments.log_level
        )

        system: System = State.get_system(name=arguments.name)

        State.startup(
            action=main,
            action_kwargs={
                "args": arguments
            },
            ssh_kwargs={
                "hostname": system.hostname,
                "port": system.port,
                "username": system.username,
                "key_file": system.key_file,
            },
        )

    except ApiExceptionBase as e:
        log.fatal(
            f"Error accessing API: {e}"
        )

    except NoResultFound as e:

        log.fatal(
            f"System is probably not "
            "loaded into the database.",
            exc_info=True
        )

        raise SystemExit(2) from e

    except Exception as e:

        log.fatal("Unknown Fatal exception", exc_info=True)
        raise SystemExit(1) from e
