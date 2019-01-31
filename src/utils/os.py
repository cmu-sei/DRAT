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

import argparse


class GetArguments(object):
    """
    This class gets the command-line parameters and returns them to
    the application
    """

    def __init__(self):
        self._parser = argparse.ArgumentParser()

        self.base_args()
        self.add_args()

    def base_args(self):

        self._parser.add_argument("name", type=str,
                                  help="Name of host to analyse")

        log_choices = [
            "info",
            "fatal",
            "error",
            "warn",
            "debug",
            "trace",
        ]

        self._parser.add_argument(
            "-l",
            "--log-level",
            type=str,
            dest="log_level",
            choices=log_choices,
            default=log_choices[0],
            help="Set default log level to capture",
        )

    def add_args(self):
        pass

    def parse(self) -> argparse.Namespace:
        return self._parser.parse_args()


class GetIaCArguments(GetArguments):
    """
    Adds arguments for outputting IaC code
    """
    def add_args(self):
        self._parser.add_argument(
            "-o",
            "--output-dir",
            dest="output_dir",
            help="Specify output directory of IaC code",
            metavar="{exe_path}/output/",
            required=True,
            type=str,
        )

        self._parser.add_argument(
            "--prune",
            dest="prune",
            help="Remove output directory before creating new IaC code",
            default=False,
            action="store_true",
        )


class GetMinimumSshArguments(GetArguments):
    """
    Added custom parameters
    """
    def add_args(self):
        self._parser.add_argument(
            '-k', '--key-file', dest='key_file',
            help='Private key file to use while connecting to the host'
        )

        self._parser.add_argument(
            '-u', '--user-name', dest='username', type=str,
            help='Username to use when connecting to the host'
        )
        self._parser.add_argument(
            "--tty",
            default=False,
            action="store_true",
            help="Allocate tty where needed",
        )


class GetSshArguments(GetMinimumSshArguments):
    """
    Added custom parameters
    """
    def add_args(self):
        super().add_args()
        self._parser.add_argument(
            "-n",
            "--node-name",
            dest="hostname",
            help="System common name",
            type=str,
        )

        self._parser.add_argument(
            '-p', '--port', dest='port', type=int,
            default=22,
            help='SSH port to use'
        )


class GetGatherArguments(GetSshArguments):
    """
    Added an add system only option
    """
    def add_args(self):
        super().add_args()

        self._parser.add_argument(
            "--insert-system-only",
            dest="insert_only",
            help="Insert system into Systems and exit",
            default=False,
            action="store_true",
        )
