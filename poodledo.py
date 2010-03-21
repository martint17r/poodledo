#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os
import urllib
import urllib2

import sys
try:
    import xml.etree.cElementTree as ET
except ImportError:
    try:
        import elementtree.ElementTree as ET
    except ImportError:
        sys.exit("poodledo requires either Python 2.5+, or the ElementTree module installed.")

import time
from datetime import datetime, timedelta

try:
    import yaml
    default_auth_handler="YamlAuth"
except ImportError:
    default_auth_handler=None

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

__all__ = ['ApiClient']

def _local_date(string):
    dt = datetime.strptime(string[0:25], '%a, %d %b %Y %H:%M:%S')
    return dt + timedelta(hours=6) + timedelta(seconds=_local_time_offset())

def _local_time_offset():
    """Return offset of local zone from GMT"""
    if time.localtime().tm_isdst and time.daylight:
        return -time.altzone
    else:
        return -time.timezone

def _date(string):
    return datetime.st

def _boolstr(string):
    return bool(int(string))

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
                'serveroffset': int,
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
                'def': _boolstr,
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
            'task': {
                'id': int,
                'parent': int,
                'children': int,
                'title': unicode,
                'tag': str,
                'folder': int,
                'context':  str,
                'goal': str,
                'added': str,
                'modified': str,
                'startdate': str,
                'starttime': str,
                'duedate': str,
                'duetime': str,
                'completed': str,
                'reminder': int,
                'repeat': int,
                'rep_advanced': str,
                'status': int,
                'star': _boolstr,
                'stamp': str,
                'priority': int,
                'length': int,
                'timer': int,
                'note': unicode 
                },
            'note': {
                'id': int,
                'folder': int,
                'added': str,
                'modified': str,
                'title': str,
                'text': str,
                'private': _boolstr,
                'stamp': str,
                },
            }

    def __init__(self,node=None):
        typemap = ToodledoData._typemap[node.tag]
        for elem in node.getchildren():
             self.__dict__[elem.tag] = typemap[elem.tag](elem.text)
        for a in node.attrib:
             self.__dict__[a] = typemap[a](node.attrib[a])
        if node.text and not node.text.isspace() :
            self.title = node.text

    def __repr__(self):
        return str(self.__dict__)


class PoodledoError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return 'PoodledoError("%s")' % self.msg

    def __str__(self):
        return self.msg

def check_api_key(f):
    ''' A decorator that makes the decorated function check for a API key'''
    def fn(*args, **kwargs):
        self = args[0]
        # check if key is set to a value
        if 'key' in kwargs and kwargs['key'] is not None:
            return f(*args, **kwargs)
        else:
            # try to get the key from the ApiClient
            if self.key is not None:
                kwargs['key'] = self.key
                return f(*args, **kwargs)
            else:
                raise PoodledoError('need API key to call function %s' % f.__name__)
    return fn

def returns_list(f):
    def fn(self, **kwargs):
        return [ ToodledoData(elem) for elem in f(self, **kwargs) ]
    return fn

def returns_item(f):
    def fn(self, **kwargs):
        return ToodledoData(f(self, **kwargs))
    return fn


class AuthHandler(object):
    def __init__(self):
        self.key=None

    @property
    def isAuthenticated(self):
        return bool(self.key is not None)

class PlainAuth(AuthHandler):
    def __init__(self, email, passwd):
        super(PlainAuth, self).__init__()
        self.email=email
        self.passwd=passwd
        self.userid=None
        self.token=None

    def _generateKey(self, userid, token, passwd):
        ''' Generates a key as specified in the API docs'''
        return md5(md5(passwd).hexdigest() + token + userid).hexdigest()

    def authenticate(self, callee, application_id):
        if self.key!=None:
            return self.key
        if self.userid==None:
            self.userid = self._getUserid(callee)
        if self.token==None:
            self.token = self._getToken(callee, application_id)
        self.key = self._generateKey(self.userid, self.token, self.passwd)
        return self.key

    def _getUserid(self, callee):
        self.userid = callee(method='getUserid', email=self.email, pass_=self.passwd).text
        if self.userid == '1':
            raise ToodledoError('invalid username/password')
        return self.userid

    def _getToken(self, callee, application_id):
        if self.userid is not None:
            userid = self.userid
        else:
            raise Exception() # TODO:
        return callee(method='getToken', userid=userid, appid=application_id).text

