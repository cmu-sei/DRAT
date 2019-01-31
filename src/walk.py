#!/usr/bin/env python
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



import os
import os.path
import sys, errno
import stat
import platform as plat
from hashlib import sha256, md5
import grp
import pwd
import re

try:
    broken_pipe_error = BrokenPipeError
except NameError:
    broken_pipe_error = IOError

try:
    """
    magic is a wrapper around the libmagic file identification library.

    See README for more information.

    Usage:

    >>> import magic
    >>> magic.from_file("testdata/test.pdf")
    'PDF document, version 1.2'
    >>> magic.from_file("testdata/test.pdf", mime=True)
    'application/pdf'
    >>> magic.from_buffer(open("testdata/test.pdf").read(1024))
    'PDF document, version 1.2'
    >>>


    """

    import glob
    import ctypes
    import ctypes.util
    import threading

    from ctypes import c_char_p, c_int, c_size_t, c_void_p


    class MagicException(Exception):
        def __init__(self, message):
            super(MagicException, self).__init__(message)
            self.message = message


    class Magic:
        """
        Magic is a wrapper around the libmagic C library.

        """

        def __init__(self, mime=False, magic_file=None, mime_encoding=False,
                     keep_going=False, uncompress=False):
            """
            Create a new libmagic wrapper.

            mime - if True, mimetypes are returned instead of textual descriptions
            mime_encoding - if True, codec is returned
            magic_file - use a mime database other than the system default
            keep_going - don't stop at the first match, keep going
            uncompress - Try to look inside compressed files.
            """
            self.flags = MAGIC_NONE
            if mime:
                self.flags |= MAGIC_MIME
            if mime_encoding:
                self.flags |= MAGIC_MIME_ENCODING
            if keep_going:
                self.flags |= MAGIC_CONTINUE

            if uncompress:
                self.flags |= MAGIC_COMPRESS

            self.cookie = magic_open(self.flags)
            self.lock = threading.Lock()
            
            magic_load(self.cookie, magic_file)

        def from_buffer(self, buf):
            """
            Identify the contents of `buf`
            """
            with self.lock:
                try:
                    return maybe_decode(magic_buffer(self.cookie, buf))
                except MagicException as e:
                    return self._handle509Bug(e)

        def from_file(self, filename):
            # raise FileNotFoundException or IOError if the file does not exist
            with open(filename):
                pass
            with self.lock:
                try:
                    return maybe_decode(magic_file(self.cookie, filename))
                except MagicException as e:
                    return self._handle509Bug(e)

        def _handle509Bug(self, e):
            # libmagic 5.09 has a bug where it might fail to identify the
            # mimetype of a file and returns null from magic_file (and
            # likely _buffer), but also does not return an error message.
            if e.message is None and (self.flags & MAGIC_MIME):
                return "application/octet-stream"
            else:
                raise e
            
        def __del__(self):
            # no _thread_check here because there can be no other
            # references to this object at this point.

            # during shutdown magic_close may have been cleared already so
            # make sure it exists before using it.

            # the self.cookie check should be unnecessary and was an
            # incorrect fix for a threading problem, however I'm leaving
            # it in because it's harmless and I'm slightly afraid to
            # remove it.
            if self.cookie and magic_close:
                magic_close(self.cookie)
                self.cookie = None

    _instances = {}

    def _get_magic_type(mime):
        i = _instances.get(mime)
        if i is None:
            i = _instances[mime] = Magic(mime=mime)
        return i

    def from_file(filename, mime=False):
        """"
        Accepts a filename and returns the detected filetype.  Return
        value is the mimetype if mime=True, otherwise a human readable
        name.

        >>> magic.from_file("testdata/test.pdf", mime=True)
        'application/pdf'
        """
        m = _get_magic_type(mime)
        return m.from_file(filename)

    def from_buffer(buffer, mime=False):
        """
        Accepts a binary string and returns the detected filetype.  Return
        value is the mimetype if mime=True, otherwise a human readable
        name.

        >>> magic.from_buffer(open("testdata/test.pdf").read(1024))
        'PDF document, version 1.2'
        """
        m = _get_magic_type(mime)
        return m.from_buffer(buffer)




    libmagic = None
    # Let's try to find magic or magic1
    dll = ctypes.util.find_library('magic') or ctypes.util.find_library('magic1') or ctypes.util.find_library('cygmagic-1')

    # This is necessary because find_library returns None if it doesn't find the library
    if dll:
        libmagic = ctypes.CDLL(dll)

    if not libmagic or not libmagic._name:
        windows_dlls = ['magic1.dll','cygmagic-1.dll']
        platform_to_lib = {'darwin': ['/opt/local/lib/libmagic.dylib',
                                      '/usr/local/lib/libmagic.dylib'] +
                             # Assumes there will only be one version installed
                             glob.glob('/usr/local/Cellar/libmagic/*/lib/libmagic.dylib'),
                           'win32': windows_dlls,
                           'cygwin': windows_dlls,
                           'linux': ['libmagic.so.1'],    # fallback for some Linuxes (e.g. Alpine) where library search does not work
                          }
        platform = 'linux' if sys.platform.startswith('linux') else sys.platform
        for dll in platform_to_lib.get(platform, []):
            try:
                libmagic = ctypes.CDLL(dll)
                break
            except OSError:
                pass

    if not libmagic or not libmagic._name:
        # It is better to raise an ImportError since we are importing magic module
        raise ImportError('failed to find libmagic.  Check your installation')

    magic_t = ctypes.c_void_p

    def errorcheck_null(result, func, args):
        if result is None:
            err = magic_error(args[0])
            raise MagicException(err)
        else:
            return result

    def errorcheck_negative_one(result, func, args):
        if result is -1:
            err = magic_error(args[0])
            raise MagicException(err)
        else:
            return result


    # return str on python3.  Don't want to unconditionally
    # decode because that results in unicode on python2
    def maybe_decode(s):
        if str == bytes:
            return s
        else:
            return s.decode('utf-8')
        
    def coerce_filename(filename):
        if filename is None:
            return None

        # ctypes will implicitly convert unicode strings to bytes with
        # .encode('ascii').  If you use the filesystem encoding 
        # then you'll get inconsistent behavior (crashes) depending on the user's
        # LANG environment variable
        is_unicode = (sys.version_info[0] <= 2 and
                      isinstance(filename, unicode)) or \
                      (sys.version_info[0] >= 3 and
                       isinstance(filename, str))
        if is_unicode:
            return filename.encode('utf-8')
        else:
            return filename

    magic_open = libmagic.magic_open
    magic_open.restype = magic_t
    magic_open.argtypes = [c_int]

    magic_close = libmagic.magic_close
    magic_close.restype = None
    magic_close.argtypes = [magic_t]

    magic_error = libmagic.magic_error
    magic_error.restype = c_char_p
    magic_error.argtypes = [magic_t]

    magic_errno = libmagic.magic_errno
    magic_errno.restype = c_int
    magic_errno.argtypes = [magic_t]

    _magic_file = libmagic.magic_file
    _magic_file.restype = c_char_p
    _magic_file.argtypes = [magic_t, c_char_p]
    _magic_file.errcheck = errorcheck_null

    def magic_file(cookie, filename):
        return _magic_file(cookie, coerce_filename(filename))

    _magic_buffer = libmagic.magic_buffer
    _magic_buffer.restype = c_char_p
    _magic_buffer.argtypes = [magic_t, c_void_p, c_size_t]
    _magic_buffer.errcheck = errorcheck_null

    def magic_buffer(cookie, buf):
        return _magic_buffer(cookie, buf, len(buf))


    _magic_load = libmagic.magic_load
    _magic_load.restype = c_int
    _magic_load.argtypes = [magic_t, c_char_p]
    _magic_load.errcheck = errorcheck_negative_one

    def magic_load(cookie, filename):
        return _magic_load(cookie, coerce_filename(filename))

    magic_setflags = libmagic.magic_setflags
    magic_setflags.restype = c_int
    magic_setflags.argtypes = [magic_t, c_int]

    magic_check = libmagic.magic_check
    magic_check.restype = c_int
    magic_check.argtypes = [magic_t, c_char_p]

    magic_compile = libmagic.magic_compile
    magic_compile.restype = c_int
    magic_compile.argtypes = [magic_t, c_char_p]



    MAGIC_NONE = 0x000000 # No flags
    MAGIC_DEBUG = 0x000001 # Turn on debugging
    MAGIC_SYMLINK = 0x000002 # Follow symlinks
    MAGIC_COMPRESS = 0x000004 # Check inside compressed files
    MAGIC_DEVICES = 0x000008 # Look at the contents of devices
    MAGIC_MIME = 0x000010 # Return a mime string
    MAGIC_MIME_ENCODING = 0x000400 # Return the MIME encoding
    MAGIC_CONTINUE = 0x000020 # Return all matches
    MAGIC_CHECK = 0x000040 # Print warnings to stderr
    MAGIC_PRESERVE_ATIME = 0x000080 # Restore access time on exit
    MAGIC_RAW = 0x000100 # Don't translate unprintable chars
    MAGIC_ERROR = 0x000200 # Handle ENOENT etc as real errors

    MAGIC_NO_CHECK_COMPRESS = 0x001000 # Don't check for compressed files
    MAGIC_NO_CHECK_TAR = 0x002000 # Don't check for tar files
    MAGIC_NO_CHECK_SOFT = 0x004000 # Don't check magic entries
    MAGIC_NO_CHECK_APPTYPE = 0x008000 # Don't check application type
    MAGIC_NO_CHECK_ELF = 0x010000 # Don't check for elf details
    MAGIC_NO_CHECK_ASCII = 0x020000 # Don't check for ascii files
    MAGIC_NO_CHECK_TROFF = 0x040000 # Don't check ascii/troff
    MAGIC_NO_CHECK_FORTRAN = 0x080000 # Don't check ascii/fortran
    MAGIC_NO_CHECK_TOKENS = 0x100000 # Don't check ascii/tokens

    is_magic = True

