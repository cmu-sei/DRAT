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

class Nginx(RuleBase):
    def __init__(self):
        self._rule_name = 'nginx package rule'
        self._package_name = 'nginx'
        super().__init__()
    
    def register(self):
        return PassEnum.PACKAGES
        
    def _should_run(self):
        if not hutils.package_installed(self._package_name):
            return False
        return True
                
    def _run(self):
        # process main conf file
        conf_path = '/etc/nginx/nginx.conf'
        if not hutils.path_exists(conf_path):
            self._log('Package ' + self._package_name + ' is installed. ' 
                      + conf_path + ' not found.')
            return
        conf_file = hutils.path_rehydrate(conf_path)
        include_paths = hutils.conf_file_fields(conf_file, 'include')
        for p in include_paths:
            if not p == '/etc/nginx/conf.d/*.conf': # the default include
                # The value has to resolve to a file, i.e. you
                # can't Include a directory. You CAN use wildcards.
                # So...if we see '/*' then take everything before that
                # as a directory. If we don't, then we are referencing
                # a single file.
                m = re.search(r'/\*',p) 
                if not m == None:
                    # path ends in wildcard - we'll grab the whole directory
                    p = m.string[:m.start()]
                self._mark_as_content(p)
            
        # We can have multiple document paths, if there are
        # virtual hosts
        doc_paths = hutils.conf_file_fields(conf_file, 'root')
        for p in doc_paths:
            self._mark_as_content(p)

        # We can have multiple Alias paths, if there are
        # virtual hosts (or even without virtual hosts)
        alias_paths = hutils.conf_file_fields(conf_file,'alias')
        for p in alias_paths:
            # These must be fully qualified.
            self._mark_as_content(p)
