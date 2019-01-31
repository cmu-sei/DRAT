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

class IacExceptionBase(Exception):
    """
    Base Except for package
    """
    pass


class ApiExceptionBase(IacExceptionBase):
    """
    Base exception for the api
    """
    pass


class RpmNotFound(ApiExceptionBase):
    """
    Could not find RPM in a yum repo
    """
    pass


class FatalError(ApiExceptionBase):
    """
    Error querying the yum api
    """
    pass


class ConflictNumerousPackagesFound(ApiExceptionBase):
    """
    Query returned numerous packages
    """
    pass


class PackageFileNotFound(IacExceptionBase):
    """
    Error finding file in package
    """
    pass


class RpmFileNotFound(PackageFileNotFound):
    """
    Error finding file in Rpm
    """
    pass


class FileNotFound(IacExceptionBase):
    """
    Error finding file on file system
    """
    pass