except ImportError:
    is_magic = False


DIR_SKIP = {
}

PRUNE_LIST = {
    # Skip this app's pid.. if not, app will freeze
    '/proc': re.compile(
        "^" +
        str(os.getpid()) +
        "$"
    ),
    '/sys': re.compile('.*')
}


def remove_skipped(dest=None, dirs=None):
    if not dest or not dirs:
        return

    # prune pids from /proc dir
    if dest in PRUNE_LIST.keys():
        prune_list = []
        for d in dirs:
            if PRUNE_LIST[dest].match(d):
                prune_list.append(d)
        for d in prune_list:
            dirs.remove(d)

    skips = DIR_SKIP.get(dest, None)

    if not skips:
        return

    for skip in skips:
        if skip in dirs:
            dirs.remove(skip)


def walk_filesystem(root_dir='/'):
    # yield root aka / information
    yield get_file_info(os.path.sep)

    for dest, dirs, files in os.walk(root_dir):

        remove_skipped(dest=dest, dirs=dirs)

        if dest[-1] == os.path.sep:
            sep = ''
        else:
            sep = os.path.sep

        for direct in dirs:
            yield get_file_info(
                sep.join([
                    dest,
                    direct,
                ])
            )

        for rec in files:
            yield get_file_info(
                sep.join([
                    dest,
                    rec,
                ])
            )


