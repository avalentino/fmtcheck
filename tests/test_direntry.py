# -*- coding: utf-8 -*-

import os
import unittest

import fmtcheck


class SimpleDirEntryTestCase(unittest.TestCase):
    DIRENTRY_TYPE = None

    def setUp(self):
        self.direntry = fmtcheck.SimpleDirEntry(__file__)

    def test_name(self):
        assert self.direntry.name == os.path.basename(__file__)

    def test_path(self):
        assert self.direntry.path == __file__

    def test_inode(self):
        assert self.direntry.inode() == os.stat(__file__).st_ino

    def test_is_dir(self):
        assert self.direntry.is_dir() is False

    def test_is_file(self):
        assert self.direntry.is_file() is True

    def test_is_symlink(self):
        assert self.direntry.is_symlink() is False

    def test_stat(self):
        assert self.direntry.stat() == os.stat(__file__)

    @unittest.skipIf(not hasattr(os, 'fspath'), 'os.fspath not available')
    def test_fspath(self):
        assert os.fspath(self.direntry) == __file__
