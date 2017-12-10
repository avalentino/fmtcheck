fmtcheck
========

:copyright: 2017 Antonio Valentino

Check the conformity of source code to basic standards.

Available checks include:

* the presence of tabs, 
* EOL consistency,
* the presence of trailing spaces, 
* conformity to the ASCII encoding. and
* code lines not longer than the maximum specified value.

Some basic tool for fixing formatting problems is also provided.

The `fmtchek` tool can be used interactively form the command line,
or it can be integrated in CI systems to perform basic check of the source
tree at each commit.

It is possible to specify one or more files and directories to scan,
so checking an entire entire source tree vary easy.


Usage
-----

The `fmtchek` program provides 3 different sub-commands:

:check:
    to check the conformity to standards
:fix:
    to fix some of non conformities to standards
:dumpcfg:
    print to screen the default configuration (in .INI format).
    The dumped configuration can be used to write a custom configuration
    file and avoid to pass options via command line.

Please note that using a configuration file is the only way to specify some
advanced options related to the the specification of file patterns to scan
or to skip.

Getting help
~~~~~~~~~~~~

The `-h` option (or `--help`) of the `fmtcheck` program can be
used to obtain a simple help message::

    $ fmtchek -h
    
    usage: fmtcheck [-h] [--version] {check,fix,dumpcfg} ...

    fmtcheck performs basic formatting checks/fixes on source code.

    optional arguments:
      -h, --help           show this help message and exit
      --version            show program's version number and exit

    subcommands:

      {check,fix,dumpcfg}
        check              Check the conformity of source code to basic
                           standards:
                           end of line (EOL) consistency, trailing spaces,
                           presence of tabs, conformity to the ASCII encoding,
                           line length. By default the program prints how many
                           files fail the check, for each of the selected
                           checks.
        fix                Fix basic formatting issues related to spacing:
                           end of line (EOL) consistency, trailing spaces,
                           presence of tabs.
        dumpcfg            Dump the default configuration to stdout.


The help option can be also used with all sub-commands.


check sub-command
~~~~~~~~~~~~~~~~~

The `check` sub-command has the following options::

    $ fmtcheck check -h

    usage: fmtcheck check [-h] [-q] [-v] [-d] [--no-tabs] [--no-eol]
                          [--no-trailing] [--no-encoding] [-l MAXLINELEN] [-f]
                          [-c CONFIG]
                          [PATH [PATH ...]]

    positional arguments:
      PATH                  root of the source tree to scan (default: '.')

    optional arguments:
      -h, --help            show this help message and exit
      -q, --quiet           suppress standard output, only errors are printed
                            to screen (by default only global statistics are
                            printed)
      -v, --verbose         enable verbose output: for each check failed print
                            an informative line (by default only global
                            statistics are printed)
      -d, --debug           enable debug output (by default only global
                            statistics are printed)
      --no-tabs             disable checks on the presence of tabs in the
                            source code (default: False)
      --no-eol              disable checks on the EOL consistency (default:
                            False). N.B. the system EOL is used as reference
      --no-trailing         disable checks on trailing spaces i.e. white spaces
                            at the end of line (default: False)
      --no-encoding         disable checks on text encoding: source code that
                            is not pure ASCII is considered not valid
                            (default: False)
      -l MAXLINELEN, --line-length MAXLINELEN
                            set the maximum line length, if not set (default)
                            disable checks on line length
      -f, --failfast        exit immediately as soon as a check fails
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


fix sub-command
~~~~~~~~~~~~~~~

The `fix` sub-command has the following options::

    $ fmtcheck fix -h
    
    usage: fmtcheck fix [-h] [-v] [-d] [--eol {NATIVE,UNIX,WIN}]
                        [--tabsize TABSIZE] [--no-trailing] [-b] [-c CONFIG]
                        [PATH [PATH ...]]

    positional arguments:
      PATH                  root of the source tree to scan (default: '.')

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         enable verbose output
      -d, --debug           enable debug output
      --eol {NATIVE,UNIX,WIN}
                            output end of line (default: native)
      --tabsize TABSIZE     specify the number of blanks to be used to replace
                            each tab (default: 4). To disable tab substitution
                            set tabsize to 0
      --no-trailing         disable checks on trailing spaces i.e. white spaces
                            at the end of line (default: False)
      -b, --backup          backup original file contents on a file with the
                            same name + ".bak". Default no backup is performed.
      -c CONFIG, --config CONFIG
                            path to the configuration file


dumpcfg sub-command
~~~~~~~~~~~~~~~~~~~

The `dumpcfg` sub-command has the following options::

    $ fmtcheck dumpcfg -h
    usage: fmtcheck dumpcfg [-h] [-d]

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

BSD 3-Clause License (see LICENSE file).