class YamlAuth(PlainAuth):
    def __init__(self, basedir="~/.toodledo", filename="user-config.yml"):
        self.tokenNeedsValidation=False
        self.basedir=basedir
        self.configfname=filename
        self.config=self._loadConfig(basedir, filename)
        super(YamlAuth, self).__init__(email=None, passwd=self.config['connection']['password'])
        self.userid=self.config['connection']['user_id']
        self._loadToken()

    def _calcTokenPath(self):
        tokenpath=os.path.join(self.basedir, "tokens", self.userid)
        return os.path.expanduser(tokenpath)

    def _loadToken(self):
        tokenpath=self._calcTokenPath()
        if not os.path.exists(os.path.dirname(tokenpath)):
            return False
        if not os.path.exists(tokenpath):
            return False
        tokenfile=open(tokenpath, 'r')
        self.token=yaml.load(tokenfile)
        self.tokenNeedsValidation=True

    def _getToken(self, callee, application_id):
        token=super(YamlAuth, self)._getToken(callee, application_id)
        self._storeToken(token)
        return token

    def _storeToken(self, token):
        tokenpath=self._calcTokenPath()
        tokendir=os.path.dirname(tokenpath)
        if not os.path.exists(tokendir):
            os.makedirs(tokendir)
        tokenfile=open(tokenpath, 'w')
        tokenfile.write(token)
        tokenfile.close()

    def _validateToken(self, callee):
        self.tokenNeedsValdation=False
        key = self._generateKey(self.userid, self.token, self.passwd)
        try:
            callee(method='getServerInfo', key=key).text
        except:
            self.token=None

    def authenticate(self, callee, application_id):
        if self.tokenNeedsValidation:
            self._validateToken(callee)
        return super(YamlAuth, self).authenticate(callee, application_id)

    def _loadConfig(self, basedir, file):
        userfname=os.path.join(basedir, file)
        userfname=os.path.expanduser(userfname)
        if os.path.exists(userfname):
            usercfgfile=open(userfname, 'r')
            config=yaml.load(usercfgfile)
        else:
            raise PoodledoError("'%s' not found - aborting" % userfname)
        return config

