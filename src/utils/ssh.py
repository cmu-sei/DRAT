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

import logging
import sys
import os
import logging
import time
import re
import tempfile
from io import BytesIO
from tempfile import mktemp
from typing import Iterator, IO, BinaryIO
from timeit import default_timer
from paramiko import SSHException, Channel, SSHClient, client
from paramiko.sftp_client import SFTPClient

log = logging.getLogger(__name__)

StringIterator = Iterator[str]
ByteIterator = Iterator[bytes]

START_TTY = f'{"/" * 40} START TTY {"/" * 40}'
END_TTY = f'{"/" * 40} END TTY {"/" * 40}'


class FetchChannelStream(object):
    """
    This takes a paramiko channel and
    yields byte arrays from it.
    """

    def __init__(
            self,
            channel: Channel = None,
            timeout_seconds: int = 600,
            block_size: int = 8192,
            sleep_period: float = .2,
    ):

        if not channel:
            raise ValueError('This class needs a live paramiko channel.')
        self._holdover_buf = []
        self.channel = channel
        self.timeout_seconds = timeout_seconds
        self.block_size = block_size
        self.sleep_period = sleep_period
        self.exit_status = None
        self.is_read_complete = False

    @staticmethod
    def sleep_timeout(start_time: float = None):
        if start_time is None:
            raise ValueError('Must have a start time')

            time.sleep(self.sleep_period)

            if default_timer() - start_time > self.timeout_seconds:
                raise TimeoutError('Timed out waiting for stream')

    def read_channel(self):

        st = default_timer()
        # Chill until we have data or an exit status
        while True:
            if self.channel.recv_ready():
                break
            if self.channel.exit_status_ready():
                break

            self.sleep_timeout(st)

        # yield data until the pipe runs dry
        data=None
        while True:
            data = self.channel.recv(self.block_size)

            if not data:
                break

            yield data

        st = default_timer()
        while not self.channel.exit_status_ready():
            self.sleep_timeout(st)

        self.exit_status = self.channel.recv_exit_status()
        return f'End of stream, exit code is {self.exit_status}.'


class ByteStreamStringParser(object):
    '''
    This class creates an iterator to yield strings out
    of a byte stream.  Stream is obtained from a
    paramiko channel
    '''

    def __init__(self):
        self._holdover_buf = []

    def parse_stream(self, byte_stream: ByteIterator = None) -> StringIterator:

        if byte_stream is None:
            raise ValueError('Need a byte stream to parse')

        for chunk in byte_stream:
            line = chunk.decode('utf-8')

            if line.find('\n') < 0:
                self._holdover_buf.append(line)
                continue

            chunks = line.split('\n')

            if not chunks[-1]:
                chunks.pop()

            if self._holdover_buf:
                self._holdover_buf.append(chunks[0])
                chunks[0] = ''.join(self._holdover_buf)
                self._holdover_buf.clear()

            if not line.endswith('\n'):
                self._holdover_buf.append(chunks.pop())

            output = [x if not x.endswith('\r') else x[:-1] for x in chunks]

            for rec in output:
                yield ''.join([rec, '\n'])

        # if anything is left in the buffer, flush it
        if self._holdover_buf:
            yield ''.join(self._holdover_buf)

        # StopIteration will contain the following for the exception string
        return 'End of stream'


class HeaderTrailerFilter(object):
    """
    This class looks for start and stop lines and
    """

    def __init__(
            self,
            success_code: int=0,
    ):
        self._start_walk = START_TTY
        self._end_walk = END_TTY
        self._first = False
        self._last = False
        self._good_exit = False
        self._exit_regex = re.compile('exit_code=(\d+)')
        self._success_code = str(success_code)

    def validate_stream(
            self,
            stream: StringIterator = None,
    ):

        if not stream:
            raise ValueError('StringIterator must exist')

        for line in stream:

            # Trailer record was found.  Looking for exit_code=\d+ now
            if self._last:
                match = self._exit_regex.search(line)
                # Do we have a regex hit
                if match:
                    # If exit is a zero, fail nice
                    if match.group(1) == self._success_code:
                        self._good_exit = True
                    break
                # Keep looping to end or match
                continue

            # loop until we find the start header
            if not self._first:
                if line.startswith(self._start_walk):
                    self._first = True
                continue

            if not self._last:
                if line.startswith(self._end_walk):
                    self._last = True
                    continue

            yield line

        if self._good_exit:
            # StopIteration
            return 'End of stream'

        raise EOFError('Did not receive good exit code.')


