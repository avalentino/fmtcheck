#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Ensure the source code conformity to basic formatting standards.

The tool provides sub-commands to "check" the conformity of all files in a
source tree to basic formatting standards, to "fix" common formatting
mistakes, and also to set and update the copyright statement
("update-copyright" sub-command) in source files.

"""


import io
import os
import re
import sys
import copy
import enum
import stat
import shutil
import fnmatch
import logging
import argparse
import datetime
import subprocess
import collections
import configparser

from operator import xor

try:
    from os import EX_OK
except ImportError:
    EX_OK = 0
EX_FAILURE = -1


try:
    import argcomplete
except ImportError:
    argcomplete = False
else:
    PYTHON_ARGCOMPLETE_OK = True


__version__ = '1.4.0b1'
PROG = 'fmtcheck'

LOGFMT = '%(levelname)s: %(message)s'

DEFAULT_CLANG_FORMAT = 'clang-format'


class Eol(enum.Enum):
    NATIVE = os.linesep
    UNIX = '\n'
    WIN = '\r\n'


class Mode(enum.Enum):
    BINARY = 'rb'
    TEXT = 'r'


ScanConfig = collections.namedtuple(
    'ScanConfig',
    ['path_patterns', 'skip_path_patterns', 'skip_data_patterns'])


DEFAULT_CFG = ScanConfig(
    path_patterns=[
        '*.[ch]',  '*.[ch]pp', '*.[ch]xx',
        '*.txt', '*.cmake',
        '*.sh', '*.bash', '*.bat',
        '*.xsd', '*.xml',
    ],
    skip_path_patterns=[
        '.*',
    ],
    skip_data_patterns=[],
)


class SimpleDirEntry(object):
    """Instantiable class with the same interface of os.DirEntry."""

    __slots__ = ['_path']

    def __init__(self, path):
        self._path = path

    @property
    def name(self):
        """The entry's base path name."""

        return os.path.basename(self._path)

    @property
    def path(self):
        """The entry's full path name."""

        return self._path

    def inode(self):
        """'Return inode of the entry."""

        return os.stat(self._path).st_ino

    def is_dir(self):
        """Return True if the entry is a directory."""

        return os.path.isdir(self._path)

    def is_file(self):
        """Return True if the entry is a file."""

        return os.path.isfile(self._path)

    def is_symlink(self):
        """Return True if the entry is a symbolic link."""

        return os.path.islink(self._path)

    def stat(self):
        """Return stat_result object for the entry."""

        return os.stat(self._path)

    def __fspath__(self):
        return os.fspath(self._path)

    def __repr__(self):
        return '<{} {!r}>'.format(self.__class__.__name__, self.name)


class SrcTree(object):
    """Tree object that provides smart iteration features."""

    def __init__(self, path='.', mode=Mode.TEXT,
                 path_patterns=DEFAULT_CFG.path_patterns,
                 skip_path_patterns=DEFAULT_CFG.skip_path_patterns,
                 skip_data_patterns=DEFAULT_CFG.skip_data_patterns):
        self.path = path
        self.mode = Mode(mode)

        self._path_patterns = None
        self._skip_path_patterns = None
        self._skip_data_patterns = None

        self._path_re = None
        self._skip_path_re = None
        self._skip_data_re = None

        self.path_patterns = path_patterns
        self.skip_path_patterns = skip_path_patterns
        self.skip_data_patterns = skip_data_patterns

    @property
    def path_patterns(self):
        return self._path_patterns

    @path_patterns.setter
    def path_patterns(self, patterns):
        self._path_patterns = patterns
        if patterns:
            self._path_re = re.compile(
                '|'.join(fnmatch.translate(p) for p in patterns))
        else:
            self._path_re = re.compile('.*')

    @property
    def skip_path_patterns(self):
        return self._skip_path_patterns

    @skip_path_patterns.setter
    def skip_path_patterns(self, patterns):
        self._skip_path_patterns = patterns

        if patterns:
            pattern = '|'.join(fnmatch.translate(p) for p in patterns)
        else:
            # does not match anything
            pattern = '-^'

        self._skip_path_re = re.compile(pattern)

    @property
    def skip_data_patterns(self):
        return self._skip_data_patterns

    @skip_data_patterns.setter
    def skip_data_patterns(self, patterns):
        self._skip_data_patterns = patterns

        if patterns:
            pattern = '|'.join(patterns)
        else:
            # does not match anything
            pattern = '-^'

        if self.mode == Mode.BINARY:
            pattern = pattern.encode('ascii')

        self._skip_data_re = re.compile(pattern)

    @staticmethod
    def _scan(path):
        if os.path.isfile(path):
            return [SimpleDirEntry(path)]
        else:
            logging.debug('scanning %r', path)
            return os.scandir(path)

    def __iter__(self):
        for entry in self._scan(self.path):
            if self._skip_path_re.match(entry.name):
                logging.debug('skipping %r', entry.path)
                continue

            if entry.is_dir():
                subtree = copy.copy(self)
                subtree.path = entry.path

                # @COMPATBILITY: "yeild form" is new in Python 3.3
                # yield from subtree
                for item in subtree:
                    yield item
            elif self._path_re.match(entry.name):
                try:
                    with open(entry.path, str(self.mode.value)) as fd:
                        data = fd.read()
                except UnicodeDecodeError as ex:
                    logging.warning(
                        'unable to read {!r}: {}'.format(entry.path, ex))
                else:
                    if self._skip_data_re.search(data):
                        logging.debug('skipping %r', entry.path)
                    else:
                        yield entry, data

            else:
                logging.debug('skipping %r', entry.path)


