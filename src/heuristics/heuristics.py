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

from base.enums import PassEnum
import importlib
from utils.session import State
import heuristics.heuristic_utils as hutils
from base.logger import LogConfig


class Heuristics(object):
    """Framework for managing and executing rules.

    Holds the callback table that rules register into. Provides methods to fire
    all rules for a particular analysis pass.

    Attributes:
        rules: Dict of list of rules to run for each pass.
        allRules: Dict of all rules (module and class name). Statically
            inialize in code for now, later refactor to discover rules.
    """

    session = 'todo'

    def __init__(self):
        self.__init_logger()
        self._discover_rules()
        # initialize the lists to empty for all passes
        self._rules = dict()
        for p in PassEnum:
            self._rules[p] = []
        self._register_rules()

    def __init_logger(self):
        """
        Factor this out now so it can be replaced by a global application
        logger later on.
        """
        self.logger = LogConfig.get_logger(__name__)

    def _log(self, message):
        """
        Helper method. Standardize logging format.
        """
        self.logger.info('Heuristics Framework: ' + message)

    def _discover_rules(self):
        """
        Discover rules from rules package, and populate the _allRules dict.

        This turns out to be complicated - you can discover the modules (*.py
        files) pretty easily, but then you need to introspect and pull out the
        rule class names.

        We'll just hardcode it for now. Extend the dict to add new rules.
        """
        self._all_rules = {
            'rule_example': 'RuleExample',
            'httpd': 'HttpdCentOS',
            'nginx': 'Nginx',
#            'ephemeral': 'EphemeralContent',
            'postgresql': 'PostgreSQL94',
            'systemd_mu_target': 'SystemdMUTargetCentOS',
            'user_home': 'UserHomeTargetCentOS',
            'package_manager': 'YumConfigurationCentOS',
        }

    def _register_rules(self):
        """
        Call each rule's register method and get back which pass to add it to.
        """
        self._log('Initializing')
        for key in self._all_rules:
            mod = "heuristics.rules." + key
            class_name = self._all_rules[key]
            rule_class = getattr(importlib.import_module(mod), class_name)
            rule = rule_class()
            pass_ID = rule.register()
            self._rules[pass_ID].append(rule)

    def run_rules(self, p):
        system_name = State.get_system().name

        self._log('Start firing rules for system '
                  + system_name + ' Pass ' + p.name)
        self._log('Unmarked files: %d' % hutils.unknown_count())
        for r in self._rules[p]:
            r.fire()
        self._log('Finished firing rules for system '
                  + system_name + ' Pass ' + p.name)
        self._log('Unmarked files: %d' % hutils.unknown_count())
