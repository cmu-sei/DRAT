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

'''
This module is used to extract data from RPMs and the RPM tables in
the database.
'''

import sys
import subprocess
import os
from pprint import pprint


class RpmException(Exception):
    '''
    This is the base exception class for this RPM module.
    '''
    def __init__(self, *arg):
        super(Exception, self).__init__(*arg)
        self.arg = arg


class RpmFileErrorException(RpmException):
    '''
    This exception class is raised if the contents of the RPM file
    cannot be dumped.
    '''
    def __init__(self, *arg):
        super(RpmException, self).__init__(*arg)
        self.arg = arg


class Rpm(object):
    '''
    This class extracts data from the given RPM and compares it to
    a specific system stored in the database.
    '''
    __rpm_headers = (
        'name',
        'size',
        'date',
        'digest',
        'mode',
        'owner',
        'group',
    )

    '''
    Checks database to see if rpm exists in the system
    '''

    def __init__(self, system_id=None, filename=None, session=None):

        if not system_id:
            raise ValueError('Need system_id to compare rpm.')

        if not session:
            raise ValueError('Missing database session.')

        if not filename:
            raise ValueError('Requires the filename of an RPM.')

        self.system_id = system_id
        self.filename = filename
        self.session = session

    def _extract_detail(self):

        with open(os.devnull, 'w') as devnull:
            try:
                output = subprocess.check_output([
                    'rpm',
                    '-qlp',
                    '--dump',
                    self.filename,
                ], stderr=devnull)

            except subprocess.CalledProcessError as ex:
                raise (
                    RpmFileErrorException(str(ex)),
                    ex.args,
                    sys.exc_info()[2],
                )

        return output

    def _parse_output(self, output=None):

        rows = output.split('\n')

        parsed_output = {}

        for row in rows:
            result = dict(zip(self.__rpm_headers, row.split(' ')))
            if len(result) != len(self.__rpm_headers):
                continue

            if (
                    result['digest'] == '0' * 32 or
                    result['digest'] == '0' * 64
            ):
                result['digest'] = None

            parsed_output[result['name']] = result

        return parsed_output

    def _fetch_details(self, details=None):

        rpm_detail = None

        for detail in details.values():
            rpm_detail = self.session.query(t.RpmDetail).filter_by(
                system_id=self.system_id,
                file_location=detail['name']
            ).first()

            if rpm_detail:
                break

        if not rpm_detail:
            print('Unable to find any matching RPM files in db.')
            return None

        rpm_info = rpm_detail.rpm_info

        for rpm_detail in rpm_info.rpm_details:
            a_rpm = details.get(rpm_detail.file_location, None)
            pprint('a_rpm:', stream=sys.stderr)
            pprint(a_rpm, stream=sys.stderr)

            if not a_rpm or a_rpm['digest'] != rpm_detail.digest:
                pprint('unable to match file.', stream=sys.stderr)
                return False

        return True

    def get_rpm_match(self):
        '''
        Take the RPM file from the constructor and compare it to
        known RPM files in the PostgreSQL RPM database.
        '''
        rpm_output = self._extract_detail()
        rpm_details = self._parse_output(output=rpm_output)
        return self._fetch_details(details=rpm_details)