def _isexecutable(mode):
    return mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class CheckTool(object):
    """Check the conformity of source code to basic standards.

    Available checks include: end of line (EOL) consistency,
    presence of trailing spaces at the end of a source code line,
    presence of tabs, conformity to the ASCII encoding,
    maximum line length, presence of an End Of Line (EOL) character
    before the End Of File (EOF),
    presence of a copyright statement is source files,
    file permissions (source files shall not be executables),
    formatting according clang-format standards.

    By default the tool prints how many files fail the check,
    for each of the selected checks.

    """

    COPYRIGHT_RE = re.compile(
        b'(?P<copyright>[Cc]opyright([ \t]+(\([Cc]\)))?)[ \t]+\d{4}')
    RELATIVE_INCLUDE_RE = re.compile(
        b'^[ \t]*#include[ \t]"\.\.', re.MULTILINE)
    #   b'^[ \t]*#include[ \t]"\.{1,2}', re.MULTILINE)  # stricter check

    CXX_PATH_RE = re.compile('|'.join(
        fnmatch.translate(p) for p in ('*.[ch]', '*.[ch]pp', '*.[ch]xx',)))

    def __init__(self, failfast=False, scancfg=DEFAULT_CFG, **kwargs):
        self.failfast = failfast
        self.scancfg = scancfg

        self.check_tabs = bool(kwargs.pop('check_tabs', True))
        self.check_eol = bool(kwargs.pop('check_eol', True))
        self.check_trailing = bool(kwargs.pop('check_trailing', True))
        self.check_encoding = bool(kwargs.pop('check_encoding', True))
        self.check_eol_at_eof = bool(kwargs.pop('check_eol_at_eof', True))
        self.check_relative_include = bool(
            kwargs.pop('check_relative_include', True))
        self.check_copyright = bool(kwargs.pop('check_copyright', True))
        self.check_mode = bool(kwargs.pop('check_mode', True))

        self.clang_format = kwargs.pop('clang_format', False)
        self.maxlinelen = int(kwargs.pop('maxlinelen', 0))
        self.eol = Eol(kwargs.pop('eol', Eol.NATIVE))
        self.encoding = kwargs.pop('encoding', 'ascii')

        if kwargs:
            key = next(iter(kwargs.keys()))
            raise TypeError(
                '__init__() got an unexpected keyword argument '
                '{!r}'.format(key))

        self._checklist = collections.OrderedDict()

    def _encoding_checker(self, data):
        for lineno, line in enumerate(data.splitlines(), 1):
            try:
                line.decode(self.encoding)
            except UnicodeDecodeError:
                logging.info(
                    'unable to decode line n. {}: {!r}'.format(lineno, line))
                return True

    def _linelen_checker(self, data):
        if self.eol is None:
            line_iterator = data.splitlines()
        else:
            line_iterator = data.split(self.eol.value.encode('ascii'))

        for lineno, line in enumerate(line_iterator):
            if len(line) > self.maxlinelen:
                logging.info(
                    'line %d is %d characters long', lineno+1, len(line))
                return True

    @staticmethod
    def _eol_at_eof_checker(data):
        last_eol_index = data.rfind(b'\n')
        if last_eol_index == -1 or data[last_eol_index:].strip() != b'':
            return True

    def _relative_include_checker(self, data):
        if self.RELATIVE_INCLUDE_RE.search(data):
            return True

    def _copyright_checker(self, data):
        if not self.COPYRIGHT_RE.search(data):
            return True

    @staticmethod
    def _mode_checker(direntry):
        mode = direntry.stat().st_mode
        if _isexecutable(mode):
            return True

    def _clang_format_checker(self, direntry, data):
        # assert(self.CXX_PATH_RE.match(direntry.name))

        cmd = [
            self.clang_format,
            '-assume-filename={}'.format(direntry.path),
            '-style=file',
        ]

        completed_process = subprocess.run(cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, input=data)

        if completed_process.returncode != os.EX_OK:
            logging.error(
                '{!r} called on {!r} exited with return code {}'.format(
                    self.clang_format, direntry.path,
                    completed_process.returncode))
            return True

        if completed_process.stdout != data:
            if logging.getLogger().level <= logging.DEBUG:
                # format diff

                import difflib
                original = data.decode('utf-8')
                reformatted = completed_process.stdout.decode('utf-8')

                diff = ''.join(difflib.unified_diff(
                    original.splitlines(keepends=True),
                    reformatted.splitlines(keepends=True),
                    fromfile=direntry.name,
                    tofile='reformatted ' + direntry.name))

                logging.info('clang format diff for %s\n\n%s',
                             direntry.path, diff)

            return True

    def _get_checklist(self):
        checklist = collections.OrderedDict()

        if self.check_tabs:
            tab_re = re.compile(b'\t')
            checklist['tabs'] = tab_re.search

        if self.check_eol:
            if self.eol.value == Eol.UNIX.value:
                invalid_eol_re = re.compile(b'\r\n')
            elif self.eol.value == Eol.WIN.value:
                invalid_eol_re = re.compile(b'(?<!\r)\n')
            else:
                raise ValueError(
                    'unexpected end of line: {!r}'.format(self.eol))

            checklist['invalid EOL'] = invalid_eol_re.search

        if self.check_trailing:
            trailing_spaces_re = re.compile(
                b'[ \t]' + self.eol.value.encode('ascii'))
            checklist['trailing spaces'] = trailing_spaces_re.search

        if self.check_encoding:
            key = 'not {}'.format(self.encoding)
            checklist[key] = self._encoding_checker

        if self.check_eol_at_eof:
            checklist['no eol at eof'] = self._eol_at_eof_checker

        if self.check_relative_include:
            checklist['relative include'] = self._relative_include_checker

        if self.check_copyright:
            checklist['no copyright'] = self._copyright_checker

        if self.maxlinelen:
            checklist['line tool long'] = self._linelen_checker

        return checklist

    def _check_file_core(self, direntry, data):
        filename = direntry.path

        logging.debug('checking %r', filename)

        stats = collections.Counter()

        for key, checkfunc in self._checklist.items():
            if checkfunc(data):
                stats[key] += 1
                logging.info('{}: {}'.format(filename, key))
                if self.failfast:
                    return stats

        if self.check_mode and self._mode_checker(direntry):
            key = 'mode (executable bit)'
            stats[key] += 1
            logging.info('{}: {}'.format(filename, key))
            if self.failfast:
                return stats

        if self.clang_format and self.CXX_PATH_RE.match(direntry.name):
            if self._clang_format_checker(direntry, data):
                key = 'clang-format'
                stats[key] += 1
                logging.info('{}: {}'.format(filename, key))
                if self.failfast:
                    return stats

        return stats

    def check_file(self, filename):
        """Perform checks on the specified file."""

        # ensure to be in sync with the current status of flags
        self._checklist = self._get_checklist()

        with open(filename, 'rb') as fd:
            data = fd.read()

        return self._check_file_core(SimpleDirEntry(filename), data)

    def scan(self, path='.'):
        """Perform checks on all source files in path."""

        # ensure to be in sync with the current status of flags
        self._checklist = self._get_checklist()

        stats = collections.Counter()

        srctree = SrcTree(
            path, mode=Mode.BINARY,
            path_patterns=self.scancfg.path_patterns,
            skip_path_patterns=self.scancfg.skip_path_patterns,
            skip_data_patterns=self.scancfg.skip_data_patterns)

        for direntry, data in srctree:
            local_stats = self._check_file_core(direntry, data)
            stats.update(local_stats)

            if self.failfast and stats:
                break

        return stats


