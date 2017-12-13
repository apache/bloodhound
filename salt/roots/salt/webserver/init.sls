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

{% if pillar['enable_webserver'] %}
libapache2-mod-wsgi:
  pkg:
    - installed
    - require:
      - pkg: apache2

a2enmod wsgi:
  cmd.run:
    - unless: test -L /etc/apache2/mods-enabled/wsgi.load
    - watch:
      - pkg: libapache2-mod-wsgi
    - require:
      - pkg: apache2

a2enmod auth_digest:
  cmd.run:
    - unless: test -L /etc/apache2/mods-enabled/auth_digest.load
    - require:
      - pkg: apache2

bloodhound_site:
  file:
    - managed
    - template: jinja
    - name: /etc/apache2/sites-available/bloodhound.conf
    - source: salt://webserver/bloodhound.site
    - require:
      - pkg: apache2

{% if grains['os_family'] == 'Debian' %}
a2dissite 000-default:
  cmd.run:
    - onlyif: test -L /etc/apache2/sites-enabled/000-default.conf
    - require:
      - pkg: apache2
{% endif %}

a2ensite bloodhound:
  cmd.run:
    - unless: test -L /etc/apache2/sites-enabled/bloodhound.conf
    - watch:
      - file: bloodhound_site
    - require:
      - pkg: apache2
      - cmd: a2dissite 000-default
      - cmd: a2enmod auth_digest
      - cmd: a2enmod wsgi
      {% for project, data in pillar['projects'].items() %} {% if project in pillar['enabled_projects'] %}
      - cmd: create bloodhound {{ project }} site dirs
      {% endif %} {% endfor %}

apache2:
  pkg:
    - installed
  service:
    - running
    - watch:
      - file: bloodhound_site
      - cmd: a2ensite bloodhound
    - require:
      - pkg: apache2

{% endif %}
