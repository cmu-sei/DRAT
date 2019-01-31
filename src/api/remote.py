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

from typing import List, Dict, Optional, BinaryIO
import requests
from requests.exceptions import HTTPError
import json
from base64 import b64decode
from io import BytesIO, FileIO
from os.path import basename, splitext
from base.exceptions import (
    RpmNotFound,
    FatalError,
    ConflictNumerousPackagesFound,
)


class RpmHandler(object):

    """
    Class fetches RPMs from the remote
    """

    def __init__(self, route: str, rpm_name: str = None):
        url_build: List[str] = [route, 'fetch']

        if not route.endswith('/'):
            url_build.insert(1, '/')

        self._base_route: str = ''.join(url_build)
        self._route: str = None

        self._rpm_name: str = None
        self._base_rpm_name: str = None

        if rpm_name:
            self.set_rpm_name(rpm_name)

    def set_rpm_name(self, rpm_name: str):
        if not rpm_name:
            raise ValueError('rpm_name string is null or empty')

        self._rpm_name = basename(rpm_name)
        if self._rpm_name.lower().endswith('.rpm'):
            self._base_rpm_name = splitext(self._rpm_name)[0]
        else:
            self._base_rpm_name = self._rpm_name

        self._route = f'{self._base_route}/{self._base_rpm_name}'

    def fetch_files_from_rpm(
            self,
            *filenames: str
    ) -> Dict[str, Optional[BinaryIO]]:

        params = {'file': filenames}
        resp = requests.get(self._route, params=params)

        try:
            resp.raise_for_status()
        except HTTPError as ex:
            if ex.response.status_code == 404:
                raise RpmNotFound(
                    f"{ex.response}: {ex.response.content}"
                ) from ex
            elif ex.response.status_code == 409:
                raise ConflictNumerousPackagesFound(
                    f"{ex.response}: {ex.response.content}"
                ) from ex
            else:
                raise FatalError(
                    f"{ex.response}: {ex.response.content}"
                ) from ex

        payload = resp.json()

        result = {}

        for file in filenames:
            encoded_data = payload.get(file, None)
            if not encoded_data:
                result[file] = BytesIO(b"")
            else:
                result[file] = self._base64_to_bytesio(encoded_data)

        return result

    def fetch_file_from_rpm(self, filename: str) -> Optional[BinaryIO]:
        if not filename:
            raise ValueError('filename string is null or empty')

        result = self.fetch_files_from_rpm(filename)

        if result:
            return result.get(filename, None)
        else:
            return BytesIO(b"")

    def _base64_to_bytesio(self, base64_data: str) -> Optional[BinaryIO]:

        if base64_data:
            bytes = b64decode(base64_data)
            return BytesIO(bytes)
        else:
            return None