class FixTool(object):
    """Fix basic formatting issues.

    Available fixes include: end of line (EOL) consistency,
    trailing spaces removal, substitution of tabs with spaces,
    ensuring that an End Of Line (EOL) character is always present
    before the End Of File (EOF),
    file permissions (source files shall not be executables),
    reformat according to clang-format standards.

    """

    TRIM_RE = re.compile('[ \t]+(?=\n)|[ \t]+$')
    CXX_PATH_RE = CheckTool.CXX_PATH_RE

    def __init__(self, tabsize=4, fix_trailing=True, fix_eof=True,
                 fix_mode=True, clang_format=False, eol=Eol.NATIVE,
                 backup_ext=None, scancfg=DEFAULT_CFG):
        self.tabsize = int(tabsize)
        self.eol = Eol(eol)
        self.fix_trailing = fix_trailing
        self.fix_eof = fix_eof
        self.fix_mode = fix_mode

        self.clang_format = clang_format
        self.backup_ext = backup_ext

        self.scancfg = scancfg

        self._line_fixers = ()

    def _get_line_fixers(self):
        line_fixers = []

        if self.fix_trailing:
            line_fixers.append(
                lambda line: self.TRIM_RE.sub('', line)
            )

        if self.tabsize:
            blanks = ' ' * self.tabsize
            line_fixers.append(
                lambda line: line.replace('\t', blanks)
            )

        return line_fixers

    @staticmethod
    def _eof_fixer(data):
        return data.rstrip() + '\n'

    @staticmethod
    def _mode_fixer(direntry):
        mode = direntry.stat().st_mode
        if _isexecutable(mode):
            mode = xor(mode, stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            os.chmod(direntry.path, mode)

    def _clang_format_fixer(self, direntry, data):
        # assert(self.CXX_PATH_RE.match(direntry.name))

        cmd = [
            self.clang_format,
            '-assume-filename={}'.format(direntry.path),
            '-style=file',
        ]

        # NOTE: The encoding argument is new in Python 3.6
        encoding = sys.getdefaultencoding()
        completed_process = subprocess.run(cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           input=data.encode(encoding),
                                           check=True)

        return completed_process.stdout.decode(encoding)

    def _fix_file_core(self, direntry, data):
        filename = direntry.path

        logging.debug('fixing %r', filename)

        if self.fix_eof:
            data = self._eof_fixer(data)

        istream = io.StringIO(data)
        ostream = io.StringIO()
        for line in istream:
            for line_fixer in self._line_fixers:
                line = line_fixer(line)
            ostream.write(line)

        data = ostream.getvalue()

        if self.clang_format and self.CXX_PATH_RE.match(direntry.name):
            data = self._clang_format_fixer(direntry, data)

        with open(filename, 'w', newline=str(self.eol.value)) as fd:
            fd.write(data)

        if self.fix_mode:
            self._mode_fixer(direntry)

    def fix_file(self, filename, outfile=None):
        """Apply specified fixes on the input data."""

        # ensure to be in sync with the current status of flags
        self._line_fixers = self._get_line_fixers()

        with open(filename, 'rb') as fd:
            data = fd.read()

        if outfile is None:
            outfile = filename

            if self.backup_ext:
                backupfile = filename + self.backup_ext
                shutil.move(filename, backupfile)

        self._fix_file_core(SimpleDirEntry(outfile), data)

    def scan(self, path='.'):
        """Apply fixes to all source files in path."""

        # ensure to be in sync with the current status of flags
        self._line_fixers = self._get_line_fixers()

        srctree = SrcTree(
            path, mode=Mode.TEXT,
            path_patterns=self.scancfg.path_patterns,
            skip_path_patterns=self.scancfg.skip_path_patterns,
            skip_data_patterns=self.scancfg.skip_data_patterns)

        for direntry, data in srctree:
            filename = direntry.path

            if self.backup_ext:
                backupfile = filename + self.backup_ext
                shutil.move(filename, backupfile)

            self._fix_file_core(direntry, data)


class CopyrightTool(object):
    """Update or add the copyright statement is source files.

    The copyright statement in source files is updated to the current year
    (if not differently specified by the user).

    If a source file does not have a copyright statement it can be added
    by providing a suiteble template.

    """

    CHECK_COPYRIGHT_RE = CheckTool.COPYRIGHT_RE.pattern.decode('utf-8')
    COPYRIGHT_RE_TEMPLATE = (
        '(?P<copyright>:?[Cc]opyright:?([ \t]+(\([Cc]\)))?)'
        '[ \t]+(?!%(year)d)'
        '(?P<firstyear>\d{4})'
        '((-|(,\d{4})*,)(?P<lastyear>\d{4})?)?'
    )
    REPL_COPYRIGHT_RE_TEMPLATE = '\g<copyright> \g<firstyear>-%(year)d'

    def __init__(self, copyright_template_path=None, update=True, year=None,
                 backup_ext=None, scancfg=DEFAULT_CFG):
        if year is None:
            year = datetime.date.today().year

        self.copyright_template_path = copyright_template_path
        self._copyright_template_str = ''   # internal cache
        self.update = update

        self.year = year
        self.backup_ext = backup_ext
        self.scancfg = scancfg

        # NOTE: use the % formatting notation
        values = dict(year=year)
        self._copyright_re = re.compile(self.COPYRIGHT_RE_TEMPLATE % values)
        self._repl_copyright_re = self.REPL_COPYRIGHT_RE_TEMPLATE % values
        self._check_copyright_re = re.compile(self.CHECK_COPYRIGHT_RE)

    def _load_copyright_template(self):
        if self.copyright_template_path:
            with open(self.copyright_template_path) as fd:
                data = fd.read()
            self._copyright_template_str = data.format(year=self.year)
        else:
            self._copyright_template_str = None

    def _update_copyright_core(self, direntry, data):
        filename = direntry.path

        logging.debug('updating %r', filename)

        if self.update:
            data = self._copyright_re.sub(self._repl_copyright_re, data)

        if (self._copyright_template_str is not None and
                not self._check_copyright_re.search(data)):
            data = self._copyright_template_str + data

        with open(filename, 'w') as fd:
            fd.write(data)

    def update_copyright(self, filename, outfile=None):
        """Update the copyright in the input file."""

        if self.copyright_template_path:
            self._load_copyright_template()

        with open(filename, 'rb') as fd:
            data = fd.read()

        if outfile is None:
            outfile = filename

            if self.backup_ext:
                backupfile = filename + self.backup_ext
                shutil.move(filename, backupfile)

        self._update_copyright_core(SimpleDirEntry(outfile), data)

    def scan(self, path='.'):
        """Update the copyright in all source files in path."""

        if not self.copyright_template_path and not self.update:
            logging.info('nothing to do: update=False and no template to add')

        if self.copyright_template_path:
            self._load_copyright_template()

        srctree = SrcTree(
            path, mode=Mode.TEXT,
            path_patterns=self.scancfg.path_patterns,
            skip_path_patterns=self.scancfg.skip_path_patterns,
            skip_data_patterns=self.scancfg.skip_data_patterns)

        for direntry, data in srctree:
            filename = direntry.path

            if self.backup_ext:
                backupfile = filename + self.backup_ext
                shutil.move(filename, backupfile)

            self._update_copyright_core(direntry, data)


class ConfigParser(configparser.ConfigParser):

    @staticmethod
    def scancfg_to_dict(scancfg):
        d = collections.OrderedDict()

        if scancfg.path_patterns:
            d['path_patterns'] = collections.OrderedDict(
                ('pattern_{:02d}'.format(i), item)
                for i, item in enumerate(scancfg.path_patterns, 1)
            )

        if scancfg.skip_path_patterns:
            d['skip_path_patterns'] = collections.OrderedDict(
                ('pattern_{:02d}'.format(i), item)
                for i, item in enumerate(scancfg.skip_path_patterns, 1)
            )

        if scancfg.skip_data_patterns:
            d['skip_data_patterns'] = collections.OrderedDict(
                ('pattern_{:02d}'.format(i), item)
                for i, item in enumerate(scancfg.skip_data_patterns, 1)
            )

        return d

    @staticmethod
    def checktool_to_dict(tool):
        d = collections.OrderedDict()

        d['failfast'] = bool(tool.failfast)
        d['check_tabs'] = bool(tool.check_tabs)
        d['check_eol'] = bool(tool.check_eol)
        d['check_trailing'] = bool(tool.check_trailing)
        d['check_encoding'] = bool(tool.check_encoding)
        d['check_eol_at_eof'] = bool(tool.check_eol_at_eof)
        d['check_relative_include'] = bool(tool.check_relative_include)
        d['check_copyright'] = bool(tool.check_copyright)
        d['check_mode'] = bool(tool.check_mode)
        d['clang_format'] = tool.clang_format
        d['maxlinelen'] = int(tool.maxlinelen)
        d['eol'] = tool.eol.name
        d['encoding'] = tool.encoding

        return d

    @staticmethod
    def fixtool_to_dict(tool):
        d = collections.OrderedDict()

        d['tabsize'] = int(tool.tabsize)
        d['eol'] = Eol(tool.eol).name
        d['fix_trailing'] = bool(tool.fix_trailing)
        d['fix_eof'] = bool(tool.fix_eof)
        d['fix_mode'] = bool(tool.fix_mode)

        d['clang_format'] = tool.clang_format
        d['backup'] = bool(tool.backup_ext is not None)

        return d

    @staticmethod
    def update_copyright_tool_to_dict(tool):
        d = collections.OrderedDict()

        if tool.copyright_template_path:
            d['copyright_template_path'] = tool.copyright_template_path

        d['update'] = bool(tool.update)

        if tool.year:
            d['year'] = tool.year

        d['backup'] = bool(tool.backup_ext is not None)

        return d

    def setup_default_config(self):
        self.add_section('logging')
        self.set('logging', 'loglevel', 'WARNING')

        cfg = self.scancfg_to_dict(DEFAULT_CFG)

        cfg['check'] = self.checktool_to_dict(CheckTool())
        cfg['fix'] = self.fixtool_to_dict(FixTool())
        cfg['update-copyright'] = self.update_copyright_tool_to_dict(
            CopyrightTool())

        self.read_dict(cfg)

    def get_scancfg(self):
        if self.has_section('path_patterns'):
            path_patterns = list(self['path_patterns'].values())
        else:
            path_patterns = []

        if self.has_section('skip_path_patterns'):
            skip_path_patterns = list(self['skip_path_patterns'].values())
        else:
            skip_path_patterns = []

        if self.has_section('skip_data_patterns'):
            skip_data_patterns = list(self['skip_data_patterns'].values())
        else:
            skip_data_patterns = []

        scancfg = ScanConfig(
            path_patterns, skip_path_patterns, skip_data_patterns)

        return scancfg

    def _get_loglevel(self):
        sectname = 'logging'
        if sectname in self:
            section = self[sectname]
            if 'loglevel' in section:
                value = self.get(sectname, 'loglevel')
                loglevel = logging.getLevelName(value)
                if not isinstance(loglevel, int):
                    raise ValueError('invalid log level: {!r}'.format(value))
                return loglevel

    def get_checkargs(self):
        d = collections.OrderedDict()

        sectname = 'check'

        if sectname not in self:
            return d

        section = self[sectname]

        for key in ('failfast', 'check_tabs', 'check_eol', 'check_trailing',
                    'check_encoding', 'check_eol_at_eof',
                    'check_relative_include', 'check_copyright', 'check_mode'):
            if key in section:
                d[key] = self.getboolean(sectname, key)

        if 'clang_format' in section:
            try:
                d['clang_format'] = self.getboolean(sectname, 'clang_format')
            except ValueError:
                d['clang_format'] = self.get(sectname, 'clang_format')

        if 'maxlinelen' in section:
            d['maxlinelen'] = self.getint(sectname, 'maxlinelen')

        if 'eol' in section:
            d['eol'] = Eol.__members__[self.get(sectname, 'eol').upper()]

        if 'encoding' in section:
            d['encoding'] = self.get(sectname, 'encoding')

        loglevel = self._get_loglevel()
        if loglevel is not None:
            d['loglevel'] = loglevel

        return d

    def get_fixargs(self):
        d = collections.OrderedDict()

        sectname = 'fix'

        if sectname not in self:
            return d

        section = self[sectname]

        if 'tabsize' in section:
            d['tabsize'] = self.getint(sectname, 'tabsize')

        if 'eol' in section:
            d['eol'] = Eol.__members__[self.get(sectname, 'eol').upper()]

        if 'fix_trailing' in section:
            d['fix_trailing'] = self.getboolean(sectname, 'fix_trailing')

        if 'fix_mode' in section:
            d['fix_mode'] = self.getboolean(sectname, 'fix_mode')

        if 'clang_format' in section:
            d['clang_format'] = self.get(sectname, 'clang_format')

        if self.getboolean(sectname, 'backup', fallback=None):
            d['backup_ext'] = '.bak'

        loglevel = self._get_loglevel()
        if loglevel is not None:
            d['loglevel'] = loglevel

        return d

    def get_update_copyright_args(self):
        d = collections.OrderedDict()

        sectname = 'update-copyright'

        if sectname not in self:
            return d

        section = self[sectname]

        if 'copyright_template_path' in section:
            name = 'copyright_template_path'
            d[name] = self.get(sectname, name)

        if 'update' in section:
            d['update'] = self.getboolean(sectname, 'update')

        if 'year' in section:
            d['year'] = self.getint(sectname, 'year')

        if self.getboolean(sectname, 'backup', fallback=None):
            d['backup_ext'] = '.bak'

        loglevel = self._get_loglevel()
        if loglevel is not None:
            d['loglevel'] = loglevel

        return d

    def get_command_args(self, command):
        if command == 'check':
            return self.get_checkargs()
        elif command == 'fix':
            return self.get_fixargs()
        elif command == 'update-copyright':
            return self.get_update_copyright_args()
        # elif command == 'dumpcfg':
        #     return collections.OrderedDict()
        else:
            raise ValueError('unexpected command: {!r}'.format(command))


def _summary_line(s):
    return s.split('\n\n', 1)[0]


def _set_common_perser_args(parser, backup=False):
    # --- backup -------------------------------------------------------------
    if backup:
        backup_group = parser.add_argument_group('backup')

        backup_group.add_argument(
            '-b', '--backup', action='store_const', default=False,
            const='.bak', help='''backup original file contents on a file
            with the same name + "%(const)s".
            Default no backup is performed.''')

    # --- logging ------------------------------------------------------------
    log_group = parser.add_argument_group('logging')

    log_group.add_argument(
        '-q', '--quiet',
        dest='loglevel', action='store_const', const=logging.ERROR,
        help='suppress standard output, only errors are printed to screen')
    log_group.add_argument(
        '-v', '--verbose',
        dest='loglevel', action='store_const', const=logging.INFO,
        help='enable verbose output')
    log_group.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=logging.DEBUG,
        help='enable debug output')

    # --- scanning -----------------------------------------------------------
    scan_group = parser.add_argument_group('source tree scanning')

    scan_group.add_argument(
        '--patterns', dest='path_patterns',
        help='''comma separated list of glob pattern to scan.
        Default: {}'''.format(','.join(DEFAULT_CFG.path_patterns)))
    scan_group.add_argument(
        '--skip', dest='skip_path_patterns',
        help='''comma separated list of glob pattern to skip.
        Default: {}'''.format(','.join(DEFAULT_CFG.skip_path_patterns)))
    scan_group.add_argument(
        '--no-skip', dest='skip_path_patterns', action='store_const', const=[],
        help='skip no file during the scanning of the directory tree')

    # --- config -------------------------------------------------------------
    config_group = parser.add_argument_group('config')

    config_group.add_argument(
        '-c', '--config', help='path to the configuration file')

    # --- path ---------------------------------------------------------------
    parser.add_argument(
        'paths', nargs='+', metavar='PATH',
        help='root of the source tree to scan (default: %(default)r)')

    return parser


