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

from datetime import datetime
from api.remote import RpmHandler
from sqlalchemy.orm import sessionmaker, Session
from db.tables import make_engine, FileStorage, RpmDetailPatchStorageLink
from db.analysis import FileDifference
from base.exceptions import RpmNotFound
from utils import generate_alt_rpm_filenames
from sys import stderr
from os.path import splitext
from heuristics import is_file_excluded
from utils.ssh import SSHRunException
from io import BytesIO
import itertools


session: Session = sessionmaker(bind=make_engine())()

x = FileDifference(system_id=1, session=session)

xxx = x.fetch_modified_rpms()

if not xxx:
    raise SystemExit(1)

with CreatePatchFileFromRemoteHost(
    hostname='localhost',
    username='vagrant',
    port=2222,
    exec_path='./'
) as host:

    for rpm in xxx:
        print(
            f'{rpm.name} id # {rpm.rpm_info_id} ',
            flush=True)

        modified_files = x.fetch_modified_files(rpm_info_id=rpm.rpm_info_id)



        rpm_files = {mod.rpm_detail_id: mod for mod in modified_files
                     if not is_file_excluded(mod.file_location)}

        file_details = {}

        for rpm_detail_id, rpm_file in list(rpm_files.items()):
            detail = x.fetch_file_detail_record(rpm_detail_id)
            if (
                detail and
                detail.file_info and
                detail.file_info .startswith('text/')
            ):
                file_details[rpm_detail_id] = detail
            else:
                del rpm_files[rpm_detail_id]

        if not rpm_files:
            print(
                f'{rpm.filename} does not contain any valid files',
            )
            continue

        file_results = {}
        file_detail = {}

        for name_permutation in generate_alt_rpm_filenames(rpm.filename):
            try:
                print(f'  {name_permutation}..')
                rpm_handler.set_rpm_name(name_permutation)
                file_results = rpm_handler.fetch_files_from_rpm(*[
                    f.file_location for f in rpm_files.values()
                ])
            except RpmNotFound:
                continue

            break

        if file_results:
            for id, file in rpm_files.items():
                abs_path = file.file_location
                result = file_results.get(abs_path)
                print(f'    {abs_path} patch.', flush=True)
                patch = BytesIO()

                try:
                    for line in host.get_patch(
                            abs_path,
                            patch,
                            result,
                    ):
                        print(line, end='')
                except:
                    raise

                print(f'got patch for {abs_path}')

                patch_rec = FileStorage(patch_data=patch.read(-1))

                patch_link = RpmDetailPatchStorageLink(
                    patch=patch_rec,
                    rpm_detail=file,
                )

                session.add_all((
                    patch_rec,
                    patch_link
                ))
                session.flush()

        else:
            print(f'rpm {rpm.filename} not found.')

    session.commit()
