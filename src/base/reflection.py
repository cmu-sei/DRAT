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

import typing
import os
import re
from utils.ssh import START_TTY, END_TTY
import logging
from io import BytesIO, StringIO, IOBase
from abc import ABC, abstractmethod
from tempfile import mktemp

from paramiko import client, SSHException
from paramiko.channel import Channel
from sqlalchemy.orm import aliased

from utils import ssh
from utils.session import State
from db.tables import (
    System,
    RpmDetail,
    FileDetail,
    RpmFileDetailLink,
    RpmDetailPatchStorageLink,
    FileDetailStorageLink,
    FileStorage,
)

from db.analysis import FileDifference
from db.storage import Fetcher
from api.remote import RpmHandler, RpmNotFound
from utils import generate_alt_rpm_filenames
from utils.session import State
from base.enums import FileOrigin

log = logging.getLogger(__name__)


class InstalledPackageInfo(ssh.SshConnector, ABC):

    """
    This is an abstract base class to gather a list of packages and package
    meta data
    """

    @abstractmethod
    def get_packages(self) -> ssh.StringIterator:
        pass

    def __init__(
            self,
            hostname: str = None,
            username: str = None,
            key_file: str = None,
            port: int = 22,
            exec_path: str = None,
            tty: bool = False,
    ):

        if not exec_path:
            raise ValueError('exec_path is empty.')

        self.exec_path = exec_path
        self.tty = tty
        self.rhel_regex = re.compile(
            r'^(?P<distro>CentOS|Red\sHat\sEnterprise)\s(\w+\s)+(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<revision>\d+))?',
            re.IGNORECASE,
        )

        self.temp_dir = mktemp(prefix='reflect_', dir='/tmp')

        super().__init__(
            hostname=hostname,
            username=username,
            key_file=key_file,
            port=port
        )

    def get_os_info(self) -> dict:

        info = {
            'distro': None,
            'major': None,
            'minor': None,
            'revision': None
        }

        match = None

        try:
            for line in self.run_remote_command(
                    command="cat /etc/redhat-release"
            ):
                if line.lstrip().startswith('#'):
                    continue

                match = self.rhel_regex.match(line)

                if match:
                    break

        except ssh.SSHRunException:
            pass

        if match:
            info = match.groupdict()
            if info['distro'].lower().startswith('red'):
                info['distro'] = 'RHEL'
            else:
                info['distro'] = info['distro'].lower()

            return info

    def get_host_info(self) -> dict:
        (stdin, stdout, stderr) = self._client.exec_command(
            'uname -a'
        )

        kernel_info = ''.join(stdout.readlines()).strip()

        (stdin, stdout, stderr) = self._client.exec_command(
            'hostname -f'
        )

        hostname = ''.join(stdout.readlines()).strip()

        return {'remote_hostname': hostname, 'kernel_version': kernel_info}

    def get_files(self):

        walk_script = self.exec_path + 'walk.py'

        with open(walk_script, 'r') as w:
            lines = w.readlines()

        if self.tty:
            lines.append('\n\n\nEOF\n')

        walk_code = ''.join(lines)

        print('Walking filesystem.')

        if self.tty:
            command = (
                'sudo python << EOF ; echo "exit_code=$?"; exit\n'
                f'{walk_code}'
            )

            for line in self.run_tty_command(command=command):
                yield line
        else:

            remote = self.run_remote_command(
                command="sudo python",
                stdin_data=BytesIO(
                    walk_code.encode("utf-8"),
                )
            )
            line = next(remote)

            if line.startswith(START_TTY):
                line = next(remote)

            # remove START and END blocks from walk results
            # these were needed with centos's old sudo
            # but 7.4/7.5 removes requiretty from /etc/sudoers
            next_line = None
            while line:
                try:
                    next_line = next(remote)
                except StopIteration:
                    if not line.startswith(END_TTY):
                        yield line
                    else:
                        raise

                yield line
                line = next_line


class InstalledRpmInfo(InstalledPackageInfo):

    def get_packages(self) -> ssh.StringIterator:
        return self.get_rpm_info()

    def get_rpm_info(self) -> ssh.StringIterator:
        command = (
            'rpm -qa --queryformat '
            '\'['
            '%{=NAME}\t%{=VERSION}\t%{=RELEASE}\t%{=ARCH}\t'
            '%{=INSTALLTID}\t%{=INSTALLTIME:date}\t'
            '%{FILENAMES}\t%{FILESIZES}\t%{FILEDIGESTS}\t'
            '%{FILECLASS}\t%{FILEFLAGS}\t%{SOURCERPM}\t'
            '%{=NAME}-%{=VERSION}-%{=RELEASE}.%{=ARCH}.rpm'
            '\n]\''
        )

        return self.run_remote_command(command=command)


