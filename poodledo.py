#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import urllib
import urllib2

import pickle
import time
from datetime import datetime, timedelta
import elementtree.ElementTree as ET
from md5 import md5

# import logging
# logging.basicConfig()
# LOG = logging.getLogger(__name__)
# LOG.setLevel(logging.DEBUG)

class ToodledoError(Exception):

    def __init__(self, error_msg):
        self.msg = error_msg

    def __str__(self):
        return "Toodledo server returned error: %s" % self.msg

class Token(object):
    def __init__(self, email, userid, token, expires = None):
        self.email = email
        self.userid = userid
        self.token = token
        if not(expires):
            self.tokenexpires = (datetime.datetime.now() + datetime.timedelta(hours=3, minutes=30))
        else:
            self.tokenexpires = expires

class TokenCache(object):
        _TOKEN_FILE = '~/.toodledo_tokencache'

        def __init__(self):
            filename = os.path.expanduser(TokenCache._TOKEN_FILE)
            if os.path.exists(filename):
                f = open(filename, 'r')
                self.cache = pickle.load(f)
                self.userids = pickle.load(f)
                f.close()
            else:
                self.cache = {}
                self.userids = {}

        def saveCache(self):
            filename = os.path.expanduser(TokenCache._TOKEN_FILE)
            f = open(filename, 'w')
            pickle.dump(self.cache, f)
            pickle.dump(self.userids, f)
            f.close()


        def addToken(self, token):
            self.cache[token.userid] = token
            self.userids[token.email] = token.userid
            self.saveCache()


def local_date(string):
    dt = datetime.strptime(string[0:25], '%a, %d %b %Y %H:%M:%S')
    return dt + timedelta(hours=6) + timedelta(seconds=local_time_offset())

def local_time_offset():
    """Return offset of local zone from GMT"""
    if time.localtime().tm_isdst and time.daylight:
        return -time.altzone
    else:
        return -time.timezone


def boolstr(string):
    return bool(int(string))

class ToodledoData(object):
    _typemap = {
            'server': {
                'unixtime': int,
                'date': local_date,
                'tokenexpires': float
                },
            'folder': {
                'id': int,
                'archived': boolstr,
                'private': boolstr,
                'order': int
                },
            'context': {
                'id': int,
                'default': boolstr,
                },
            'goal': {
                'id': int,
                'level': int,
                'contributes': int,
                'archived': boolstr
                },
            'account': {
                'userid': str,
                'alias': str,
                'pro': boolstr,
                'dateformat': int,
                'timezone': int,
                'hidemonths': int,
                'hotlistpriority': int,
                'hotlistduedate': int,
                'lastaddedit': str,
                'lastdelete': str,
                'lastfolderedit': str,
                'lastcontextedit': str,
                'lastgoaledit': str,
                'lastnotebookedit': str,
                },
            }

    def __init__(self,node=None):
        typemap = ToodledoData._typemap[node.tag]
        for elem in node.getchildren():
             self.__dict__[elem.tag] = typemap[elem.tag](elem.text)
        for a in node.attrib:
             self.__dict__[a] = typemap[a](node.attrib[a])
        if not node.text.isspace() :
            self.title = node.text

    def __repr__(self):
        return str(self.__dict__)


class ApiClient(object):
    ''' Toodledo API client'''
    _SERVICE_URL = 'http://www.toodledo.com/api.php?'

    def __init__(self, key=None):
        ''' Initializes a new ApiClient w/o auth credentials'''
        self._urlopener = urllib2.build_opener()

        self.key = key
        self.token = None
        self.userid = None

    def set_urlopener(self, opener):
        self._urlopener = opener


    def _call(self, **kwargs):
        assert('method' in kwargs)
        url = self._create_url(**kwargs)
        return self._urlopener.open(url)


    def _create_url(self,**kwargs):
        url = ApiClient._SERVICE_URL
        # add args to url (key1=value1;key2=value2)
        # trailing underscores are stripped from keys to allow keys like pass_
        url += ';'.join(key.rstrip('_') + '=' + kwargs[key] for key in sorted(kwargs))
        return url

    def authenticate(self, email, passwd):
        ''' Uses credentials to get userid, token and auth key'''
        self.userid = self.getUserid(email,passwd)
        self.token = self.getToken()
        self.key = self._generateKey(self.userid, self.token, passwd)

    @property
    def isAuthenticated(self):
        return bool(self.key is not None)

    def _generateKey(self, userid, token, passwd):
        ''' Generates a key as specified in the API docs'''
        return md5(md5(passwd).hexdigest() + token + userid).hexdigest()


    def getUserid(self, email, passwd):
        stream = self._call(method='getUserid', email=email, pass_=passwd)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)
        else:
            return root_node.text

    def getToken(self,userid=None):
        if userid is None:
            if self.userid is not None:
                userid = self.userid
            else:
                raise Exception() # TODO: 

        stream = self._call(method='getToken', userid=userid)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)
        else:
            return root_node.text

    def getServerInfo(self,key=None):
        if key is None:
            key = self.key
        stream = self._call(method='getServerInfo', key=key)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)

        return ToodledoData(root_node) 

    def getFolders(self,key=None):
        if key is None:
            key = self.key
        stream = self._call(method='getFolders', key=key)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)

        folders = []
        for elem in root_node.getchildren():
            folders.append( ToodledoData(elem))
        return folders

    def getContexts(self,key=None):
        if key is None:
            key = self.key
        stream = self._call(method='getContexts', key=key)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)

        contexts = []
        for elem in root_node.getchildren():
            contexts.append( ToodledoData(elem))
        return contexts

    def getAccountInfo(self,key=None):
        if key is None:
            key = self.key
        stream = self._call(method='getAccountInfo', key=key)
        xmltree = ET.parse(stream)
        root_node = xmltree.getroot()

        if root_node.tag == 'error':
            raise ToodledoError(root_node.text)

        return ToodledoData(root_node)

