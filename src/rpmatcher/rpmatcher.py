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

rpnmatcher.py is a web application that will take an uploaded rpm, and it will
decide if that rpm is installed on a specific RHEL/CentOS system that is
uploaded into the IaC database.  It will display the results to the user in a
div that is displayed to the user.

"""

import sys
import os
import os.path
from flask import Flask, render_template, request, redirect, flash, get_flashed_messages
from utils.rpm import RpmFileErrorException
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy

if os.environ.get('DOCKER', None):
    print("Starting with relative path.", sys.stderr)
    from db import tables as t
    db_uri = t.relative_engine_uri
else:
    print("Starting with absolute path.", sys.stderr)
    sys.path.append('../')
    from db import tables as t
    db_uri = t.abs_engine_uri

from utils import rpm

app = Flask(__name__)
ALLOWED_EXTENSIONS = set(['rpm'])

# TODO: change to static value if using outside of dev
app.secret_key = str(os.urandom(32))

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.mkdir(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)


def is_file_extension_allowed(filename):
    """
    This method check to see if the uploaded file extension is allowed to be
    uploaded to the service.

    Args:
        string - filename and extension

    Returns:
        boolean
    """
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route('/', methods=['GET'])
def show_matcher():
    """
    This controller method displays the rpm upload page to the user.

    Args:
        None

    Returns:
        This renders and returns a HTML jinja2 template.
    """

    systems = db.session.query(t.System).order_by(t.System.name).all()
    return render_template('rpmatcher.j2', systems=systems)


@app.route('/rpmatcher', methods=['POST'])
def receive_match():
    """
    This controller method is called via Ajax and receives an uploaded RPM
    file.  It takes that file and compares it to all fthe files on the system.
    It returns text based on the result of the request.

    Args:
        Multipart post with a file

    Returns:
        A text string containing text to populate a div on the web page.
    """

    rpm_file = request.files.get('file', None)
    print(request.data)
    try:
        system_id = int(request.form.get('system', ''))
    except ValueError:
        return 'You must select a system.'

    system = db.session.query(t.System).get(system_id)

    if not system:
        return 'System was not found.'

    if not rpm_file:
        return 'File was not included.'

    if not rpm_file.filename or not is_file_extension_allowed(rpm_file.filename):
        return 'File must have an extension of .rpm'

    sec_filename = secure_filename(rpm_file.filename)

    local_filename = os.path.join(
        app.config['UPLOAD_FOLDER'],
        sec_filename
    )

    rpm_file.save(local_filename)

    rpm_info = rpm.Rpm(
        system_id=system_id,
        filename=local_filename,
        session=db.session
    )

    try:
        result = rpm_info.get_rpm_match()
    except RpmFileErrorException:
        return (
            'An error occurred when inspecting the RPM file.  '
            'The file could be corrupted.'
        )

    if result:
        return 'The rpm file {} was installed on system {}.'.format(
            sec_filename,
            system.name,
        )

    return 'The rpm file {} does not appear on system {}.'.format(
        sec_filename,
        system.name,
    )


"""
This calls and runs the flask framework.
"""
app.run(host='0.0.0.0', port=5000)