def get_type(file_path):

    result = 'U'

    try:
        fstat = os.lstat(file_path)
    except OSError:
        fstat = None
        result = 'X'

    if result == 'X':
        pass
    elif stat.S_ISREG(fstat.st_mode):
        result = 'F'
    elif stat.S_ISDIR(fstat.st_mode):
        result = 'D'
    elif stat.S_ISLNK(fstat.st_mode):
        result = 'S'
    elif os.path.ismount(file_path):
        result = 'M'
    elif stat.S_ISCHR(fstat.st_mode):
        result = 'C'
    elif stat.S_ISBLK(fstat.st_mode):
        result = 'B'
    elif stat.S_ISFIFO(fstat.st_mode):
        result = 'O'
    elif stat.S_ISSOCK(fstat.st_mode):
        result = 'K'

    return {
        'type': result,
        'stat': fstat,
    }


def get_file_info(file_path):

    file_info = {
        'path': file_path,
        'type': 'U',
        'target': '',
        'target_type': '',
        'uid': 0,
        'gid': 0,
        'user': '',
        'group': '',
        'md5': '',
        'sha256': '',
        'size': 0,
        'mode': '',
        'perm': '',
        'info': '',
    }

    info = get_type(file_path)
    file_info['type'] = info['type']
    fstat = info['stat']

    if file_info['type'] == 'S':
        try:
            file_info['target'] = os.readlink(file_path)
        except OSError:
            pass

        if file_info['target']:
            if file_info['target'].startswith(os.path.sep):
                target_path = file_info['target']
            else:
                target_path = '/'.join([
                    os.path.dirname(file_path),
                    file_info['target'],
                ])

            file_info['target_type'] = get_type(target_path).get('type')

    if not fstat:
        print(file_path)
    file_info['uid'] = fstat.st_uid
    file_info['gid'] = fstat.st_gid

    if (
            is_magic and file_info['type'] == 'F' and
            not file_path.startswith('/proc')
    ):
        file_info['info'] = from_file(file_path, mime=True)

    if file_info['type'] == 'F' and not file_path.startswith('/proc'):
        file_info['md5'], file_info['sha256'] = generate_hashes(file_path)

    try:
        file_info['user'] = pwd.getpwuid(fstat.st_uid).pw_name
    except KeyError:
        file_info['user'] = fstat.st_uid

    try:
        file_info['group'] = grp.getgrgid(fstat.st_gid).gr_name
    except KeyError:
        file_info['group'] = fstat.st_gid

    file_info['size'] = fstat.st_size
    # %o is used to return a standard string
    # without a prefix of 0o
    file_info['mode'] = '%o' % fstat.st_mode
    file_info['perm'] = '%o' % stat.S_IMODE(fstat.st_mode)

    return file_info


