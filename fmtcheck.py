#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Basic checks on source code

Available checks include: presence of tabs, EOL consistency,
presence of trailing spaces, conformity to the ASCII encoding and
line length.

Some basic tool for fixing formatting problems is also provided.

"""

# TODO: make skip patterns and file extensions configurable via command line

import io
import os
import re
import sys
import copy
import enum
import shutil
import fnmatch
import logging
import argparse
import collections
import configparser


__version__ = '1.0.1.dev0'


PROG = 'fmtcheck'


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


class SrcTree(object):
    """Tree object that provides smart iteration features."""

    def __init__(self, path='.', mode='r',
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

    def _scan(self, path):
        if os.path.isfile(path):
            return [path]
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
                yield from subtree
                # for item in suntree:
                #     yield item
            elif self._path_re.match(entry.name):
                try:
                    with open(entry.path, self.mode.value) as fd:
                        data = fd.read()
                except UnicodeDecodeError as ex:
                    logging.warning(
                        'unable to read {!r}: {}'.format(entry.path, ex))
                else:
                    if self._skip_data_re.search(data):
                        logging.debug('skipping {!r}'.format(entry.path))
                    else:
                        yield entry.path, data

            else:
                logging.debug('skipping {!r}'.format(entry.path))


class CheckTool(object):
    """Tool for source code checking."""

    def __init__(self, failfast=False, scancfg=DEFAULT_CFG, **kwargs):
        self.failfast = failfast
        self.scancfg = scancfg

        self.check_tabs = bool(kwargs.pop('check_tabs', True))
        self.check_eol = bool(kwargs.pop('check_eol', True))
        self.check_trailing = bool(kwargs.pop('check_trailing', True))
        self.check_encoding = bool(kwargs.pop('check_encoding', True))

        self.maxlinelen = int(kwargs.pop('maxlinelen', 0))
        self.eol = Eol(kwargs.pop('eol', Eol.NATIVE))
        self.encoding = kwargs.pop('encoding', 'ascii')

        if kwargs:
            key = next(iter(kwargs.keys()))
            raise TypeError(
                '__init__() got an unexpected keyword argument '
                '{!r}'.format(key))

        self._checklist = ()

    def _encoding_checker(self, data):
        for lineno, line in enumerate(data.splitlines(), 1):
            try:
                line.decode(self.encoding)
            except UnicodeDecodeError as ex:
                logging.info(
                    'unable to decode line n. {}: {!r}'.format(lineno, line))
                return True

    def _linelen_checker(self, data):
        if self.eol is None:
            line_iterator = data.splitlines()
        else:
            line_iterator = data.split(self.eol.value)

        for line in line_iterator:
            if len(line) > self.maxlinelen:
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

        if self.maxlinelen:
            checklist['line tool long'] = self._linelen_checker

        return checklist

    def _check_file_core(self, filename, data):
        stats = collections.Counter()

        for key, checkfunc in self._checklist.items():
            if checkfunc(data):
                stats[key] += 1
                logging.info('{}: {}'.format(filename, key))
                if self.failfast:
                    return stats

        return stats

    def check_file(self, filename):
        """Perform checks on the input data."""

        # ensure to be in sync with the current status of flags
        self._checklist = self._get_checklist()

        with open(filename, 'rb') as fd:
            data = fd.read()

        return self._check_file_core(filename, data)

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

        for filename, data in srctree:
            local_stats = self._check_file_core(filename, data)
            stats.update(local_stats)

            if self.failfast and stats:
                break

        return stats


class FixTool(object):
    """Tool for source code fixing."""

    TRIM_RE = re.compile('[ \t]+(?=\n)|[ \t]+$')

    def __init__(self, tabsize=4, fix_trailing=True, eol=Eol.NATIVE,
                 backup_ext=None, scancfg=DEFAULT_CFG):
        self.tabsize = int(tabsize)
        self.eol = Eol(eol)
        self.fix_trailing = fix_trailing

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

    def _fix_file_core(self, filename, data):
        fd = io.StringIO(data)
        with open(filename, 'w', newline=self.eol.value) as out:
            for line in fd:
                for line_fixer in self._line_fixers:
                    line = line_fixer(line)
                out.write(line)

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

        self._fix_file_core(outfile, data)

    def scan(self, path='.'):
        """Apply fixes to all source files in path."""

        # ensure to be in sync with the current status of flags
        self._line_fixers = self._get_line_fixers()

        srctree = SrcTree(
            path, mode=Mode.TEXT,
            path_patterns=self.scancfg.path_patterns,
            skip_path_patterns=self.scancfg.skip_path_patterns,
            skip_data_patterns=self.scancfg.skip_data_patterns)

        for filename, data in srctree:
            if self.backup_ext:
                backupfile = filename + self.backup_ext
                shutil.move(filename, backupfile)

            self._fix_file_core(filename, data)


class ConfigParser(configparser.ConfigParser):
    def scancfg_to_dict(self, scancfg):
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

    def checktool_to_dict(self, tool):
        d = collections.OrderedDict()

        d['failfast'] = bool(tool.failfast)
        d['check_tabs'] = bool(tool.check_tabs)
        d['check_eol'] = bool(tool.check_eol)
        d['check_trailing'] = bool(tool.check_trailing)
        d['check_encoding'] = bool(tool.check_encoding)
        d['maxlinelen'] = int(tool.maxlinelen)
        d['eol'] = tool.eol.name
        d['encoding'] = tool.encoding

        return d

    def fixtool_to_dict(self, tool):
        d = collections.OrderedDict()

        d['tabsize'] = int(tool.tabsize)
        d['eol'] = Eol(tool.eol).name
        d['fix_trailing'] = bool(tool.fix_trailing)

        if tool.backup_ext:
            d['backup_ext'] = tool.backup_ext

        return d

    def setup_default_config(self):
        cfg = self.scancfg_to_dict(DEFAULT_CFG)
        cfg['check'] = self.checktool_to_dict(CheckTool())
        cfg['fix'] = self.fixtool_to_dict(FixTool())
        self.read_dict(cfg)

        self.add_section('logging')
        self.set('logging', 'loglevel', 'WARNING')

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
                    'check_encoding'):
            if key in section:
                d[key] = self.getboolean(sectname, key)

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

        if 'backup_ext' in section:
            d['backup_ext'] = self.getboolean(sectname, 'backup_ext')

        loglevel = self._get_loglevel()
        if loglevel is not None:
            d['loglevel'] = loglevel

        return d

    def get_command_args(self, command):
        if command == 'check':
            return self.get_checkargs()
        elif command == 'fix':
            return self.get_fixargs()
        else:
            raise ValueError('unexpected command: {!r}'.format(command))


def get_check_parser(parser=None):
    """Build and return the command line parser for the "check" command."""

    description = '''Check the conformity of source code to basic
    standards: end of line (EOL) consistency, trailing spaces,
    presence of tabs, conformity to the ASCII encoding, line length.
    By default the program prints how many files fail the check,
    for each of the selected checks.'''

    if parser is None:
        parser = argparse.ArgumentParser(description=description)
    elif isinstance(parser, argparse.Action):
        parser = parser.add_parser('check', help=description)

    parser.add_argument(
        '-q', '--quiet',
        dest='loglevel', action='store_const', const=logging.ERROR,
        help='''suppress standard output, only errors are printed to screen
        (by default only global statistics are printed)''')
    parser.add_argument(
        '-v', '--verbose',
        dest='loglevel', action='store_const', const=logging.INFO,
        help='''enable verbose output: for each check failed print an
        informative line (by default only global statistics are printed)''')
    parser.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=logging.DEBUG,
        help='''enable debug output (by default only global statistics
        are printed)''')

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
        '-l', '--line-length', dest='maxlinelen', type=int, default=0,
        help='''set the maximum line length, if not set (default) disable
        checks on line length''')

    parser.add_argument(
        '-f', '--failfast', action='store_true', default=False,
        help='exit immediately as soon as a check fails')

    parser.add_argument(
        '-c', '--config', help='path to the configuration file')

    parser.add_argument(
        'paths', default='.', nargs='*',
        help='root of the source tree to scan (default: %(default)r)')

    return parser


def get_fix_parser(parser=None):
    """Build and return the command line parser for the "fix" command."""

    description = '''Fix basic formatting issues related to spacing:
    end of line (EOL) consistency, trailing spaces, presence of tabs.'''

    if parser is None:
        parser = argparse.ArgumentParser(description=description)
    elif isinstance(parser, argparse.Action):
        parser = parser.add_parser('fix', help=description)

    parser.add_argument(
        '-v', '--verbose',
        dest='loglevel', action='store_const', const=logging.INFO,
        help='''enable verbose output: for each check failed print an
        informative line (by default only global statistics are printed)''')
    parser.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=logging.DEBUG,
        help='''enable debug output (by default only global statistics
        are printed)''')

    parser.add_argument(
        '--eol', default=Eol.NATIVE, choices=list(Eol.__members__.keys()),
        help='output end of line (default: native)')
    parser.add_argument(
        '--tabsize', default=4, type=int, help='''specify the number of
        blanks to be used to replace each tab (default: %(default)s).
        To disable tab substitution set tabsize to 0''')
    parser.add_argument(
        '--no-trailing', action='store_false', dest='fix_trailing',
        default=True, help='''disable checks on trailing spaces
        i.e. white spaces at the end of line (default: False)''')

    parser.add_argument(
        '-b', '--backup', action='store_const', default=False, const='.bak',
        help='''backup original file contents on a file with the same
        name + "%(const)s". Default no backup is performed.''')

    parser.add_argument(
        '-c', '--config', help='path to the configuration file')

    parser.add_argument(
        'paths', default='.', nargs='*',
        help='root of the source tree to scan (default: %(default)r)')

    return parser


def get_dumpcfg_parser(parser=None):
    """Build and return the command line parser for the "fix" command."""

    description = '''Dump the default configuration to stdout.'''

    if parser is None:
        parser = argparse.ArgumentParser(description=description)
    elif isinstance(parser, argparse.Action):
        parser = parser.add_parser('dumpcfg', help=description)

    parser.add_argument(
        '-d', '--debug',
        dest='loglevel', action='store_const', const=logging.DEBUG,
        help='''enable debug output (by default only global statistics
        are printed)''')

    return parser


def get_parser():
    """Build and return the command line parser."""

    parser = argparse.ArgumentParser(
        prog=PROG, description='''%(prog)s performs basic formatting
        checks/fixes on source code.''')

    parser.add_argument(
        '--version', action='version',
        version='%(prog)s {}'.format(__version__))

    subparsers = parser.add_subparsers(dest='command', description='')

    get_check_parser(subparsers)
    get_fix_parser(subparsers)
    get_dumpcfg_parser(subparsers)

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
        name = 'get_{}_parser'.format(command)
        get_parser_func = globals()[name]
        parser = get_parser_func()

        argv = sys.argv[1:]
        argv.remove(command)
        args = parser.parse_args(argv, namespace)
        args.command = command

    if getattr(args, 'loglevel', None) is None:
        args.loglevel = logging.WARNING

    return args


def main():
    """Main program."""

    logging.basicConfig(
        format='%(levelname)s: %(message)s', stream=sys.stdout)

    args = parse_args()
    logging.getLogger().setLevel(args.loglevel)

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

        logging.debug(
            'PATH_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.path_patterns)))
        logging.debug(
            'SKIP_PATH_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.skip_path_patterns)))
        logging.debug(
            'SKIP_DATA_PATTERNS: {}'.format(
                ', '.join(repr(p) for p in scancfg.skip_data_patterns)))

        if args.command == 'check':
            tool = CheckTool(
                check_tabs=args.check_tabs,
                check_eol=args.check_eol,
                check_trailing=args.check_trailing,
                check_encoding=args.check_encoding,
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
                eol=args.eol,
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
    except Exception as ex:
        logging.critical(str(ex))
        logging.debug('', exc_info=True)


if __name__ == '__main__':
    sys.exit(main())
