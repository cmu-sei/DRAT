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


from __future__ import print_function
from pprint import pprint
import sys
import os
import pwd
import base64

try:
    from subprocess import run
except ImportError:
    import subprocess

    def run(*cmd, timeout=300):
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
        )

        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            out = err = b""

        return proc.returncode, out


UID_START = 1000
CHUNK_SIZE = 8192

try:
    OUT_FILE = sys.argv[1]
except IndexError:
    print("Please pass the output filename as the first parameter.")
    raise SystemExit(2)

if os.path.exists(OUT_FILE):
    print("File %s already exists; will not overwrite." % OUT_FILE)
    raise SystemExit(1)

with open(OUT_FILE, 'wb') as f:

    for pwd in pwd.getpwall():
        if pwd.pw_uid < UID_START:
            continue

        print("Processing user %s." % pwd.pw_name)

        f.write(
            (
                "%d\t%s\t%s\t" % (
                    pwd.pw_uid,
                    pwd.pw_name,
                    pwd.pw_dir,
                )
            ).encode()
        )

        pprint(pwd)

        dot_files = [
            ".profile",
            ".bash_profile",
            ".bashrc",
        ]

        for file in dot_files:
            dot_file = "%s/%s" % (pwd.pw_dir, file)

            if os.path.exists(dot_file):
                with open(dot_file, "rb") as p:
                    while True:
                        chunk = p.read(CHUNK_SIZE - CHUNK_SIZE % 3)
                        if not chunk:
                            break
                        f.write(base64.b64encode(chunk))
            f.write(b"\t")

        f.seek(-1, 2)
        f.write(b"\n")
