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

import shutil
from typing import (
    Tuple,
    Iterable,
    Callable,
)
from pathlib import Path
from collections import OrderedDict
import oyaml as yaml
from base.logger import LogConfig
from utils.session import State
from db.tables import *
from base.enums import get_user_content_names, FileOrigin
from sqlalchemy.sql.expression import not_

log = LogConfig.get_logger(__name__)


class Hierarchy(object):
    def __init__(self, hierarchy):
        self.tasks: Path = None
        self.files: Path = None
        self.handlers: Path = None
        self.templates: Path = None
        self.role: Path = None
        self.roles: Path = None
        self.inventory: Path = None

        self.__dict__.update(hierarchy)


class BaseInfrastructureAsCodeGenerator(object):

    def __init__(self, **kwargs):
        """
        :param output_dir: directory that will receive the iac code
        :type str:
        :param prune: remove contents of output directory
        :type bool:
        """
        self.output_dir: Path = self.setup_output(kwargs.pop("output_dir"))
        self.pruned_output: bool = self.prune_output(
            kwargs.pop("prune", False)
        )

        self.system = kwargs.pop("system")

    def setup_output(self, dir_name: str) -> Path:
        if not dir_name:
            raise ValueError("This requires variable output_dir")

        out = Path(dir_name).resolve()

        if not out.exists():
            out.mkdir(parents=True)

        return out

    def prune_output(self, do_prune: bool = False):
        if not do_prune:
            return False

        shutil.rmtree(self.output_dir.as_posix(), ignore_errors=True)
        self.output_dir.mkdir(exist_ok=True)

        return True

    def _get_user_directories_to_create(self):
        session = State.get_db_session()

        directories = session.query(
            FileDetail
        ).join(
            System
        ).filter(
            (System.system_id == self.system.system_id) &
            (FileDetail.file_type == "D") &
            (FileDetail.origin.in_(
                get_user_content_names(),
            ))
        ).order_by(
            FileDetail.file_location
        ).yield_per(10)

        for directory in directories:
            yield directory

    def _get_files_to_create(
        self,
        origins: Tuple[str] = None,
        file_prefix: str = None,
    ) -> Iterable[Tuple[FileDetail, FileStorage]]:

        session = State.get_db_session()

        where_clause = (
            System.system_id == self.system.system_id
        ) & (
            FileDetail.file_type == "F"
        )

        if origins:
            where_clause &= (
                FileDetail.origin.in_(
                    origins
                )
            )

        if file_prefix:
            where_clause &= (
                FileDetail.file_location.startswith(file_prefix)
            )

        files = session.query(
            FileDetail,
            FileStorage,
        ).join(
            System
        ).join(
            FileDetailStorageLink
        ).join(
            FileStorage
        ).filter(
            where_clause,
        ).order_by(
            FileDetail.file_location
        ).yield_per(10)

        for file_pair in files:
            yield file_pair