def get_check_parser(parser=None):
    """Build and return the command line parser for the "check" command."""

    if parser is None:
        parser = argparse.ArgumentParser(description=CheckTool.__doc__)
    elif hasattr(parser, 'add_parser'):
        # SubParsersAction
        parser = parser.add_parser(
            'check',
            description=CheckTool.__doc__,
            help=_summary_line(CheckTool.__doc__))

    parser.add_argument(
        '--no-tabs', action='store_false', dest='check_tabs', default=True,
        help='''disable checks on the presence of tabs in the source code
        (default: False)''')
    parser.add_argument(
        '--no-eol', action='store_false', dest='check_eol',
        default=True, help='''disable checks on the EOL consistency
        (default: False). N.B. the system EOL is used as reference''')
    parser.add_argument(
        '--no-trailing', action='store_false', dest='check_trailing',
        default=True, help='''disable checks on trailing spaces i.e. white
        spaces at the end of line (default: False)''')
    parser.add_argument(
        '--no-encoding', action='store_false', dest='check_encoding',
        default=True, help='''disable checks on text encoding:
        source code that is not pure ASCII is considered not valid
        (default: False)''')
    parser.add_argument(
        '--no-eof', action='store_false', dest='check_eol_at_eof',
        default=True, help='''disable checks on the presence of an EOL
        character at the end of the file (default: False)''')
    parser.add_argument(
        '--no-relative-include', action='store_false',
        dest='check_relative_include', default=True,
        help='''disable checks on the presence of C/C++ "#include"
        statements with relative path (default: False)''')
    parser.add_argument(
        '--no-copyright', action='store_false', dest='check_copyright',
        default=True, help='''disable checks on the presence of the
        copyright line is source files (default: False)''')
    parser.add_argument(
        '--no-mode', action='store_false', dest='check_mode',
        default=True, help='''disable checks on file mode bits i.e. permissions
        (default: False)''')

    parser.add_argument(
        '--clang-format', nargs='?', const=DEFAULT_CLANG_FORMAT,
        metavar='CLANG-FORMAT EXECUTABLE',
        help='''checks formatting with clang-format (default: not check). The
        path to the "clang-format" executable can be optionally secified.
        Please remember to use the "--" separator before positional arguments.
        ''')
    parser.add_argument(
        '-l', '--line-length', dest='maxlinelen', type=int, default=0,
        help='''set the maximum line length, if not set (default) disable
        checks on line length''')

    parser.add_argument(
        '-f', '--failfast', action='store_true', default=False,
        help='exit immediately as soon as a check fails')

    parser = _set_common_perser_args(parser)

    return parser