class ContentGatherer(object):

    def __init__(
            self,
            system: System=None,
            handler_route=None,
            ssh_connector: ssh.SshConnector=None,
    ):
        self.system: System = system or State.get_system()
        self.connector: ssh.SshConnector = (
                ssh_connector or State.get_ssh_session()
        )
        self.file_difference: FileDifference = FileDifference(
            system=self.system
        )


class RpmGatherer(ContentGatherer):
    def __init__(self, **kwargs):

        self.rpm_handler: RpmHandler = RpmHandler(
            route=kwargs.pop("handler_route", None)
        )

        super().__init__(**kwargs)


class GetModifiedFilesFromRemoteHost(RpmGatherer):
    """
    This class uses an open SSH connection to a remote host,
    and retrieves a modified file.
    results as a BytesIO object.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def process_user_content(self):

        session = State.get_db_session()
        system: System = State.get_system()

        try:
            # TODO: Done in another method, maybe consolidate
            # log.info("Deleting prior art...")
            #
            # fdsl: FileDetailStorageLink = aliased(FileDetailStorageLink)
            #
            # exists_query = session.query(
            #     FileDetail
            # ).filter(
            #     FileDetail.system_id == system.system_id
            # ).filter(
            #     FileDetail.file_type == "F"
            # ).filter(
            #     FileDetail.origin.in_([
            #         FileOrigin.PackageModified.name,
            #         FileOrigin.PackageContent.name,
            #         FileOrigin.OtherExecutable.name,
            #         FileOrigin.UserData.name,
            #     ])
            # ).filter(
            #     fdsl.file_detail_id == FileDetail.file_detail_id
            # )
            #
            # result = session.query(
            #     fdsl
            # ).filter(
            #     exists_query.exists()
            # ).delete(synchronize_session=False)
            #
            # log.debug("Expiring session")
            # session.expire_all()
            #
            # log.debug(f"Delete result: {result}")

            log.info("Fetching user files from file_detail..")
            query = session.query(
                FileDetail
            ).filter(
                FileDetail.system_id == system.system_id
            ).filter(
                FileDetail.file_type == "F"
            ).filter(
                FileDetail.origin.in_([
                    FileOrigin.PackageContent.name,
                    FileOrigin.OtherExecutable.name,
                    FileOrigin.UserData.name,
                ])
            )
            log.info("Deleted.")
            session.flush()

            log.info("Opening SFTPCLient")

            sftp = ssh.SftpWrapper(
                open_sftp_client=State.get_ssh_session().get_sftp_client(),
            )

            file: FileDetail

            for file in query.all():
                log.info(f"Fetching {file.file_location} from {system.name}.")
                file_handle = sftp.get_file_handle(file.file_location)

                file_storage: FileStorage = FileStorage(file_type="C")

                if (
                    type(file_handle) is BytesIO
                ):
                    log.debug("file result is type BytesIO")
                    file_handle.seek(0)
                    log.debug("reading data into file_storage")
                    file_storage.file_data = file_handle.read()
                else:
                    log.debug("file result is not type BytesIO")
                    file_storage.file_data = b""
                    log.debug("file stored as empty file.")

                file_link = FileDetailStorageLink(
                    file_detail=file,
                    file_storage=file_storage,
                    file_type="C",
                )

                log.info(f"Storing {file.file_location} from {system.name}.")

                session.add(file_storage)
                session.add(file_link)
                log.debug("SQLAlchemy session flushing.")
                session.flush()
                log.debug("SQLAlchemy session flushed.")

            log.info("Fetching user files has been completed.")

            session.commit()

            log.info("Committed data to database")

        except Exception as e:
            log.fatal(
                "Exception occurred during the gathering of user content"
            )
            log.fatal(e)
            session.rollback()
            raise

        finally:
            session.close()

    def process_modified_packages(self):

        self.file_difference.clear_system_file_storage()
        modified_rpms = self.file_difference.fetch_flagged_rpms()

        sftp = ssh.SftpWrapper(
            open_sftp_client=State.get_ssh_session().get_sftp_client(),
        )

        for rpm in modified_rpms:

            modified_files = list(self.file_difference.fetch_flagged_files(
                rpm_info=rpm
            ))

            flagged_files = self.file_difference.fetch_flagged_file_details(
                rpm_info=rpm
            )

            for file_detail in flagged_files:

                file_data = sftp.get_file_handle(file_detail.file_location)

                log.info(f'Got file for {file_detail.file_location}')

                log.info(f"Storing file into the database.")

                if file_detail.file_location.endswith(".py"):
                    new_origin = FileOrigin.OtherExecutable
                else:
                    new_origin = FileOrigin.PackageModified

                self.file_difference.store_file_data(
                    file_detail=file_detail,
                    sys_file=file_data,
                    new_origin=new_origin,
                )

                log.info("File stored into database.")


class CreatePatchFileFromRemoteHost(RpmGatherer):
    """
    This class uses an open SSH connection to a remote host,
    sends down a file, diffs the file, and returns the
    results as a BytesIO object.
    """

    def __init__(self, **kwargs):
        from warnings import warn
        warn(
            "This class has been deprecated.  Patch gathering "
            "worked but can be really limited; switched over "
            "to get storing the file."
        )
        super().__init__(**kwargs)

    def process_modified_packages(self):
        self.file_difference.clear_data_for_current_system()
        modified_rpms = self.file_difference.fetch_flagged_rpms()

        for rpm in modified_rpms:
            modified_files = list(self.file_difference.fetch_flagged_files(
                rpm_info=rpm
            ))

            file_results: typing.Dict[str, str] = {}

            rpm_files = [f.file_location for f in modified_files]

            if not rpm_files:
                log.warning(
                    f"rpm {rpm.name} does not have any text files to patch.  "
                    "Skipping to the next rpm."
                )
                continue

            for name_permutation in generate_alt_rpm_filenames(rpm.filename):
                try:
                    log.info(f'  {name_permutation}..')
                    self.rpm_handler.set_rpm_name(name_permutation)
                    file_results = self.rpm_handler.fetch_files_from_rpm(
                        *rpm_files
                    )
                except RpmNotFound:
                    continue

                break

            if not file_results:
                log.error(f'rpm {rpm.filename} not found.')

            for file in modified_files:
                abs_path = file.file_location
                og_file: typing.BinaryIO = file_results.get(abs_path)
                log.info(f'    {abs_path} patch.')
                patch = BytesIO()

                try:
                    for line in self.get_patch(
                            abs_path,
                            patch,
                            og_file,
                    ):
                        log.info(line.rstrip('\r\n'))
                except Exception as e:
                    raise

                log.info(f'got patch for {abs_path}')

                # rewind BytesIO for saving
                og_file.seek(0)

                file_detail = Fetcher.fetch_file_detail(file)

                self.file_difference.store_file_data(
                    original_file=og_file,
                    rpm_detail=file,
                    file_detail=file_detail,
                    sys_file=patch
                )

    def get_patch(
            self,
            file_location: str,
            sys_file: typing.IO,
            original_file: typing.IO=None,
    ) -> ssh.StringIterator:
        """
        Runs a remote ssh command to diff a file at the remote server.
        Command is ran via sudo with a tty.  The file is uploaded into a temp
        folder, compared to a file on the remote system, and the patch results
        are stored in the sys_file via reference.  The string iterator
        yields the output of the diff command.  Note: diff returns a 1 if it
        creates a patch, and zero if there is no difference.

        :param file_location: File location on the remote server
        :param sys_file: IOBase object.  Will be truncated and rewound.
        :param original_file: IOBase object.  File that will the compared to
            file_location.
        :return: String Iterator, returns output of diff command.
        """

        if original_file is None:
            upload_file = BytesIO(b'')
        else:
            upload_file = original_file

        remote_file = f'{self.connector.temp_dir}/orig'
        remote_patch = f'{self.connector.temp_dir}/patch'

        command = (
            'unset HISTFILE\n'
            f'echo && echo "{ssh.START_TTY}"; '
            f'sudo diff -u {remote_file} {file_location} > '
            f'{remote_patch} ; '
            'exit_code=$? && echo && echo "'
            f'{ssh.END_TTY}\nexit_code=${{exit_code}}"; exit\n'
        )

        return self.connector.run_tty_command(
            command=command,
            input_file_data=upload_file,
            success_code=1,
            in_file=remote_file,
            out_file=remote_patch,
            output_file_data=sys_file,
        )
