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

from .rule_base import RuleBase
from  base.enums import FileOrigin, OSDistro,  PassEnum
import heuristics.heuristic_utils as hutils
import re

class PostgreSQL94(RuleBase):
    def __init__(self):
        self._rule_name = 'postgresql 9.4 package rule'
        self._package_name = 'postgresql94'
        self._version = '9.4'
        super().__init__()
    
    def register(self):
        return PassEnum.PACKAGES
        
    def _should_run(self):
        if not hutils.package_installed(self._package_name):
            return False
        return True
                
    def _run(self):
        # process systemd service startup file
        f_path = '/etc/systemd/system/multi-user.target.wants/postgresql-' + self._version + '.service'
        if not hutils.path_exists(f_path):
            self._log('Package ' + self._package_name + ' is installed but service not started. ' 
                      + f_path + ' not found.')
            return
        f = hutils.path_rehydrate(f_path)
        # find the ExecStart line
        s = re.search(r'^ExecStart=.+', f, re.M).group(0)
        # look for a -D switch
        m = re.search(r'-D\s+',s)
        if m == None:
            self._log('Postgresql data directory not specified in service definition')
            return
        # find the argument for the -D switch
        s = m.group(0).split()[1]
        if not s[0] == '$':
            # argument is not an environment variable
            self._mark_as_content(s)
        else:
            # Else argument is an environment variable - extract it's name
            # Assume format is ${v_name}
            v_name = s[2:-1]
            # Find Environment statement that assigns a value to that name
            d = re.search(r'^Environment='+v_name+'=.+',f,re.M).group(0).split('=')[2]
            self._mark_as_content(d)
        