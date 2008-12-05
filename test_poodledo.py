#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import os

import unittest
import urllib2
import time
from datetime import datetime,timedelta

from poodledo import ApiClient, ToodledoError

class MockOpener(object):
    def __init__(self):
        self.url_map = {}

    def add_file(self, url, fname):
        self.url_map[url] = fname

    def open(self,url):
        if url in self.url_map:
            return open(self.url_map[url],'r')
        else:
            # print url
            return open(self.url_map['default'],'r')

class MyTest(unittest.TestCase):

    def setUp(self):
        self.opener = MockOpener()
        self.opener.add_file('default', 'testdata/error.xml')
        self.opener.add_file(
                'http://www.toodledo.com/api.php?email=test@test.de;method=getUserid;pass=mypassword',
                'testdata/getUserid_good.xml')
        self.opener.add_file(
                'http://www.toodledo.com/api.php?method=getToken;userid=sampleuserid156',
                'testdata/getToken_good.xml')
        self.opener.add_file(
                'http://www.toodledo.com/api.php?key=83210ee13e69133d9b241e2f24cf5850;method=getServerInfo',
                'testdata/getServerInfo.xml')

    def _createApiClient(self,authenticate=False):
        api = ApiClient()
        api.set_urlopener(self.opener)
        if authenticate:
            api.authenticate('test@test.de', 'mypassword')
        return api

    def test_getUserid(self):
        api = self._createApiClient()

        api.getUserid('test@test.de','mypassword')
        self.assertRaises(ToodledoError, api.getUserid, 'test@test.de','wrong_password')

    def test_getToken(self):
        api = self._createApiClient()

        token = api.getToken('sampleuserid156')
        self.assertEquals(token, 'td493900752ca4d')

    def test_authenticate(self):
        api = self._createApiClient()

        api.authenticate('test@test.de', 'mypassword')
        self.assertTrue( api.isAuthenticated )

    def test_getServerInfo(self):
        api = self._createApiClient(True)
        info = api.getServerInfo()
        self.assertEquals(info.unixtime, 1228476730)
        # self.assertEquals(info.date, 'Fri, 05 Dec 2008 05:32:10 -0600')
        self.assertEquals(info.date, datetime(2008, 12, 5, 11, 32, 10) - timedelta(seconds=time.timezone))
        self.assertEquals(info.tokenexpires, 238.53)


def suite():
    loader = unittest.TestLoader()
    testsuite = loader.loadTestsFromTestCase(MyTest)
    return testsuite


if __name__ == '__main__':
    from unittestguiWx import GUITestRunner
    testsuite = suite()
    runner = unittest.TextTestRunner(sys.stdout, verbosity=2)
    result = runner.run(testsuite)
