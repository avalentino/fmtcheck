Release History
===============

1.3.0 (in development)
----------------------

* Bug fix: actually update copyright dates
* Improved debug logging


1.2.0 (07/12/2017)
------------------

* New checks for:

  - the presence on an End Of Line (EOL) character before the
    End Of File (EOF)
  - the presence of a copyright line in the file

* New option for fixing missing the EOL at EOF
* New tool for:

  - updating the copyright date in source files
  - add a copyright statement (from a template) in source files where
    it is missing

* Bug fix: honour the log level set from the configuration file


1.1.0 (26/11/2017)
------------------

* Workaround for an issue related to sub-parsers management.
  See Python issue #29670 (https://bugs.python.org/issue29670)
* Fixed some typos in help messages
* The README.rst file has been improved
* The specification of the "path" argument is now mandatory for
  the "check" and "fix" sub-commands


1.0.0 (26/11/2017)
------------------

* Initial release

