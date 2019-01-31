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
from sys import stderr
from os import unlink
from os.path import isfile
import tempfile
import yum
from shutil import rmtree
from base64 import b64encode
import subprocess


class YumWrapper(yum.YumBase):

    """
    Wrapper around yum
    """
    cache_dir = '/data/yum'

    def __init__(self):
        yum.YumBase.__init__(self)

        self.resolve_name = resolve_name

        self.conf.downloadonly = True

        if not self.setCacheDir(force=True, reuse=True, tmpdir=self.cache_dir):
            raise IOError(
                'Yum Cache directory, {}, does not exist.'.format(
                    self.cache_dir
                )
            )

    def find_package(self, *pkg_name):

        pl = self.pkgSack.returnPackages(patterns=pkg_name)
        em, mat, unmat = yum.packages.parsePackages(pl, pkg_name)

        return em

    def get_cache_locations(self, pkg_objs):

        result = {}

        for po in pkg_objs:

            name = self.resolve_name(po)
            result[name] = po.localPkg()

        return result

    def fetch_file(self, *pkgs):
        try:
            self.downloadPkgs(pkgs)
        except SystemExit:
            # smash SystemExit from yum
            pass

    def fetch_dependencies(self, *pkgs):
        try:
            return self.findDeps(pkgs)
        except SystemExit:
            pass

    def fetch_group_members(self, group_name):

        try:
            group_info = self.returnGroupInfo(group_name)
            pprint(group_info)
        except SystemExit:
            pass


def resolve_name(pkg):
    return '{}-{}-{}.{}'.format(
        pkg.name, pkg.version, pkg.release, pkg.arch
    )


class EncodeMember(object):

    @staticmethod
    def encode_members(rpm_name, *member_names):
        temp_folder = tempfile.mkdtemp()

        print('extracting rpm file {}'.format(rpm_name), file=stderr)

        exit_code = subprocess.call([
            'bsdtar',
            '-xvf',
            rpm_name,
            '-C',
            temp_folder,
        ])

        result = {}
        for file in member_names:
            path = [temp_folder, file]
            if not file.startswith('/'):
                path.insert(1, '/')
            abs_file = ''.join(path)

            if isfile(abs_file):
                with open(abs_file) as fh:
                    result[file] = b64encode(fh.read())
            else:
                result[file] = None

        rmtree(temp_folder)
        return result

    @staticmethod
    def encode_member(rpm_name, member_name):
        if not member_name or len(member_name) < 3:
            raise ValueError('member_name is null or less than 3 characters')

        file = member_name[1:] if member_name.startswith('/') else member_name

        print('rpm file to extract from: {}'.format(rpm_name), file=stderr)

        exit_code = subprocess.call([
            'bsdtar',
            '-xvf',
            rpm_name,
            '-C',
            '/tmp',
            './' + file,
        ])

        if exit_code == 0:
            local_path = '/tmp/{}'.format(file)
            with open(local_path) as fh:
                data = b64encode(fh.read())
                unlink(local_path)
                return data
        else:
            return None

