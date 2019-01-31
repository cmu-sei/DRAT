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

class EphemeralContent(RuleBase):
    def __init__(self):
        self._rule_name = 'Ephemeral Content Rule'
        super().__init__()
    
    def register(self):
        return PassEnum.EPHEMERALS
        
    def _should_run(self):
        # Always run
        return True
                
    def _run(self):
        eph_dirs = ['/dev',
                    '/proc',
                    '/run',
                    '/tmp',
                    '/var/account',
                    '/var/adm',
                    '/var/cache',
                    '/var/crash',
                    '/var/empty',
                    '/var/gopher',
                    '/var/lock',
                    '/var/log',
                    '/var/mail',
                    '/var/preserve',
                    '/var/run',
                    '/var/spool',
                    '/var/lib/misc',
                    '/usr/tmp'
                    ]
        for d in eph_dirs:
            if hutils.path_exists(d):
                self._mark_as_ephemeral(d)
    