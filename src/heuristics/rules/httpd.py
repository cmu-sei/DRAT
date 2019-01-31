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

class HttpdCentOS(RuleBase):
    def __init__(self):
        self._rule_name = 'httpd package rule'
        self._package_name = 'httpd'
        super().__init__()
    
    def register(self):
        return PassEnum.PACKAGES
        
    def _should_run(self):
        if not hutils.system_OS(OSDistro.CentOS):
            return False
        if not hutils.package_installed(self._package_name):
            return False
        return True
                
    def _run(self):
        # process main conf file
        conf_path = '/etc/httpd/conf/httpd.conf'
        if not hutils.path_exists(conf_path):
            self._log('Package ' + self._package_name + ' is installed. ' 
                      + conf_path + ' not found.')
            return
        conf_file = hutils.path_rehydrate(conf_path)
        server_root = hutils.conf_file_field(conf_file, 'ServerRoot')
        if not server_root == '/etc/httpd':
            self._log('UNUSUAL! httpd ServerRoot is ' + server_root)
        
        include_paths = hutils.conf_file_fields(conf_file, 'Include')
        for p in include_paths:
            if not p == 'conf.modules.d/*.conf': # the default includes
                # The value has to resolve to a file, i.e. you
                # can't Include a directory. You CAN use wildcards.
                # So...if we see '/*' then take everything before that
                # as a directory. If we don't, then we are referencing
                # a single file.
                p = self._httpd_path_mangle(p, server_root)
                m = re.search(r'/\*',p) 
                if not m == None:
                    # path ends in wildcard - we'll grab the whole directory
                    p = m.string[:m.start()]
                self._mark_as_content(p)
            
        # We can have multiple document paths, if there are
        # virtual hosts
        doc_paths = hutils.conf_file_fields(conf_file, 'DocumentRoot')
        for p in doc_paths:
            # mangling this path is a 'just in case' - it should
            # be a fully qualified path
            p = self._httpd_path_mangle(p, server_root)
            self._mark_as_content(p)

        # We can have multiple Alias paths, if there are
        # virtual hosts (or even without virtual hosts)
        alias_paths = hutils.conf_file_fields(conf_file,'Alias')
        for p in alias_paths:
            # These must be fully qualified.
            self._mark_as_content(p) 
            
        # We can have multiple script alias paths, if there are
        # virtual hosts            
        script_alias_paths = hutils.conf_file_fields(conf_file,'ScriptAlias')        
        for p in script_alias_paths:
            mp = self._httpd_path_mangle(p, server_root)
            # These must be fully qualified.
            self._mark_as_content(mp)
        
        # Process standard conf.d files
        # autoindex.conf
        conf_file_path = server_root + 'conf.d/autoindex.conf'
        if hutils.path_exists(conf_file_path):
            conf_file = hutils.path_rehydrate(conf_file_path)
            icon_path = hutils.conf_file_field(conf_file, 'Alias')
            if not icon_path == '"/usr/share/httpd/icons/"':
                self._mark_as_content(icon_path)
        
        # fcgid.conf - Fast CGI - nothing for us there
        # manual.conf - going to skip this.
        # ssl.conf
        conf_file_path = server_root + 'conf.d/ssl.conf'
        if hutils.path_exists(conf_file_path):
            conf_file = hutils.path_rehydrate(conf_file_path)            
            pass_phrase_dialog = hutils.conf_file_field(conf_file, 'SSLPassPhraseDialog')
            if not pass_phrase_dialog == 'exec:/usr/libexec/httpd-ssl-pass-dialog':
                #strip leading "exec:"
                p = pass_phrase_dialog[5:]
                self._mark_as_content(p)
                           
        # userdir.conf - serve ~user content - skip for now.
        # welcome.conf - going to skip this.
        
        # conf.modules.d files all contain LoadModule scripts, no file references
    
    def _httpd_path_mangle(self, path_spec, server_root):
        """ Interpret path specifications as specified in httpd/httpd.conf.
        """
        if path_spec[0] == '/':
            return path_spec
        else:
            return server_root + '/' + path_spec
        
