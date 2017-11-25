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
        '^__version__\s*=\s*(?P<quote>[\'"])(?P<version>[^\'"]+)(?P=quote)',
        data,
        re.MULTILINE)
    return mobj.group('version')


setup(
    name='fmtcheck',
    version=get_version(),
    description='Check the conformity of source code to basic standards.',
    long_description='''Check the conformity of source code to basic standards.
    Available checks include: presence of tabs, EOL consistency,
    presence of trailing speces, coformity to the ASCII encoding and
    line length.
    Some basic tool for fixing formatting problems is also provided.''',
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
    ],
    keywords='utility formatting checkers',
    py_modules=["fmtcheck"],
    entry_points={
        'console_scripts': [
            'fmtcheck=fmtcheck:main',
        ],
    },
)
