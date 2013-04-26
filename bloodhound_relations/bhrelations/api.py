#!/usr/bin/env python
# -*- coding: UTF-8 -*-

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
from bhrelations import db_default
from bhrelations.model import Relation
from multiproduct.env import ProductEnvironment
from trac.core import Component, implements, TracError
from trac.env import IEnvironmentSetupParticipant
from trac.db import DatabaseManager
from trac.resource import manager_for_neighborhood, ResourceSystem
from trac.ticket import Ticket

PLUGIN_NAME = 'Bloodhound Relations Plugin'


class EnvironmentSetup(Component):
    implements(IEnvironmentSetupParticipant)

    def environment_created(self):
        self.found_db_version = 0
        self.upgrade_environment(self.env.db_transaction)

    def environment_needs_upgrade(self, db):
        """Detects if the installed db version matches the running system"""
        db_installed_version = self._get_version()

        db_version = db_default.DB_VERSION
        if db_installed_version > db_version:
            raise TracError('''Current db version (%d) newer than supported by
            this version of the %s (%d).''' % (db_installed_version,
                                               PLUGIN_NAME,
                                               db_version))
        needs_upgrade = db_installed_version < db_version
        return needs_upgrade

    def upgrade_environment(self, db):
        self.log.debug("upgrading existing environment for %s plugin." %
                       PLUGIN_NAME)
        db_installed_version = self._get_version()
        with self.env.db_direct_transaction as db:
            if db_installed_version < 1:
                self._initialize_db(db)
                self._update_db_version(db, 1)
            #add upgrade logic later if needed

    def _get_version(self):
        """Finds the current version of the bloodhound database schema"""
        rows = self.env.db_direct_query("""
            SELECT value FROM system WHERE name = %s
            """, (db_default.DB_SYSTEM_KEY,))
        return int(rows[0][0]) if rows else -1

    def _update_db_version(self, db, version):
        old_version = self._get_version()
        if old_version != -1:
            self.log.info(
                "Updating %s database schema from version %d to %d",
                PLUGIN_NAME, old_version, version)
            db("""UPDATE system SET value=%s
                      WHERE name=%s""", (version, db_default.DB_SYSTEM_KEY))
        else:
            self.log.info(
                "Initial %s database schema set to version %d",
                PLUGIN_NAME, version)
            db("""
                INSERT INTO system (name, value) VALUES ('%s','%s')
                """  % (db_default.DB_SYSTEM_KEY, version))
        return version

    def _initialize_db(self, db):
        self.log.debug("creating initial db schema for %s.", PLUGIN_NAME)
        db_connector, dummy = DatabaseManager(self.env)._get_connector()
        for table in db_default.SCHEMA:
            for statement in db_connector.to_sql(table):
                db(statement)