def get_mount_info(mountpoint=None):

    result = ''

    if UNAME == 'Darwin':
        return result

    with open('/proc/mounts', 'r') as mounts:

        line = mounts.readline()

        while line:
            fs = line.strip()
            info = fs.split(' ')

            if len(info) > 1 and info[1] == mountpoint:
                result = info[1]

            line = mounts.readline()

    return result


def generate_hashes(file_path=None):

    CHUNK_SIZE = 16384

    md5sum = md5()
    sha256sum = sha256()

    with open(file_path, 'rb') as f:

        blob = f.read(CHUNK_SIZE)

        while blob:

            md5sum.update(blob)
            sha256sum.update(blob)

            blob = f.read(CHUNK_SIZE)

    return md5sum.hexdigest(), sha256sum.hexdigest()


def main():

    global UNAME
    UNAME = plat.uname()

    if isinstance(UNAME, tuple):
        UNAME = UNAME[0]
    else:
        UNAME = UNAME.system

    slashes = '/' * 40

    try:
        sys.stdout.write('{0} START TTY {0}\n'.format(slashes))

        keys = None
        key_count = 0
        first = False
        count = 0

        for rec in walk_filesystem():

            if not first:
                keys = rec.keys()
                key_count = len(keys)
                counter = 0
                for key in keys:
                    counter += 1
                    if counter == key_count:
                        eol = '\n'
                    else:
                        eol = '\t'

                    sys.stdout.write(key)
                    sys.stdout.write(eol)

                sys.stdout.flush()
                first = True

            counter = 0
            for value in rec.values():
                counter += 1
                if counter == key_count:
                    eol = '\n'
                else:
                    eol = '\t'

                sys.stdout.write(str(value))
                sys.stdout.write(eol)

            count += 1
            if count % 1000 == 0:
                sys.stdout.flush()

        sys.stdout.write('{0} END TTY {0}\n'.format(slashes))
    except broken_pipe_error as e:
        if e.errno == errno.EPIPE:
            pass
        else:
            raise


if __name__ == '__main__':
    main()
    sys.stderr.close()
