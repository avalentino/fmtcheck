fmtcheck
========

Check the conformity of source code to basic standards

:copiright: 2017 Antonio Valentino


Usage
-----

::

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


License
-------

BSD 3-Clause License (see LICENSE file).
