#!/usr/bin/env python

#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.

"""Simple htdigest file creation.
Saves the need for an installed htdigest program"""

import os
import shutil
import sys
from tempfile import mkstemp
from optparse import OptionParser
from hashlib import md5
from getpass import getpass

DEFAULT_USER = 'admin'
DEFAULT_REALM = 'default'
DEFAULT_FILE = 'default.htdigest'

def htdigest_create(filename, user, realm, password, path=''):
    """Create an htdigest file by adding the user to the file
    Just in case an htdigest file already exists, this function will copy the
    data line by line into a temporary file, commenting out any lines that match
    the user and realm data. The new entry is then appended before the temporary
    copy is moved back to the original location"""
    
    user_realm = ':'.join((user, realm))
    digest = md5(':'.join((user_realm, password))).hexdigest()
    data = ':'.join((user_realm, digest)) + '\n'
    
    filepath = os.path.join(path, filename)
    temp, tempfilepath = mkstemp()
    with open(tempfilepath,'w') as tempdigestfile:
        if os.path.exists(filepath):
            with open(filepath) as origdigestfile:
                for line in origdigestfile:
                    if line.strip().startswith(user_realm + ':'):
                        tempdigestfile.write('#' + line)
                    else:
                        tempdigestfile.write(line)
        tempdigestfile.write(data)
    os.close(temp)
    if os.path.exists(filepath):
        os.remove(filepath)
    shutil.move(tempfilepath, filepath)

def main():
    """Parse arguments and run the  function"""
    
    parser = OptionParser()
    parser.add_option('-f', '--digestfile', dest='digestfile',
                      help='htdigest filename')
    parser.add_option('-r', '--realm', dest='realm',
                      help='authentication realm')
    parser.add_option('-u', '--user', dest='user',
                      help='user name')
    parser.add_option('-p', '--password', dest='password',
                      help='password for USER')
    
    (opts, args) = parser.parse_args()
    
    if not opts.digestfile:
        input_file = raw_input('Enter the file [%s]: ' % DEFAULT_FILE)
        opts.digestfile = input_file if input_file else DEFAULT_FILE
    path, filename = os.path.split(opts.digestfile)
    
    if not opts.user:
        input_user = raw_input('Enter the user [%s]: ' % DEFAULT_USER)
        opts.user = input_user if input_user else DEFAULT_USER
        
    if not opts.password:
        attempts = 3
        for attempt in range(attempts):
            if attempt > 0:
                print "Passwords empty or did not match. Please try again",
                print "(attempt %d/%d)""" % (attempt+1, attempts)
            password1 = getpass('Enter a new password for "%s": ' % opts.user)
            password2 = getpass('Please reenter the password: ')
            if password1 and password1 == password2:
                opts.password = password1
                break
        if not opts.password:
            print "Passwords did not match. Quitting."
            sys.exit(1)
    
    if not opts.realm:
        input_realm = raw_input('Enter the auth realm [%s]: ' % DEFAULT_REALM)
        opts.realm = input_realm if input_realm else DEFAULT_REALM
    
    htdigest_create(filename, opts.user, opts.realm, opts.password, path)

if __name__ == '__main__':
    main()
