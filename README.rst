fmtcheck
========

`fmtcheck` is a tool that helps to ensure the conformity of source code
to basic standards.

The tool provides the following sub-commands:

:check:
    to check the conformity of all files in a source tree to basic
    formatting standards
:fix:
    to fix common formatting mistakes
:update-copyright:
    to set and update the copyright statement in source files
:dumcfg:
    to dump to screen the default configuration (in .INI format).
    The dumped configuration can be used to write a custom configuration
    file and avoid to pass options via command line.

Please note that using a configuration file is the only way to specify some
advanced options related to the the specification of file patterns to scan
or to skip.

The `fmtchek` tool can be used interactively form the command line,
or it can be integrated in CI systems to perform basic check/fixes of the
source tree at each commit.

It is possible to specify one or more files and directories to scan,
so checking an entire entire source tree vary easy.


Usage
-----

Getting help
~~~~~~~~~~~~

The `-h` option (or `--help`) of the `fmtcheck` program can be
used to obtain a simple help message::

    $ fmtchek -h

    usage: fmtcheck [-h] [--version] {check,fix,update-copyright,dumpcfg} ...

    Ensure the source code conformity to basic formatting standards.
    The tool provides sub-commands to "check" the conformity of all files
    in a source tree to basic formatting standards, to "fix" common
    formatting mistakes, and also to set and update the copyright statement
    ("update-copyright" sub-command) in source files.

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit

    subcommands:

      {check,fix,update-copyright,dumpcfg}
        check               Check the conformity of source code to basic
                            standards.
        fix                 Fix basic formatting issues.
        update-copyright    Update or add the copyright statement is source
                            files.
        dumpcfg             Dump to screen the default configuration (in .INI
                            format).


The help option can be also used with all sub-commands.


`check` sub-command
~~~~~~~~~~~~~~~~~~~

The `check` sub-command allows to perform the following checks on the
source code:

* the presence of tabs,
* end of line (EOL) consistency,
* the presence of trailing spaces at the end of a source code line,
* conformity to the ASCII encoding,
* code lines not longer than the maximum specified value,
* the presence of an End Of Line (EOL) character before the End Of File (EOF),
* the presence of a copyright statement is source files,
* the file permissions (source files shall not be executables).

The `check` sub-command has the following options::

    $ fmtcheck check -h

    usage: fmtcheck check [-h] [--no-tabs] [--no-eol] [--no-trailing]
                          [--no-encoding] [--no-eof] [--no-relative-include]
                          [--no-copyright] [--no-mode]
                          [-l MAXLINELEN] [-f] [-q] [-v] [-d]
                          [--patterns PATH_PATTERNS]
                          [--skip SKIP_PATH_PATTERNS] [--no-skip] [-c CONFIG]
                          PATH [PATH ...]

    Check the conformity of source code to basic standards. Available checks
    include: end of line (EOL) consistency, presence of trailing spaces at
    the end of a source code line, presence of tabs, conformity to the ASCII
    encoding, maximum line length, presence of an End Of Line (EOL) character
    before the End Of File (EOF), presence of a copyright statement is source
    files, file permissions (source files shall not be executables),
    formatting according clang-format standards.
    By default the tool prints how many files fail the check, for each of
    the selected checks.

    positional arguments:
      PATH                  root of the source tree to scan (default: None)

    optional arguments:
      -h, --help            show this help message and exit
      --no-tabs             disable checks on the presence of tabs in the
                            source code (default: False)
      --no-eol              disable checks on the EOL consistency (default:
                            False). N.B. the system EOL is used as reference
      --no-trailing         disable checks on trailing spaces i.e. white
                            spaces at the end of line (default: False)
      --no-encoding         disable checks on text encoding: source code that
                            is not pure ASCII is considered not valid
                            (default: False)
      --no-eof              disable checks on the presence of an EOL character
                            at the end of the file (default: False)
      --no-relative-include
                            disable checks on the presence of C/C++ "#include"
                            statements with relative path (default: False)
      --no-copyright        disable checks on the presence of the copyright
                            line is source files (default: False)
      --no-mode             disable checks on file mode bits i.e. permissions
                            (default: False)
      -l MAXLINELEN, --line-length MAXLINELEN
                            set the maximum line length, if not set (default)
                            disable checks on line length
      -f, --failfast        exit immediately as soon as a check fails

    logging:
      -q, --quiet           suppress standard output, only errors are printed
                            to screen
      -v, --verbose         enable verbose output
      -d, --debug           enable debug output

    source tree scanning:
      --patterns PATH_PATTERNS
                            comma separated list of glob pattern to scan.
                            Default: *.[ch],*.[ch]pp,*.[ch]xx,*.txt,*.cmake,
                            *.sh,*.bash,*.bat,*.xsd,*.xml
      --skip SKIP_PATH_PATTERNS
                            comma separated list of glob pattern to skip.
                            Default: .*
      --no-skip             skip no file during the scanning of the directory
                            tree

    config:
      -c CONFIG, --config CONFIG
                            path to the configuration file


