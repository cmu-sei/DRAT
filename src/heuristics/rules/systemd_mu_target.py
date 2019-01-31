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

class SystemdMUTargetCentOS(RuleBase):
    def __init__(self):
        self._rule_name = 'Find daemons in multi-user.target.wants'
        self._package_name = 'user-installed-daemons'
        super().__init__()
    
    def register(self):
        return PassEnum.DAEMONS
        
    def _should_run(self):
        if not hutils.system_OS(OSDistro.CentOS):
            return False
        return True
                
    def _run(self):
        self._log_start()
        
        mu_dir_path = '/etc/systemd/system/multi-user.target.wants'
        
        # services we expect to see from OS install in mu_dir_path
        expected_services = [
            'auditd.service',
            'crond.service',
            'firewalld.service',
            'irqbalance.service', 
            'kdump.service', 
            'NetworkManager.service',
            'postfix.service',
            'rhel-configure.service', 
            'rsyslog.service', 
            'sshd.service', 
            'tuned.service'
        ]
        
        # services that we might see, but these are covered by package
        # rules
        package_services = [
            'nginx.service',
            'postgresql-9.4.service',
        ]
        known_services = expected_services + package_services

        if not hutils.path_exists(mu_dir_path):
            self._log('multi-user.target.wants directory does not exist')
            self._log_stop()
            return
            
        d = hutils.get_directory_contents(mu_dir_path) # list of FileDetail
        # strip out non-service files
        s = []
        for f in d:
            if f.file_location[-8:] == '.service':
                s.append(f.file_location.rpartition('/')[2])
        
        for f in s:
            if not f in known_services:
                self._process_service_def(mu_dir_path + '/' + f)
        
        self._log_complete()
    
    def _process_service_def(self, path_spec):
        # We assume that path_spec points to file, and file exists
        self._log('Found possible user-defined service ' + path_spec)
        svc_file = hutils.path_rehydrate(path_spec)
        # find the ExecStart
        m = re.search(r'^ExecStart=.+', svc_file, re.M)
        if m == None:
            self._log('Error - file did not contain ExecStart line')
            return
        el = m.group(0)[10:] # after 'ExecStart='
        es = el.split() # split fields by whitespace
        
        for field in es:
            # if it looks like a path
            if hutils.path_exists(field):
                if hutils.origin_unknown(field):
                    # The first field may be something like /bin/python,
                    # so the origin_unknown check should keep us from sweeping
                    # that up.
                    self._mark_as_other_exe(field)
        
        
                
                
        
                