class RelationsSystem(Component):

    RELATIONS_CONFIG_NAME = 'bhrelations_links'
    RESOURCE_ID_DELIMITER = u":"
    RELATION_ID_DELIMITER = u","

    def __init__(self):
        self._links, self._labels, \
        self._validators, self._blockers, \
        self._copy_fields = self._get_links_config()

        self.link_ends_map = {}
        for end1, end2 in self.get_ends():
            self.link_ends_map[end1] = end2
            if end2 is not None:
                self.link_ends_map[end2] = end1

    def get_ends(self):
        return self._links

    def add_relation(
            self,
            source_resource_instance,
            destination_resource_instance,
            relation_type,
            comment = None,
            ):
        source = self.get_resource_id(source_resource_instance)
        destination = self.get_resource_id(destination_resource_instance)
        relation = Relation(self.env)
        relation.source = source
        relation.destination = destination
        relation.type = relation_type
        relation.comment = comment
        self._add_relation_instance(relation)

    def _add_relation_instance(self, relation):
        #TBD: add changes in source and destination ticket history
        with self.env.db_transaction:
            relation.insert()
            other_end = self.link_ends_map[relation.type]
            if other_end:
                reverted_relation = relation.clone_reverted(other_end)
                reverted_relation.insert()

    def delete_relation_by_id(
            self,
            relation_id,
        ):
        source, destination, relation_type = self._parse_relation_id(
            relation_id)
        #TODO: some optimization can be introduced here to not load relations
        #before actual DELETE SQL
        relation = Relation(self.env, keys=dict(
            source=source,
            destination=destination,
            type=relation_type
            ))
        self._delete_relation_instance(relation)

    def _delete_relation_instance(self, relation):
        source = relation.source
        destination = relation.destination
        relation_type = relation.type
        with self.env.db_transaction:
            relation.delete()
            other_end = self.link_ends_map[relation_type]
            if other_end:
                reverted_relation = Relation(self.env, keys=dict(
                    source=destination,
                    destination=source,
                    type=other_end,
                ))
                reverted_relation.delete()

    def _debug_select(self):
        """The method is used for debug purposes"""
        sql = "SELECT id, source, destination, type FROM bloodhound_relations"
        with self.env.db_query as db:
            return [db(sql)]

    def get_relations_by_resource(self, resource):
        source = self.get_resource_id(resource)
        return self.get_relations_by_resource_id(source)

    def get_relations_by_resource_id(self, resource):
        #todo: add optional paging for possible umbrella tickets with
        #a lot of child tickets
        source = self.get_resource_id(resource)
        return Relation.select(
            self.env,
            where=dict(source=source),
            order_by=["type", "destination"]
            )

    def get_relations(self, resource_instance):
        source = self.get_resource_id(resource_instance)
        relations =  Relation.select(self.env, where=dict(source=source))
        relation_list = []
        for relation in relations:
            relation_list.append(dict(
                relation_id = self._create_relation_id(relation),
                destination_id = relation.destination,
                destination=self.get_resource_by_id(relation.destination),
                type = relation.type,
                comment = relation.comment
            ))
        return relation_list

    def _create_relation_id(self, relation):
        return self.RELATION_ID_DELIMITER.join((
            relation.source,
            relation.destination,
            relation.type))

    def _parse_relation_id(self, relation_id):
        source, destination, relation_type = relation_id.split(
            self.RELATION_ID_DELIMITER)
        return source, destination, relation_type

    # Copied from trac/ticket/links.py, ticket-links-trunk branch
    def _get_links_config(self):
        links = []
        labels = {}
        validators = {}
        blockers = {}
        copy_fields = {}

        config = self.config[self.RELATIONS_CONFIG_NAME]
        for name in [option for option, _ in config.options()
                     if '.' not in option]:
            ends = [e.strip() for e in config.get(name).split(',')]
            if not ends:
                continue
            end1 = ends[0]
            end2 = None
            if len(ends) > 1:
                end2 = ends[1]
            links.append((end1, end2))

            label1 = config.get(end1 + '.label') or end1.capitalize()
            labels[end1] = label1
            if end2:
                label2 = config.get(end2 + '.label') or end2.capitalize()
                labels[end2] = label2

            validator = config.get(name + '.validator')
            if validator:
                validators[end1] = validator
                if end2:
                    validators[end2] = validator

            blockers[end1] = config.getbool(end1 + '.blocks', default=False)
            if end2:
                blockers[end2] = config.getbool(end2 + '.blocks', default=False)

            # <end>.copy_fields may be absent or intentionally set empty.
            # config.getlist() will return [] in either case, so check that
            # the key is present before assigning the value
            for end in [end1, end2]:
                if end:
                    cf_key = '%s.copy_fields' % end
                    if cf_key in config:
                        copy_fields[end] = config.getlist(cf_key)

        return links, labels, validators, blockers, copy_fields

    def get_resource_id(self, resource_instance):
        resource = resource_instance.resource
        rsys = ResourceSystem(manager_for_neighborhood(
            self.env, resource.neighborhood))
        nbhprefix = rsys.neighborhood_prefix(resource.neighborhood)
        resource_full_id = self.RESOURCE_ID_DELIMITER.join(
            (nbhprefix, resource.realm, unicode(resource.id))
        )
        return resource_full_id

    def get_resource_by_id(self, resource_full_id):
        """
        Expects resource_full_id in format "product:ticket:123". In case of
        global environment: ":ticket:123"
        """
        nbhprefix, realm, id = resource_full_id.split(
            self.RESOURCE_ID_DELIMITER)
        return self._get_resource_instance(nbhprefix, realm, id)

    def _get_resource_instance(self, nbhprefix, realm, id):
        env = self._get_env_by_prefix(nbhprefix)
        if realm == "ticket":
            return Ticket(env, id)
        else:
            raise TracError("Resource type %s is not supported by " +
                            "Bloodhound Relations" % realm)

    def _get_env_by_prefix(self, nbhprefix):
        if nbhprefix:
            env = ProductEnvironment(nbhprefix)
        elif hasattr(self.env, "parent") and self.env.parent:
            env = self.env.parent
        else:
            env = self.env
        return env

