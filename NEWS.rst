Release History
===============

1.4.0 (in development)
----------------------

* New check/fix for file permissions (source files shall not be executable).
* New option for checking/fixing file formatting using the
  :program:`clang-format` tool (if available).
  See also https://clang.llvm.org/docs/ClangFormat.html.
* Improved docstrings and descriptions.
* Update copyright statement date.
* Fix linter warnings.
* Fixed a bug in the :meth:`CopyrightTool.update_copyright` method
  that caused infinite recursive calls.
* The :class:`SrcTree` iterator now returns directory entries instead
  of file names.


1.3.0 (16/12/2017)
------------------

* Now it is possible to specify scanning parameters form the command line
  (new options added).
* New option for checking C/C++ relative includes.
* General update of doc-strings and online command help.
* Improved management of the "backup" option.
* Factorized setup of common command line options.
  Added option groups for better readability of the help messages.
* Support for ReStructuredText copyright format in `update-copyright`.
* Log more detailed information about long lines.
* Include the `NEWS.rst` file in the distribution.
* Bug fixes:

  - actually update copyright dates
  - fix line length check (split lines with the correct separator)
  - improved debug logging


1.2.0 (07/12/2017)
------------------

* New checks for:

  - the presence on an End Of Line (EOL) character before the
    End Of File (EOF)
  - the presence of a copyright line in the file

* New option for fixing missing the EOL at EOF.
* New tool for:

  - updating the copyright date in source files
  - add a copyright statement (from a template) in source files where
    it is missing

* Bug fix: honour the log level set from the configuration file.


1.1.0 (26/11/2017)
------------------

* Workaround for an issue related to sub-parsers management.
  See Python issue #29670 (https://bugs.python.org/issue29670).
* Fixed some typos in help messages.
* The README.rst file has been improved.
* The specification of the "path" argument is now mandatory for
  the "check" and "fix" sub-commands.


1.0.0 (26/11/2017)
------------------

* Initial release.