class SshConnector(object):

    def __enter__(self):

        self._client.set_missing_host_key_policy(client.AutoAddPolicy())

        logging.info(
            f"Connecting to {self.username}@{self.hostname}:{self.port}."
        )

        self._client.connect(
            hostname=self.hostname,
            username=self.username,
            key_filename=self.key_file,
            port=self.port
        )

        return self

    def get_sftp_client(self):
        return self._client.open_sftp()

    def get_default_private_key(self, key_file: str=None) -> str:

        if key_file and os.path.isfile(key_file):
            return key_file

        home_dir = os.environ.get('HOME', '')
        key_path = '/'.join([home_dir,
                             '.ssh',
                             'id_rsa',
                             ])

        return key_path if os.path.isfile(key_path) else None

    def _close_channel(self):

        if self._client:
            try:
                self._client.close()
            except SSHException:
                pass

    def __exit__(self, exception_type, exception_value, traceback):

        logging.info(
            f"Closing connection to {self.hostname}."
        )
        self._close_channel()
        return False

    def __init__(
            self,
            hostname: str = None,
            username: str = None,
            key_file: str = None,
            port: int = 22,
    ):

        self._client = client.SSHClient()
        self.hostname = hostname
        self.username = username or os.getlogin()
        self.port = port
        self.key_file = self.get_default_private_key(key_file=key_file)
        self.temp_dir = mktemp(prefix='reflect_', dir='/tmp')

    def run_remote_command(
        self,
        command: str = None,
        get_pty: bool = False,
        stdin_data: BytesIO = None,
    ) -> StringIterator:

        if not command:
            raise ValueError("Command cannot be empty")

        try:
            logging.info(f"Executing command: {command}")
            (stdin, stdout, stderr) = self._client.exec_command(
                command,
                get_pty=get_pty,
            )

            logging.info("Waiting for results.")

            if stdin_data:
                data = stdin_data.read(1024)
                while data:
                    stdin.channel.send(data)
                    data = stdin_data.read(1024)

            stdin.flush()
            stdin.channel.shutdown_write()

            byte_stream = FetchChannelStream(channel=stdout.channel)
            string_parser = ByteStreamStringParser()

            for string in string_parser.parse_stream(byte_stream=byte_stream.read_channel()):
                yield string

            exit_status = byte_stream.exit_status

            logging.info(f"Exit status: {exit_status}")

            if exit_status == 0:
                return 'End of command output'

            raise SSHRunException('non-zero command exit status')

        except SSHException as ex:
            logging.error("Unable to gather results")
            logging.error("Exception was thrown", ex)

    def run_tty_command(
            self,
            command=None,
            input_file_data: IO=None,
            output_file_data: IO=None,
            in_file: str = None,
            out_file: str = None,
            success_code: int=0,
    ) -> BytesIO:
        """
        Running command that needs a pty
        """

        if not command:
            raise ValueError('Command cannot be empty')

        channel: Channel = self._client.invoke_shell(width=1000)

        with SftpWrapper(self._client.open_sftp(), self.temp_dir) as sftp:
            if in_file and input_file_data:
                sftp.put_file_handle(in_file, input_file_data)

            channel.send(command)

            channel_fetcher = FetchChannelStream(channel=channel)
            stream_parser = ByteStreamStringParser()
            stream_filter = HeaderTrailerFilter(success_code=success_code)

            for line in stream_filter.validate_stream(
                    stream=stream_parser.parse_stream(
                        byte_stream=channel_fetcher.read_channel()
                    )
            ):
                yield line

            if out_file and output_file_data:
                fh = sftp.get_file_handle(out_file)
                sftp.remove_file(out_file)
                output_file_data.truncate(0)
                output_file_data.seek(0)
                output_file_data.write(fh.read(-1))
                output_file_data.seek(0)

            if in_file and input_file_data:
                sftp.remove_file(in_file)

        channel.close()

        return 'tty read complete.'


class SSHRunException(Exception):
    pass


class SftpWrapper(object):
    """
    Wrapper around Paramiko's SFTP client.
    This is used to transmit patch files to and from the system
    """

    def download_callback(self, bytes_xferd: int, bytes_total: int):
        log.info(f'Downloaded {bytes_xferd}/{bytes_total}.')

    def upload_callback(self, bytes_xferd: int, bytes_total: int):
        log.info(f'Uploaded {bytes_xferd}/{bytes_total}.')

    def __init__(self, open_sftp_client: SFTPClient, temp_dir: str=None):
        self._sftp_client: SFTPClient = open_sftp_client
        self.temp_dir = temp_dir

    def put_file_handle(self, remote_name: str, file_handle: BytesIO):
        size = len(file_handle.getvalue())

        self._sftp_client.putfo(
            fl=file_handle,
            remotepath=remote_name,
            file_size=size,
            callback=self.upload_callback,
            confirm=True,
        )

    # noinspection PyTypeChecker
    def get_file_handle(self, remote_name: str):
        file_handle: BinaryIO = BytesIO()
        self._sftp_client.getfo(
            remote_name,
            file_handle,
            callback=self.download_callback,
        )

        file_handle.seek(0)
        return file_handle

    def remove_file(self, filename):
        self._sftp_client.remove(filename)

    def __enter__(self):
        if self.temp_dir:
            self._sftp_client.mkdir(self.temp_dir, 0o700)

        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if self.temp_dir:
            self._sftp_client.rmdir(self.temp_dir)

        self._sftp_client.close()
