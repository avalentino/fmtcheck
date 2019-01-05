#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re

from setuptools import setup


def get_version():
    filename = os.path.join(os.path.dirname(__file__), 'fmtcheck.py')
    with open(filename) as fd:
        data = fd.read()
    mobj = re.search(
        r'^__version__\s*=\s*(?P<quote>[\'"])(?P<version>[^\'"]+)(?P=quote)',
        data,
        re.MULTILINE)
    return mobj.group('version')


setup(
    name='fmtcheck',
    version=get_version(),
    description='fmtcheck ensures the conformity of code to basic standards.',
    long_description='''fmtcheck ensures the conformity of source code to
    basic formatting standards.
    The tool provides sub-commands to "check" the conformity of all files in a
    source tree to basic formatting standards, to "fix" common formatting
    mistakes, and also to set and update the copyright statement
    ("update-copyright" sub-command) in source files.''',
    url='https://github.com/avalentino/fmtcheck',
    author='Antonio Valentino',
    author_email='antonio.valentino@tiscali.it',
    license='BSD',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Quality Assurance',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='utility formatting checkers',
    py_modules=["fmtcheck"],
    entry_points={
        'console_scripts': [
            'fmtcheck=fmtcheck:main',
        ],
    },
)