class ApiClient(object):
    ''' Toodledo API client'''
    _SERVICE_URL = 'http://www.toodledo.com/api.php?'

    def __init__(self, key=None, application_id="poodledo", auth_handler=default_auth_handler):
        ''' Initializes a new ApiClient w/o auth credentials'''
        self._urlopener = urllib2.build_opener()

        self.key = key
        self.token = None
        self.userid = None
        self.application_id = application_id
        if auth_handler==None or isinstance(auth_handler, type(AuthHandler)):
            self.auth_handler = auth_handler
        elif isinstance(auth_handler, basestring):
            valid_handlers={'YamlAuth': YamlAuth}
            self.auth_handler = valid_handlers[auth_handler]()

    def set_urlopener(self, opener):
        self._urlopener = opener


    def _create_url(self,**kwargs):
        ''' Creates a request url by appending key-value pairs to the SERVICE_URL'''
        url = ApiClient._SERVICE_URL
        # add args to url (key1=value1;key2=value2)
        # trailing underscores are stripped from keys to allow keys like pass_
        url += ';'.join(key.rstrip('_') + '=' + urllib2.quote(str(kwargs[key])) for key in sorted(kwargs))
        return url

    def _check_for_error(self, node):
        if node.tag == 'error':
            raise ToodledoError(node.text)

    def _call(self, **kwargs):
        url = self._create_url(**kwargs)
        stream = self._urlopener.open(url)
        root_node = ET.parse(stream).getroot()
        self._check_for_error(root_node)
        return root_node

    def authenticate(self, email=None, passwd=None):
        ''' 
            Uses credentials to get userid, token and auth key.

            Returns the auth key, which can be cached and used later in the constructor in 
            order to skip authenticate()
        '''
        if email!=None and passwd!=None:
            self.auth_handler = PlainAuth(email, passwd)
        return self._authenticate()

    def _authenticate(self):
        if self.key!=None:
            return self.key
        if self.auth_handler==None:
            raise PoodledoError('cannot authenticate - please pass in email and password or use an auth handler')
        self.key=self.auth_handler.authenticate(self._call, self.application_id)
        return self.key

    @property
    def isAuthenticated(self):
        if self.auth_handler==None:
            raise PoodledoError('cannot authenticate - please pass in email and password or use an auth handler')
        return self.auth_handler.isAuthenticated

    @check_api_key
    @returns_item
    def getServerInfo(self, key=None):
        return self._call(method='getServerInfo', key=key)

    @check_api_key
    @returns_item
    def getAccountInfo(self, key=None):
        return self._call(method='getAccountInfo', key=key)

    @check_api_key
    @returns_list
    def getFolders(self, key=None):
        return self._call(method='getFolders', key=key)

    @check_api_key
    @returns_list
    def getContexts(self, key=None):
        return self._call(method='getContexts', key=key)

    @check_api_key
    @returns_list
    def getGoals(self, key=None):
        return self._call(method='getGoals', key=key)

    @check_api_key
    @returns_list
    def getTasks(self, key=None, **kwargs):
        return self._call(method='getTasks', key=key, **kwargs)

    @check_api_key
    @returns_list
    def getDeleted(self, after, key=None ):
        return self._call(method='getDeleted', key=key, after=after)

    @check_api_key
    def addTask(self,key=None,**kwargs):
        return self._call(method='addTask', key=key, **kwargs).text

    @check_api_key
    def addContext(self,key=None,**kwargs):
        return self._call(method='addContext', key=key, **kwargs).text

    @check_api_key
    def addGoal(self,key=None,**kwargs):
        return self._call(method='addGoal', key=key, **kwargs).text

    @check_api_key
    def addFolder(self,key=None,**kwargs):
        return self._call(method='addFolder', key=key, **kwargs).text

    @check_api_key
    def deleteFolder(self, id_, key=None):
        return self._call(method='deleteFolder', id_=id_, key=key).text

    @check_api_key
    def deleteContext(self, id_, key=None):
        return self._call(method='deleteContext', id_=id_, key=key).text

    @check_api_key
    def deleteGoal(self, id_, key=None):
        return self._call(method='deleteGoal', id_=id_, key=key).text

    @check_api_key
    def deleteTask(self, id_, key=None):
        return self._call(method='deleteTask', id_=id_, key=key).text

    @check_api_key
    def editTask(self, id_, key=None, **kwargs):
        return self._call(method='editTask', id_=id_, key=key, **kwargs).text

    @check_api_key
    def editFolder(self, id_, key=None, **kwargs):
        return self._call(method='editFolder', id_=id_, key=key, **kwargs).text

    def createAccount(self, email, pass_):
        '''Create a new account

        Returns:
            userid - 15 or 16 character hexidecimal string
        '''
        return self._call(method='createAccount', email=_email, pass_=pass_).text

# Notes API #######################################

    @check_api_key
    @returns_list
    def getNotes(self, key=None):
        return self._call(method='getNotes', key=key)

    @check_api_key
    @returns_list
    def getDeletedNotes(self, after, key=None ):
        return self._call(method='getDeletedNotes', key=key, after=after)

    @check_api_key
    def addNote(self,key=None,**kwargs):
        return self._call(method='addNote', key=key, **kwargs).text

    @check_api_key
    def deleteNote(self, id_, key=None):
        return self._call(method='deleteNote', id_=id_, key=key).text

    @check_api_key
    def editNote(self, id_, key=None, **kwargs):
        return self._call(method='editNote', id_=id_, key=key, **kwargs).text

