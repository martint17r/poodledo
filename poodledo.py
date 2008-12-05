#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import urllib
import urllib2

import elementtree.ElementTree as ET
import time
from datetime import datetime, timedelta
from md5 import md5

__all__ = ['ApiClient']

class ToodledoError(Exception):
    ''' Error return from Toodledo API server'''

    def __init__(self, error_msg):
        self.msg = error_msg

    def __str__(self):
        return "Toodledo server returned error: %s" % self.msg


class ToodledoData(object):
    _typemap = {
            'server': {
                'unixtime': int,
                'date': _local_date,
                'tokenexpires': float
                },
            'folder': {
                'id': int,
                'archived': _boolstr,
                'private': _boolstr,
                'order': int
                },
            'context': {
                'id': int,
                'default': _boolstr,
                },
            'goal': {
                'id': int,
                'level': int,
                'contributes': int,
                'archived': _boolstr
                },
            'account': {
                'userid': str,
                'alias': str,
                'pro': _boolstr,
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


    def _create_url(self,**kwargs):
        ''' Creates a request url by appending key-value pairs to the SERVICE_URL'''
        url = ApiClient._SERVICE_URL
        # add args to url (key1=value1;key2=value2)
        # trailing underscores are stripped from keys to allow keys like pass_
        url += ';'.join(key.rstrip('_') + '=' + kwargs[key] for key in sorted(kwargs))
        return url

    def _call(self, **kwargs):
        assert('method' in kwargs)
        url = self._create_url(**kwargs)
        return self._urlopener.open(url)

    def _check_for_error(self, node):
        if node.tag == 'error':
            raise ToodledoError(node.text)

    def _get_call(self,method,key=None, **kwargs):
        if key is None:
            key = self.key
        stream = self._call(method=method, key=key, **kwargs)
        root_node = ET.parse(stream).getroot()
        self._check_for_error(root_node)
        return ToodledoData(root_node)

    def _get_list_call(self,method,key=None,**kwargs):
        if key is None:
            key = self.key
        stream = self._call(method=method, key=key, **kwargs)
        root_node = ET.parse(stream).getroot()
        self._check_for_error(root_node)
        return [ ToodledoData(elem) for elem in root_node.getchildren() ]

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
        root_node = ET.parse(stream).getroot()
        self._check_for_error(root_node)
        return root_node.text

    def getToken(self,userid=None):
        if userid is None:
            if self.userid is not None:
                userid = self.userid
            else:
                raise Exception() # TODO: 
        root_node = ET.parse(self._call(method='getToken', userid=userid)).getroot()
        self._check_for_error(root_node)
        return root_node.text

    def getServerInfo(self,key=None):
        return self._get_call(method='getServerInfo', key=key)

    def getAccountInfo(self,key=None):
        return self._get_call(method='getAccountInfo', key=key)


    def getFolders(self,key=None):
        return self._get_list_call('getFolders',key=key)

    def getContexts(self,key=None):
        return self._get_list_call('getContexts',key=key)

    def getGoals(self,key=None):
        return self._get_list_call('getGoals',key=key)


def _local_date(string):
    dt = datetime.strptime(string[0:25], '%a, %d %b %Y %H:%M:%S')
    return dt + timedelta(hours=6) + timedelta(seconds=_local_time_offset())

def _local_time_offset():
    """Return offset of local zone from GMT"""
    if time.localtime().tm_isdst and time.daylight:
        return -time.altzone
    else:
        return -time.timezone

def _boolstr(string):
    return bool(int(string))
