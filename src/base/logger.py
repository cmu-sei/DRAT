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
import sys
from pathlib import Path, PurePath


class LogConfig(object):
    __log_config = {}

    @classmethod
    def set_log_level(cls, level=logging.INFO):

        if type(level) == str:
            level = level.upper()
            if level == "DEBUG":
                cls.__log_config["sqlalchemy"] = logging.INFO
            elif level == "TRACE":
                cls.__log_config["sqlalchemy"] = logging.DEBUG
                level = "DEBUG"

        log_level = logging.getLevelName(level)

        if type(log_level) == str and log_level.startswith("Level "):
            raise ValueError(
                f"Level {level} is not a legitimate log level"
            )

        cls.__log_config["level"] = log_level

    @classmethod
    def get_log_level(cls):

        if not cls.__log_config.get("level"):
            cls.set_log_level()

        return cls.__log_config["level"]

    @classmethod
    def get_sqlalchemy_level(cls):
        return cls.__log_config.get("sqlalchemy", logging.WARN)

    @classmethod
    def initialize(cls, path: str, level: int=logging.INFO):
        try:
            exe_path = Path(sys.argv[0]).resolve()

            if Path(path).is_absolute():
                path = Path(path)
            elif exe_path.is_dir():
                path = exe_path.joinpath(path)
            else:
                path: Path = exe_path.parent.joinpath(path)

            parent_path: Path = path.parent

            cls.set_log_level(level)

            root = logging.getLogger()

            default_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.formatter = default_formatter

            if not path.parts[-1].endswith(".log"):
                raise ValueError("Log files must end in .log")

            if not parent_path.exists():
                parent_path.mkdir()

            file_handler = logging.FileHandler(filename=path)

            file_handler.formatter = default_formatter

            root.addHandler(stdout_handler)
            root.addHandler(file_handler)

            root.setLevel(cls.get_log_level())

            logging.getLogger(
                "sqlalchemy.engine"
            ).setLevel(
                cls.get_sqlalchemy_level()
            )
        except Exception as e:
            print(
                "Error initializing logger.  Unable to create logging.",
                file=sys.stderr
            )
            print("Exception: %s" % str(e), file=sys.stderr)
            raise

    @classmethod
    def get_logger(cls, name):
        lg = logging.getLogger(name)
        lg.addHandler(logging.NullHandler())

        return lg