Example::

    $ fmtcheck check -v src
    
    INFO: src/foo.hpp: tabs
    INFO: src/foo.hpp: trailing spaces
    INFO: src/bar.hpp: tabs
    INFO: src/bar.hpp: trailing spaces
    INFO: src/baz.h: tabs
    WARNING: check failed
          3: tabs
          2: trailing spaces


`fix` sub-command
~~~~~~~~~~~~~~~~~

The `fix` sub-command allows to perform the following fixes on the
source code:

* end of line (EOL) consistency,
* trailing spaces removal,
* substitution of tabs with spaces,
* ensuring that an End Of Line (EOL) character is always present before
  the End Of File (EOF), and
* file permissions (source files shall not be executables).

The `fix` sub-command has the following options::

    $ fmtcheck fix -h
    
    usage: fmtcheck fix [-h] [--eol {NATIVE,UNIX,WIN}] [--tabsize TABSIZE]
                        [--no-trailing] [--no-eof] [--no-mode]
                        [-b] [-q] [-v] [-d]
                        [--patterns PATH_PATTERNS] [--skip SKIP_PATH_PATTERNS]
                        [--no-skip] [-c CONFIG]
                        PATH [PATH ...]

    Fix basic formatting issues. Available fixes include: end of line (EOL)
    consistency, trailing spaces removal, substitution of tabs with spaces,
    ensuring that an End Of Line (EOL) character is always present before the
    End Of File (EOF), file permissions (source files shall not be
    executables).

    positional arguments:
      PATH                  root of the source tree to scan (default: None)

    optional arguments:
      -h, --help            show this help message and exit
      --eol {NATIVE,UNIX,WIN}
                            output end of line (default: native)
      --tabsize TABSIZE     specify the number of blanks to be used to replace
                            each tab (default: 4). To disable tab substitution
                            set tabsize to 0
      --no-trailing         do not fix trailing spaces i.e. white spaces at the
                            end of line (default: False)
      --no-eof              do not fix missing EOL characters at the end of the
                            file (default: False)
      --no-mode             do not fix file mode bits i.e. permissions (default:
                            False)

    backup:
      -b, --backup          backup original file contents on a file with the
                            same name + ".bak". Default no backup is performed.

    logging:
      -q, --quiet           suppress standard output, only errors are printed
                            to screen
      -v, --verbose         enable verbose output
      -d, --debug           enable debug output

    source tree scanning:
      --patterns PATH_PATTERNS
                            comma separated list of glob pattern to scan.
                            Default: *.[ch],*.[ch]pp,*.[ch]xx,*.txt,*.cmake,
                            *.sh,*.bash,*.bat,*.xsd,*.xml
      --skip SKIP_PATH_PATTERNS
                            comma separated list of glob pattern to skip.
                            Default: .*
      --no-skip             skip no file during the scanning of the directory
                            tree

    config:
      -c CONFIG, --config CONFIG
                            path to the configuration file


