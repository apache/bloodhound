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

include:
  - webserver
  - requirements
  - postgresql

/home/vagrant/bhenv:
  virtualenv.managed:
    - system_site_packages: False
    - user: vagrant
    - requirements: /vagrant/installer/requirements-dev.txt
    - cwd: /vagrant/installer/
    - require:
      - pkg: python-dev
      - pkg: python-virtualenv
      - pkg: libpq-dev

project environment requirements:
  cmd.run:
    - user: vagrant
    - cwd: /vagrant/installer/
    - name: "source /home/vagrant/bhenv/bin/activate
             && pip install -r pgrequirements.txt"
    - require:
      - virtualenv: /home/vagrant/bhenv

{% for project, data in pillar['projects'].items() %} {% if project in pillar['enabled_projects'] %}
create {{ project }} project environment:
  cmd.run:
    - user: vagrant
    - unless: "test -d /home/vagrant/environments/{{ project }}"
    - cwd: /vagrant/installer/
    - name: "source /home/vagrant/bhenv/bin/activate && 
             python bloodhound_setup.py --environments_directory=/home/vagrant/environments
                                        --project={{ project }}
                                        --default-product-prefix={{ data['prodprefix'] }}
                                        --database-type={{ data['dbtype'] }}
                                        --database-name={{ data['dbname'] }}
                                        --user={{ data['dbuser'] }}
                                        --password={{ data['dbpassword'] }}
                                        --database-port={{ data['dbport'] }}
                                        --database-host={{ data['dbhost'] }}
                                        --admin-user={{ data['adminuser'] }}
                                        --admin-password={{ data['adminpassword'] }}"
    - require:
      {% if data['dbtype'] == 'postgres' %}
      - postgres_database: bloodhounddb for {{ project }}
      {% endif %}
      - cmd: project environment requirements

create bloodhound {{ project }} site dirs:
  cmd.run:
    - user: vagrant
    - onlyif: "test -d /home/vagrant/environments/{{ project }}"
    - cwd: /home/vagrant/environments/
    - name: "source /home/vagrant/bhenv/bin/activate &&
             trac-admin {{ project }} deploy {{ project }}/site"
    - require:
      - virtualenv: /home/vagrant/bhenv
      - cmd: create {{ project }} project environment

{% if data['dbtype'] == 'postgres' %}
bloodhounduser for {{ project }}:
  postgres_user.present:
    - name: {{ data['dbuser'] }}
    - password: {{ data['dbpassword'] }}
    - user: postgres
    - db_port: {{ data['dbport'] }}
    - require:
      - pkg: {{ pillar['postgresql'] }}
      - service: {{ pillar['postgresql_service'] }}


bloodhounddb for {{ project }}:
  postgres_database.present:
    - name: {{ data['dbname'] }}
    - encoding: 'UTF8'
    - template: template0
    - owner: {{ data['dbuser'] }}
    - user: postgres
    - db_port: {{ data['dbport'] }}
    - require:
      - postgres_user: bloodhounduser for {{ project }}
{% endif %}

{% endif %}{% endfor %}