def get_fix_parser(parser=None):
    """Build and return the command line parser for the "fix" command."""

    if parser is None:
        parser = argparse.ArgumentParser(description=FixTool.__doc__)
    elif hasattr(parser, 'add_parser'):
        # SubParsersAction
        parser = parser.add_parser(
            'fix',
            description=FixTool.__doc__,
            help=_summary_line(FixTool.__doc__))

    parser.add_argument(
        '--eol', default=Eol.NATIVE, choices=list(Eol.__members__.keys()),
        help='output end of line (default: native)')
    parser.add_argument(
        '--tabsize', default=4, type=int, help='''specify the number of
        blanks to be used to replace each tab (default: %(default)s).
        To disable tab substitution set tabsize to 0''')
    parser.add_argument(
        '--no-trailing', action='store_false', dest='fix_trailing',
        default=True, help='''do not fix trailing spaces
        i.e. white spaces at the end of line (default: False)''')
    parser.add_argument(
        '--no-eof', action='store_false', dest='fix_eof',
        default=True, help='''do not fix missing EOL characters at the end
        of the file (default: False)''')
    parser.add_argument(
        '--no-mode', action='store_false', dest='fix_mode',
        default=True, help='''do not fix file mode bits i.e. permissions
        (default: False)''')
    parser.add_argument(
        '--clang-format', nargs='?', const=DEFAULT_CLANG_FORMAT,
        metavar='CLANG-FORMAT EXECUTABLE',
        help='''fix formatting using clang-format (default: disabled). The
        path to the "clang-format" executable can be optionally secified.
        Please remember to use the "--" separator before positional arguments.
        ''')

    parser = _set_common_perser_args(parser, backup=True)

    return parser


