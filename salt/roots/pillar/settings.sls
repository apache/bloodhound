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

# comment out any projects here that you don't want loaded by default..
enabled_projects:
  - postgres
  - sqlite
  - bloodhound

# controls whether webserver is required:
enable_webserver: True

# these settings are not tested thoroughly with many boxes so will probably
# need correcting
{% if grains['oscodename'] in ['lucid', 'natty', 'maverick', 'squeeze'] %}
pg_version: 8.4
postgresql: postgresql-8.4
pg_hba_file: /etc/postgresql/8.4/bhcluster/pg_hba.conf
pg_hba_replace: pg_hba_8.4.conf
{% elif grains['oscodename'] == 'xenial' %}
pg_version: 9.5
postgresql: postgresql-9.5
pg_hba_file: /etc/postgresql/9.5/bhcluster/pg_hba.conf
pg_hba_replace: pg_hba_9.1.conf
{% else %}
pg_version: 9.1
postgresql: postgresql-9.1
pg_hba_file: /etc/postgresql/9.1/bhcluster/pg_hba.conf
pg_hba_replace: pg_hba_9.1.conf
{% endif %}
{% if grains['oscodename'] in ['lucid', 'natty', 'maverick'] %}
postgresql_service: postgresql-8.4
{% else %}
postgresql_service: postgresql
{% endif %}

# add new projects to this list, enable them at the top of the file
projects:
  postgres:
    dbtype: postgres
    dbname: bhdb
    dbuser: bloodhound
    dbpassword: bloodhound
    dbhost: localhost
    dbport: 5434
    adminuser: admin
    adminpassword: adminpass
    project: test
    prodprefix: TEST
  sqlite:
    dbtype: sqlite
    dbname: a
    dbuser: a
    dbpassword: a
    dbhost: a
    dbport: a
    adminuser: admin
    adminpassword: adminpass
    project: test
    prodprefix: TEST
  bloodhound:
    dbtype: postgres
    dbname: bloodhound
    dbuser: bloodhound
    dbpassword: bloodhound
    dbhost: localhost
    dbport: 5434
    adminuser: admin
    adminpassword: adminpass
    project: Bloodhound
    prodprefix: BLDHND

