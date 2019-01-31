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


import os
import sys
import timeit

import db.tables as t
from base.reflection import InstalledRpmInfo
from db.storage import StorePackageResults
import utils.os
from utils.time import seconds_to_minutes_with_seconds


def main():

    try:
        exec_path = os.path.realpath(os.path.expanduser(__file__))
    except NameError:
        exec_path = os.path.realpath(os.path.expanduser(sys.argv[0]))

    exec_path = os.path.dirname(exec_path)

    if exec_path[-1] != os.path.sep:
        exec_path += os.path.sep

    args = utils.os.GetGatherArguments().parse()

    with InstalledRpmInfo(
        hostname=args.hostname or args.name,
        username=args.username or os.getlogin(),
        key_file=args.key_file,
        port=args.port,
        exec_path=exec_path,
        tty=args.tty,
    ) as rpm_info:
        with StorePackageResults(gather=True) as store_results:

            info = rpm_info.get_host_info()
            os_info = rpm_info.get_os_info()
            system = store_results.store_system_info(
                name=args.name,
                hostname=args.hostname or args.name,
                port=args.port,
                username=args.username or os.getlogin(),
                key_file=args.key_file,
                use_tty=args.tty,
                **{**info, **os_info}
            )

            if args.insert_only:
                print("Exiting after system insert")
                return

            sf = timeit.default_timer()

            with open(f'{system.name}_files.txt', 'w') as f:
                for line in rpm_info.get_files():
                    f.write(line)

            ef = timeit.default_timer()

            elapsed_f = seconds_to_minutes_with_seconds(sf, ef)

            print(
                f'Time to gather files was {elapsed_f["minutes"]} '
                f'minutes and {elapsed_f["seconds"]} seconds.'
            )

            s = timeit.default_timer()

            with open(f'{system.name}_packages.txt', 'w') as f:
                for line in rpm_info.get_packages():
                    f.write(line)

            e = timeit.default_timer()

            elapsed_r = seconds_to_minutes_with_seconds(s, e)

            print(
                f'Time to gather rpms was {elapsed_r["minutes"]} '
                f'minutes and {elapsed_r["seconds"]} seconds.'
            )


if __name__ == '__main__':

    main()