def get_update_copyright_parser(parser=None):
    """Build and return the command line parser for the "update-copyright"
    command."""

    if parser is None:
        parser = argparse.ArgumentParser(description=CopyrightTool.__doc__)
    elif hasattr(parser, 'add_parser'):
        # SubParsersAction
        parser = parser.add_parser(
            'update-copyright',
            description=CopyrightTool.__doc__,
            help=_summary_line(CopyrightTool.__doc__))

    parser.add_argument(
        '-t', '--template', dest='copyright_template_path',
        help='''copyright statement template file.
        The specification of a template is the only way to enable the
        function that adds a copyright statement in source file where it is
        missing.
        Please note that it is possible to specify only one template, and it
        shall contain valid code (or comments) for all files it is applied to.
        For this reason it is not always possible to add the copyright
        template to files written in different languages (e.g. C++ and Pyhton),
        otherwise the operation will produce invalid source files.
        All the occurrences of the marker "{year}" in the template will be
        replaced by the specified year.''')
    parser.add_argument(
        '--no-update', action='store_false', dest='update',
        default=True, help='''disable the update of the date in existing
        copyright lines (default: False)''')
    parser.add_argument(
        '-y', '--year', type=int,
        help='''specify the last year covered by the copyright
        (default: %(default)d)''' % dict(default=datetime.date.today().year))

    parser = _set_common_perser_args(parser, backup=True)

    return parser


