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

{% set firstloop=True %}
{% for project, data in pillar['projects'].items() %} {% if project in pillar['enabled_projects'] and data['dbtype'] == 'postgres' %}

{% if firstloop %}
{% set firstloop=False %}
pg_hb.conf:
  file.managed:
    - name: {{ pillar['pg_hba_file'] }}
    - source: salt://postgresql/{{ pillar['pg_hba_replace'] }}
    - template: jinja
    - user: postgres
    - group: postgres
    - mode: 644
    - require:
      - postgres_cluster: bhcluster
      - pkg: {{ pillar['postgresql'] }}

postgresql:
  pkg:
    - name: {{ pillar['postgresql'] }}
    - installed
  service.running:
    - name: {{ pillar['postgresql_service'] }}
    - enable: True
    - watch:
      - file: {{ pillar['pg_hba_file'] }}

bhcluster:
  postgres_cluster.present:
    - name: 'bhcluster'
    - version: '{{ pillar["pg_version"] }}'
    - encoding: 'UTF8'
    - port: '{{ data["dbport"] }}'
    - require:
      - pkg: {{ pillar['postgresql'] }}
    - unless: test -d /etc/postgresql/{{ pillar["pg_version"] }}/bhcluster

{% endif %}
{% endif %} {% endfor %}