class AnsibleInfrastructureAsCodeGenerator(BaseInfrastructureAsCodeGenerator):
    """
    Generates Ansible YAML files to install the needed packages and files.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        log.debug("Initializing Ansible IaC generator.")
        self._yaml = []
        self._yaml_comments = []
        self.hierarchy: Hierarchy = None
        self.ensure_hierarchy()

    def ensure_hierarchy(self):
        """
        Creates the directories needed to write the Ansible configuration.
        :return: None
        """
        # noinspection PyDictCreation
        hierarchy = {
            "roles": self.output_dir.joinpath("roles")
        }

        hierarchy["role"] = hierarchy["roles"].joinpath(
            self.system.name,
        )

        hierarchy["inventory"] = self.output_dir.joinpath("inventory")

        if not hierarchy["inventory"].exists():
            hierarchy["inventory"].mkdir(parents=True)

        for entity in ["tasks", "files", "handlers", "templates"]:
            hierarchy[entity] = hierarchy["role"].joinpath(
                entity,
            )

            if not hierarchy[entity].exists():
                hierarchy[entity].mkdir(parents=True, exist_ok=True)

        self.hierarchy = Hierarchy(hierarchy)

    def create(self):
        """
        Creates the IaC.
        :return: None
        """
        self.create_package_mgr_config()
        self.create_package_task()
        self.create_user_directories()
        self.create_user_files(file_path=self.hierarchy.files)
        self.create_templates()
        self.create_main_task()
        self.create_hosts()
        self.create_site()

    def create_package_mgr_config(self):
        """
        Creates the configuration to install the package manager repos
        before trying to install packages.
        :return:
        """

        self._add_pkg_mgr_config(
            self._get_files_to_create(
                origins=get_user_content_names(),
                file_prefix="/etc/yum",
            )
        )

        self._add_yum_cleaning()

        self.fixate(self.hierarchy.tasks.joinpath("package_manager.yaml"))

    def create_hosts(self):
        """
        Creates a yaml-based inventory file for ansible
        :return:
        """

        self._generate_hosts()
        self.fixate(self.hierarchy.inventory.joinpath("hosts.yaml"))

    def create_site(self):
        """
        Creates the top-level playbook
        :return:
        """

        self._generate_site()
        self.fixate(self.output_dir.joinpath("site.yaml"))

    def create_main_task(self):
        """
        Generates the master playbook.
        :return: None
        """
        self._generate_main(
            "package_manager",
            "packages",
            "templates",
            "user_directories",
            "user_files",
        )

        self.fixate(self.hierarchy.tasks.joinpath("main.yaml"))

    def create_package_task(self):
        """
        Generates the playbook to install packages.
        :return: None
        """
        self._add_packages()
        self.fixate(self.hierarchy.tasks.joinpath("packages.yaml"))

    def create_user_directories(self):
        """
        Generates the playbook to create directories
        :return: None
        """
        self._add_user_directories(
            dirs=self._get_user_directories_to_create()
        )
        self.fixate(self.hierarchy.tasks.joinpath("user_directories.yaml"))

    def create_user_files(self, file_path):
        """
        Generate the playbook to create the user-generated content
        :return: None
        """

        self._add_user_files(
            files=self._get_files_to_create(
                get_user_content_names()
            ),
        )

        self.fixate(self.hierarchy.tasks.joinpath("user_files.yaml"))

    def create_templates(self):
        """
        Generates the playbook that installs the files from the original
        system.
        :return: None
        """

        self._add_template_files(
            self._get_files_to_create(
                (FileOrigin.PackageModified.name,)
            )
        )

        self.fixate(self.hierarchy.tasks.joinpath("templates.yaml"))

    def fixate(self, location: Path):
        """
        Writes a YAML file with comments and YAML.
        :param location: Where to write the file
        :return: None
        """

        file = location.as_posix()
        with open(file, "w") as yaml_file:
            yaml_file.write("---\n\n")

            for line in self._yaml_comments:
                lines = None
                if "\n" in line:
                    lines = line.split("\n")
                else:
                    lines = [line]

                for subline in lines:
                    yaml_file.write(f"#  {subline}\n")

            log.info(f"Writing output to {file}.")
            yaml_file.write(self._generate_yaml())

            yaml_file.write("\n...\n")

            log.info("Done.")

        if type(self._yaml) is list:
            self._yaml.clear()
        else:
            self._yaml = []

        self._yaml_comments.clear()

    # region protected methods

    def _generate_yaml(self):
        """
        Converts the dictionary into YAML text.
        :return: str
        """
        return yaml.dump(
            self._yaml,
            default_flow_style=False,
        )

    def _generate_main(self, *includes: str):
        """
        Inserts the include files into the dictionary.
        :param includes: name of modules to include, minus the .yaml
        :return: None
        """
        for include in includes:
            self._yaml.append({
                "include": " ".join([
                    ".".join([
                        include,
                        "yaml",
                    ]),
                    "tags=%s" % include,
                ])
            })

    def _add_packages(self):

        log.debug("entering _add_packages")

        session = State.get_db_session()

        # skip fake gpg-pubkey package
        # https://unix.stackexchange.com/questions/190203/what-are-gpg-pubkey-packages
        packages = session.query(
            RpmInfo
        ).join(
            System
        ).filter(
            (System.system_id == self.system.system_id) &
            not_(RpmInfo.name == "gpg-pubkey")  # skip fake package
        ).order_by(
            RpmInfo.installation_date
        ).yield_per(10)

        for package in packages:
            task = OrderedDict(
                name=f"Install {package.name}",
                package=self._get_install(package.name),
            )

            self._yaml.append(task)

        log.debug("exiting _add_packages")

    def _add_user_directories(self, dirs):
        log.debug("entering _add_user_directories")

        directory: FileDetail

        for directory in dirs:

            task = OrderedDict(
                name=f"Create directory \"{directory.file_location}\"",
                file=OrderedDict(
                    path=directory.file_location,
                    state="directory",
                    owner=directory.owner_name,
                    group=directory.owner_group,
                    mode=f"{directory.file_perm_mode}",
                ),
            )

            self._yaml.append(task)

        log.debug("exiting _add_user_directories")

    def _add_generic_file_task(
        self,
        files: Iterable[
            Tuple[
                FileDetail,
                FileStorage,
            ]
        ],
        file_path: Path,
        task_maker: Callable[[
            str,
            FileDetail,
        ], OrderedDict],
        extension: str = None,
    ):

        log.debug("entering _add_generic_file_task")

        file_detail: FileDetail
        file_data: FileStorage

        for file_detail, file_data in files:

            rel_path = file_detail.file_location[1:]

            local_file = file_path.joinpath(rel_path)

            if extension:
                local_file = local_file.parent.joinpath(
                    local_file.name + extension
                )
                rel_path += extension

            local_path = local_file.parent

            log.debug("Create directory for file")
            os.makedirs(local_path.as_posix(), exist_ok=True)

            log.debug(f"Writing file {local_file}.")

            with open(local_file.as_posix(), "wb") as user_file:
                if file_data.file_data:
                    user_file.write(file_data.file_data)

            log.debug(f"Done writing file {local_file}.")

            log.debug("Generating yaml dictionary.")

            task = task_maker(rel_path, file_detail)

            log.debug("Append task dictionary to yaml")

            self._yaml.append(task)

        log.debug("exiting _add_generic_file_task")

    def _add_user_files(
        self,
        files: Iterable[
            Tuple[
                FileDetail,
                FileStorage,
            ]
        ]
    ):
        log.debug("entering _add_user_files")

        def task_generator(relative_path: str, detail: FileDetail):
            return OrderedDict(
                name=f"Install user file \"{detail.file_location}\"",
                copy=OrderedDict(
                    src=relative_path,
                    dest=detail.file_location,
                    owner=detail.owner_name,
                    group=detail.owner_group,
                    mode=f"{detail.file_perm_mode}",
                )
            )

        self._add_generic_file_task(
            files=files,
            file_path=self.hierarchy.files,
            task_maker=task_generator,
        )

        log.debug("exiting _add_user_files")

    def _add_template_files(
        self,
        files: Iterable[
            Tuple[
                FileDetail,
                FileStorage,
            ]
        ],
        task_name: str = None,
    ):
        log.debug("entering _add_template_files")

        def task_generator(relative_path: str, detail: FileDetail):

            default_name = "Install modified package file"

            return OrderedDict(
                name=(
                    f"{task_name or default_name} "
                    f"\"{detail.file_location}\""
                ),
                template=OrderedDict(
                    src=relative_path,
                    dest=detail.file_location,
                    owner=detail.owner_name,
                    group=detail.owner_group,
                    mode=f"{detail.file_perm_mode}",
                )
            )

        self._add_generic_file_task(
            files=files,
            file_path=self.hierarchy.templates,
            task_maker=task_generator,
            extension=".j2",
        )

        log.debug("exiting _add_template_files")

    def _add_pkg_mgr_config(
        self,
        files: Iterable[
            Tuple[
                FileDetail,
                FileStorage,
            ]
        ],
    ):
        self._add_template_files(
            files=files,
            task_name="Install yum configuration",
        )

    def _add_yum_cleaning(self):
        cmd = OrderedDict(
            name="Clear yum database",
            shell="yum clean all",
            args=OrderedDict(
                warn=False
            ),
        )

        self._yaml.append(cmd)

    def _get_install(self, package_name):

        task = OrderedDict(
            name=package_name,
            state="present"
        )

        return task

    def _generate_site(self):
        site = OrderedDict(
            hosts="all",
            roles=[
                self.hierarchy.role.name
            ]
        )

        self._yaml.append(site)

    def _generate_hosts(self):
        inventory = OrderedDict(
            all=OrderedDict(
                hosts=OrderedDict(),
            ),
        )

        inventory["all"]["hosts"][self.system.name] = OrderedDict(
            ansible_user=self.system.username,
            ansible_host=self.system.hostname,
            ansible_port=self.system.port,
        )

        self._yaml = inventory

    # endregion