def get_dumpcfg_parser(parser=None):
    """Build and return the command line parser for the "fix" command."""

    description = '''Dump to screen the default configuration
    (in .INI format).

    The dumped configuration can be used to write a custom configuration
    file and avoid to pass options via command line.

    '''

    if parser is None:
        parser = argparse.ArgumentParser(description=description)
    elif hasattr(parser, 'add_parser'):
        # SubParsersAction
        parser = parser.add_parser(
            'dumpcfg',
            description=description,
            help=_summary_line(description))

    parser.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=logging.DEBUG,
        help='enable debug output')

    return parser


def get_parser():
    """Instantiate the command line argument parser."""

    parser = argparse.ArgumentParser(
        description=__doc__, prog=PROG,
        epilog='Copyright (C) 2017-2019 Antonio Valentino')

    parser.add_argument(
        '--version', action='version', version='%(prog)s v' + __version__)

    subparsers = parser.add_subparsers(dest='command', title='sub-commands')

    get_check_parser(subparsers)
    get_fix_parser(subparsers)
    get_update_copyright_parser(subparsers)
    get_dumpcfg_parser(subparsers)

    if argcomplete:
        argcomplete.autocomplete(parser)

    return parser


def parse_args(args=None, namespace=None, parser=None):
    """Parse command line arguments."""

    if parser is None:
        parser = get_parser()

    # passing a napespace here doesn't work due to Python issue #29670
    # (https://bugs.python.org/issue29670)
    # args = parser.parse_args(args, namespace)
    args = parser.parse_args(args, namespace=None)

    if args.command is None:
        parser.error('command not specified')

    if namespace is not None:
        command = args.command
        name = 'get_{}_parser'.format(command.replace('-', '_'))
        get_parser_func = globals()[name]
        parser = get_parser_func()

        argv = sys.argv[1:]
        argv.remove(command)
        args = parser.parse_args(argv, namespace)
        args.command = command

    if getattr(args, 'loglevel', None) is None:
        args.loglevel = logging.WARNING

    return args