`update-copyright` sub-command
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `update-copyright` sub-command has the following options::

    $ fmtcheck update-copyright -h

    usage: fmtcheck update-copyright [-h] [-t COPYRIGHT_TEMPLATE_PATH]
                                     [--no-update] [-y YEAR] [-b] [-q] [-v] [-d]
                                     [--patterns PATH_PATTERNS]
                                     [--skip SKIP_PATH_PATTERNS] [--no-skip]
                                     [-c CONFIG]
                                     PATH [PATH ...]

    Update or add the copyright statement is source files. The copyright
    statement in source files is updated to the current year (if not
    differently specified by the user).
    If a source file does not have a copyright statement it can be
    added by providing a suiteble template.

    positional arguments:
      PATH                  root of the source tree to scan (default: None)

    optional arguments:
      -h, --help            show this help message and exit
      -t COPYRIGHT_TEMPLATE_PATH, --template COPYRIGHT_TEMPLATE_PATH
                            copyright statement template file. The
                            specification of a template is the only way to
                            enable the function that adds a copyright
                            statement in source file where it is missing.
                            Please note that it is possible to specify only
                            one template, and it shall contain valid
                            code (or comments) for all files it is applied to.
                            For this reason it is not always possible to add
                            the copyright template to files written in
                            different languages (e.g. C++ and Pyhton),
                            otherwise the operation will produce invalid
                            source files. All the occurrences of the marker
                            "{year}" in the template will be replaced by the
                            specified year.
      --no-update           disable the update of the date in existing
                            copyright lines (default: False)
      -y YEAR, --year YEAR  specify the last year covered by the copyright
                            (default: 2018)

    backup:
      -b, --backup          backup original file contents on a file with the
                            same name + ".bak". Default no backup is performed.

    logging:
      -q, --quiet           suppress standard output, only errors are printed
                            to screen
      -v, --verbose         enable verbose output
      -d, --debug           enable debug output

    source tree scanning:
      --patterns PATH_PATTERNS
                            comma separated list of glob pattern to scan.
                            Default: *.[ch],*.[ch]pp,*.[ch]xx,*.txt,*.cmake,
                            *.sh,*.bash,*.bat,*.xsd,*.xml
      --skip SKIP_PATH_PATTERNS
                            comma separated list of glob pattern to skip.
                            Default: .*
      --no-skip             skip no file during the scanning of the directory
                            tree

    config:
      -c CONFIG, --config CONFIG
                            path to the configuration file


`dumpcfg` sub-command
~~~~~~~~~~~~~~~~~~~~~

The `dumpcfg` sub-command has the following options::

    $ fmtcheck dumpcfg -h
    
    usage: fmtcheck dumpcfg [-h] [-d]

    Dump to screen the default configuration (in .INI format). The dumped
    configuration can be used to write a custom configuration file and avoid
    to pass options via command line.

    optional arguments:
      -h, --help   show this help message and exit
      -d, --debug  enable debug output


Example::

    $ fmtcheck dumpcfg
    
    [path_patterns]
    pattern_01 = *.[ch]
    pattern_02 = *.[ch]pp
    pattern_03 = *.[ch]xx
    pattern_04 = *.txt
    pattern_05 = *.cmake
    pattern_06 = *.sh
    pattern_07 = *.bash
    pattern_08 = *.bat
    pattern_09 = *.xsd
    pattern_10 = *.xml

    [skip_path_patterns]
    pattern_01 = .*

    [check]
    failfast = False
    check_tabs = True
    check_eol = True
    check_trailing = True
    check_encoding = True
    maxlinelen = 0
    eol = NATIVE
    encoding = ascii

    [fix]
    tabsize = 4
    eol = NATIVE
    fix_trailing = True

    [logging]
    loglevel = WARNING


License
-------

:copyright: 2017 Antonio Valentino

BSD 3-Clause License (see LICENSE file).
