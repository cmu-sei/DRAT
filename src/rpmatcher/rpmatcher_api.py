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

# -*- coding: utf-8 -*-
"""

rpmatcher_api.py runs in a Docker container and provides access to the Yum API.
A list of files can be requested from this API, and it will returned the files
in a json message.  The files will be encoding with base64; this will allow
the download of binary files if needed.  This an API designed to be called
by the run_analysis.py file.

"""
from __future__ import print_function

import sys
import os
import os.path
from flask import Flask, request, jsonify, send_file, make_response
from pprint import pformat
from utils.rpm import RpmFileErrorException
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

try:
    import pydevd
except ImportError:
    pass

from db import tables as t
from utils import rpm
from utils import pkg

app = Flask(__name__)

# TODO: change to static value if using outside of dev
app.secret_key = str(os.urandom(32))

app.config['SQLALCHEMY_DATABASE_URI'] = t.get_db_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


@app.route('/api/fetch/<pkg_name>', methods=['GET'])
def fetch_files_from_package(pkg_name):
    """
    This method takes the name of a rpm package and fetches it from a repo.
    The package is unarchived, and the requested files are encoded with
    base64 and returned in a json message.  This allows the run_analysis.py
    file to fetch and diff files on the main system.

    """

    files = request.args.getlist('file')

    if not files:
        return make_response(jsonify(
            {'error': 'no files specified'}
        ), 400)

    wrapper = pkg.YumWrapper()
    pkgs = wrapper.find_package(pkg_name)

    if not pkgs:
        return response_package_not_found(pkg_name)

    packages = []

    if len(pkgs) > 1:
        for package in pkgs:
            if package.nvra == pkg_name:
                packages.append(package)
                break

        if len(packages) != 1:
            return response_found_multiple(pkg_name, pkgs)
    else:
        packages.extend(pkgs)

    wrapper.fetch_file(*packages)

    loc = wrapper.get_cache_locations(packages)

    abs_file = loc.get(pkg_name, '')
    returned_pkg_name = loc.keys()[0]

    if not abs_file:
        return make_response(jsonify(
            {
                'error': (
                    'Package name is not specific enough.  '
                    'Found pkg {}'.format(
                        returned_pkg_name
                    )
                )
            }
        ), 410)

    result = {}

    try:
        result = pkg.EncodeMember.encode_members(abs_file, *files)
        print()
    except OSError as e:
        print(e)

    return make_response(jsonify(result), 200)


@app.route("/api/fetch_group/<group_name>", methods=["GET"])
def fetch_group_info(group_name):
    wrapper = pkg.YumWrapper()
    group_info = wrapper.fetch_group_members(group_name)

    return make_response(jsonify(group_info), 200)


@app.route("/api/fetch_deps/<pkg_name>", methods=["GET"])
def fetch_dependencies(pkg_name):
    """
    fetches the providers of a package's dependencies
    :param pkg_name: Name of package
    :return: JSON list of packages
    """
    wrapper = pkg.YumWrapper()
    packages = wrapper.find_package(pkg_name)

    if not packages:
        return response_package_not_found(pkg_name)

    if len(packages) > 1:
        return response_found_multiple(pkg_name, packages)

    package = packages.pop()
    requires = wrapper.fetch_dependencies(package)
    deps = requires.get(package)

    results = []
    for dep, providers in deps.items():
        results.extend(providers)

    result = []
    for dep in results:
        if dep.arch == package.arch:
            result.append({
                "name": dep.name,
                "version": dep.version,
                "release": dep.release,
                "arch": dep.arch,
                "rpm": "%s.rpm" % wrapper.resolve_name(dep),
            })

    result = {"result": result}

    return make_response(jsonify(result), 200)


def response_package_not_found(pkg_name):
    """
    Short cut to return a 404 message for a package not find
    :param pkg_name: Name of package
    :return: flask response
    """

    return make_response(jsonify(
        {'error': 'Package {} was not found'.format(pkg_name)}
    ), 404)


def response_found_multiple(pkg_name, pkgs):
    """
    Shortcut to return a 409 for finding multiple packages
    :param pkg_name: Name of package requests
    :param pkgs: List of packages found by that name
    :return: flask response
    """
    return make_response(jsonify(
        {
            'error': 'pkg_name {} resolved to multiple pkgs: {}'.format(
                pkg_name,
                ', '.join([
                    pkg.resolve_name(p)
                    for p in pkgs
                ])
            )
        }
    ), 409)