def main(argv=None):
    """Main CLI interface."""

    logging.basicConfig(format=LOGFMT, level=logging.INFO, stream=sys.stdout)
    logging.captureWarnings(True)

    args = parse_args(argv)
    logging.getLogger().setLevel(args.loglevel)
    ret = EX_OK

    try:
        scancfg = DEFAULT_CFG

        if getattr(args, 'config', None) is not None:
            cfg = ConfigParser()

            with open(args.config) as fd:
                cfg.read_file(fd)

            scancfg = cfg.get_scancfg()

            # re-parse
            kwargs = cfg.get_command_args(args.command)
            namespace = argparse.Namespace(**kwargs)
            args = parse_args(namespace=namespace)
            logging.getLogger().setLevel(args.loglevel)

        if getattr(args, 'path_patterns', None) is not None:
            path_patterns = args.path_patterns.split(',')

            scancfg = ScanConfig(
                path_patterns,
                scancfg.skip_path_patterns,
                scancfg.skip_data_patterns)

        if getattr(args, 'skip_path_patterns', None) is not None:
            if not args.skip_path_patterns:
                skip_path_patterns = []
            else:
                skip_path_patterns = args.skip_path_patterns.split(',')

            scancfg = ScanConfig(
                scancfg.path_patterns,
                skip_path_patterns,
                scancfg.skip_data_patterns)

        logging.debug(
            'PATH_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.path_patterns)))
        logging.debug(
            'SKIP_PATH_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.skip_path_patterns)))
        logging.debug(
            'SKIP_DATA_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.skip_data_patterns)))

        if getattr(args, 'clang_format', None):
            clang_format = args.clang_format
            if clang_format is True:
                clang_format = DEFAULT_CLANG_FORMAT

            completed_process = subprocess.run(
                [clang_format, '--version'], check=True,
                stdout=subprocess.PIPE)
            logging.debug(
                completed_process.stdout.decode(sys.getdefaultencoding()))

        if args.command == 'check':
            tool = CheckTool(
                check_tabs=args.check_tabs,
                check_eol=args.check_eol,
                check_trailing=args.check_trailing,
                check_encoding=args.check_encoding,
                check_eol_at_eof=args.check_eol_at_eof,
                check_relative_include=args.check_relative_include,
                check_copyright=args.check_copyright,
                check_mode=args.check_mode,
                clang_format=args.clang_format,
                maxlinelen=args.maxlinelen,
                failfast=args.failfast,
                scancfg=scancfg,
            )

            stats = collections.Counter()
            for path in args.paths:
                partial_stats = tool.scan(path)
                stats.update(partial_stats)

            if stats:
                msg = '\n'.join(
                    '{:7d}: {}'.format(v, k) for k, v in stats.items())
                logging.warning('check failed\n' + msg)
            else:
                logging.info('check completed successfully')

            return bool(stats)
        elif args.command == 'fix':
            tool = FixTool(
                tabsize=args.tabsize,
                fix_trailing=args.fix_trailing,
                fix_eof=args.fix_eof,
                fix_mode=args.fix_mode,
                clang_format=args.clang_format,
                eol=args.eol,
                backup_ext=args.backup,
                scancfg=scancfg,
            )
            for path in args.paths:
                tool.scan(path)
        elif args.command == 'update-copyright':
            tool = CopyrightTool(
                copyright_template_path=args.copyright_template_path,
                update=args.update,
                year=args.year,
                backup_ext=args.backup,
                scancfg=scancfg,
            )
            for path in args.paths:
                tool.scan(path)
        elif args.command == 'dumpcfg':
            cfg = ConfigParser()
            cfg.setup_default_config()
            out = io.StringIO()
            cfg.write(out)
            print(out.getvalue())
        else:
            raise ValueError('invalid command: {!r}'.format(args.command))

    except Exception as exc:
        logging.critical(
            'unexpected exception caught: {!r} {}'.format(
                type(exc).__name__, exc))
        logging.debug('stacktrace:', exc_info=True)
        ret = EX_FAILURE

    return ret


if __name__ == '__main__':
    sys.exit(main())
