#!/usr/bin/env python3
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


from sqlalchemy.orm.exc import NoResultFound
from base.logger import LogConfig
import utils.os
from utils.session import State, NoSystemState
from db.tables import System
from base.iac import AnsibleInfrastructureAsCodeGenerator

log = LogConfig.get_logger(__name__)


def main(args=None, name: System=None):
    log.info("Starting iac_create.py")
    log.info(f"Generating Ansible yaml for {args.name}.")
    iac = AnsibleInfrastructureAsCodeGenerator(
        prune=args.prune,
        output_dir=args.output_dir,
        system=name,
    )
    iac.create()


if __name__ == '__main__':
    try:
        arguments = utils.os.GetIaCArguments().parse()
        LogConfig.initialize(
            path="logs/create_iac.log",
            level=arguments.log_level,
        )

        system: System = State.get_system(name=arguments.name)

        State.startup(
            action=main,
            action_kwargs={
                "args": arguments,
                "name": system,
            },
        )

    except NoSystemState as e:
        log.fatal(
            f"System is probably not "
            "loaded into the database.",
            exc_info=e,
        )

        raise SystemExit(2) from e

    except Exception as e:

        log.fatal("Unknown Fatal exception", exc_info=e)
        raise SystemExit(1) from e
