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
from datetime import datetime
from pkg_resources import resource_filename
from bhrelations import db_default
from bhrelations.model import Relation
from multiproduct.api import ISupportMultiProductEnvironment
from trac.core import (Component, implements, TracError, Interface,
                       ExtensionPoint)
from trac.env import IEnvironmentSetupParticipant
from trac.db import DatabaseManager
from trac.resource import (ResourceSystem, Resource,
                           get_resource_shortname, Neighborhood)
from trac.ticket import Ticket, ITicketManipulator, ITicketChangeListener
from trac.util.datefmt import utc, to_utimestamp
from trac.web.chrome import ITemplateProvider

PLUGIN_NAME = 'Bloodhound Relations Plugin'


class BaseValidationError(TracError):
    def __init__(self, message, title=None, show_traceback=False):
        super(BaseValidationError, self).__init__(
            message, title, show_traceback)
        self.failed_ids = []


class CycleValidationError(BaseValidationError):
    pass


class ParentValidationError(BaseValidationError):
    pass


#TODO: consider making the interface part of future
# I[*|Resource]ChangingListener approach based on output from the
# correlated discussion in Trac community
# (http://trac.edgewall.org/ticket/11148)
class IRelationChangingListener(Interface):
    """
    Extension point interface for components that require notification
    when relations are created or deleted and database transaction is not
    yet committed. The interface can be used when database actions have to be
    made by listener must be performed within the same transaction as
    relations modification.

    Caution:
    Because the database transaction is not yet committed during the event
    notification, a long running listener activity may
    influence overall database performance or raise lock
    or transaction timeout errors. If component have to perform non-transaction
    activity, use IRelationChanged interface instead.

    If a listener raises an exception, all changes that were made within the
    transaction will not be applied.
    """

    def adding_relation(relation):
        """
        Called when a relation was added but transaction was not committed.
        """

    def deleting_relation(relation, when):
        """
        Called when a relation was added but transaction was not committed.
        """


class EnvironmentSetup(Component):
    implements(IEnvironmentSetupParticipant, ISupportMultiProductEnvironment,
               ITemplateProvider)

    def environment_created(self):
        self.upgrade_environment(self.env.db_transaction)

    def environment_needs_upgrade(self, db):
        """Detects if the installed db version matches the running system"""
        db_installed_version = self._get_version(db)

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
        db_installed_version = self._get_version(db)
        if db_installed_version < 1:
            self._initialize_db(db)
            self._update_db_version(db, db_default.DB_VERSION)
            #add upgrade logic later if needed

    def _get_version(self, db):
        """Finds the current version of the bloodhound database schema"""
        rows = db("""
            SELECT value FROM system WHERE name = %s
            """, (db_default.DB_SYSTEM_KEY,))
        return int(rows[0][0]) if rows else -1

    def _update_db_version(self, db, version):
        old_version = self._get_version(db)
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
                """ % (db_default.DB_SYSTEM_KEY, version))
        return version

    def _initialize_db(self, db):
        # pylint: disable=protected-access
        self.log.debug("creating initial db schema for %s.", PLUGIN_NAME)
        db_connector, dummy = DatabaseManager(self.env)._get_connector()
        for table in db_default.SCHEMA:
            for statement in db_connector.to_sql(table):
                db(statement)

    # ITemplateProviderMethods
    def get_templates_dirs(self):
        """provide the plugin templates"""
        return [resource_filename(__name__, 'templates')]


class RelationsSystem(Component):
    PARENT_RELATION_TYPE = 'parent'
    CHILDREN_RELATION_TYPE = 'children'
    RELATIONS_CONFIG_NAME = 'bhrelations_links'

    changing_listeners = ExtensionPoint(IRelationChangingListener)

    def __init__(self):
        self._links, self._labels, self._validators, self._blockers, \
            self._copy_fields = self._get_links_config()

        self.link_ends_map = {}
        for end1, end2 in self.get_ends():
            self.link_ends_map[end1] = end2
            if end2 is not None:
                self.link_ends_map[end2] = end1

    def get_ends(self):
        return self._links

    def add(self,
            source_resource_instance,
            destination_resource_instance,
            relation_type,
            comment=None,
            author=None,
            when=None):
        source = ResourceIdSerializer.get_resource_id_from_instance(
            self.env, source_resource_instance)
        destination = ResourceIdSerializer.get_resource_id_from_instance(
            self.env, destination_resource_instance)
        if when is None:
            when = datetime.now(utc)
        relation = Relation(self.env)
        relation.source = source
        relation.destination = destination
        relation.type = relation_type
        relation.comment = comment
        relation.author = author
        relation.when = when
        self.add_relation(relation)
        return relation

    def get_reverted_relation(self, relation):
        """Return None if relation is one way"""
        other_end = self.link_ends_map[relation.type]
        if other_end:
            return relation.clone_reverted(other_end)

    def add_relation(self, relation):
        #TBD: add changes in source and destination ticket history
        self.validate(relation)
        with self.env.db_transaction:
            relation.insert()
            reverted_relation = self.get_reverted_relation(relation)
            if reverted_relation:
                reverted_relation.insert()

            for listener in self.changing_listeners:
                listener.adding_relation(relation)

            from bhrelations.notification import RelationNotifyEmail
            RelationNotifyEmail(self.env).notify(relation)

    def delete(self, relation_id, when=None):
        if when is None:
            when = datetime.now(utc)
        relation = Relation.load_by_relation_id(self.env, relation_id)
        source = relation.source
        destination = relation.destination
        relation_type = relation.type
        with self.env.db_transaction:
            cloned_relation = relation.clone()
            relation.delete()
            other_end = self.link_ends_map[relation_type]
            if other_end:
                reverted_relation = Relation(self.env, keys=dict(
                    source=destination,
                    destination=source,
                    type=other_end,
                ))
                reverted_relation.delete()

            for listener in self.changing_listeners:
                listener.deleting_relation(cloned_relation, when)

            from bhrelations.notification import RelationNotifyEmail
            RelationNotifyEmail(self.env).notify(cloned_relation, deleted=when)

    def delete_resource_relations(self, resource_instance):
        sql = "DELETE FROM " + Relation.get_table_name() + \
              " WHERE source=%s OR destination=%s"
        full_resource_id = ResourceIdSerializer.get_resource_id_from_instance(
            self.env, resource_instance)
        with self.env.db_transaction as db:
            db(sql, (full_resource_id, full_resource_id))

    def _debug_select(self):
        """The method is used for debug purposes"""
        sql = "SELECT id, source, destination, type FROM bloodhound_relations"
        with self.env.db_query as db:
            return [db(sql)]

    def get_relations(self, resource_instance):
        relation_list = []
        for relation in self._select_relations_for_resource_instance(
                resource_instance):
            relation_list.append(dict(
                relation_id=relation.get_relation_id(),
                destination_id=relation.destination,
                destination=ResourceIdSerializer.get_resource_by_id(
                    relation.destination),
                type=relation.type,
                comment=relation.comment,
                when=relation.when,
                author=relation.author,
            ))
        return relation_list

    def _select_relations_for_resource_instance(self, resource):
        resource_full_id = ResourceIdSerializer.get_resource_id_from_instance(
            self.env, resource)
        return self._select_relations(resource_full_id)

    def _select_relations(
            self, source, resource_type=None):
        #todo: add optional paging for possible umbrella tickets with
        #a lot of child tickets
        where = dict(source=source)
        if resource_type:
            where["type"] = resource_type
            order_by = ["destination"]
        else:
            order_by = ["type", "destination"]
        return Relation.select(
            self.env,
            where=where,
            order_by=order_by
        )

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
                blockers[end2] = config.getbool(end2 + '.blocks',
                                                default=False)

            # <end>.copy_fields may be absent or intentionally set empty.
            # config.getlist() will return [] in either case, so check that
            # the key is present before assigning the value
            for end in [end1, end2]:
                if end:
                    cf_key = '%s.copy_fields' % end
                    if cf_key in config:
                        copy_fields[end] = config.getlist(cf_key)

        return links, labels, validators, blockers, copy_fields

    def validate(self, relation):
        validator = self._get_validator(relation.type)
        if validator:
            validator(relation)

    def is_blocker(self, relation_type):
        return self._blockers[relation_type]

    def _get_validator(self, relation_type):
        #todo: implement generic validator factory based on interfaces
        validator_name = self._validators.get(relation_type)
        if validator_name == 'no_cycle':
            validator = self._validate_no_cycle
        elif validator_name == 'parent_child':
            validator = self._validate_parent
        else:
            validator = None
        return validator

    def _validate_no_cycle(self, relation):
        """If a path exists from relation's destination to its source,
         adding the relation will create a cycle.
         """
        path = self._find_path(relation.destination,
                               relation.source,
                               relation.type)
        if path:
            cycle_str = [self.get_resource_name_from_id(resource_id)
                         for resource_id in path]
            error = 'Cycle in ''%s'': %s' % (
                self.render_relation_type(relation.type),
                ' -> '.join(cycle_str))
            error = CycleValidationError(error)
            error.failed_ids = path
            raise error

    def _validate_parent(self, relation):
        self._validate_no_cycle(relation)

        if relation.type == self.PARENT_RELATION_TYPE:
            source = relation.source
        elif relation.type == self.CHILDREN_RELATION_TYPE:
            source = relation.destination
        else:
            return None

        parent_relations = self._select_relations(
            source, self.PARENT_RELATION_TYPE)
        if len(parent_relations) > 0:
            source_resource_name = self.get_resource_name_from_id(
                relation.source)
            parent_ids_ins_string = ", ".join(
                [self.get_resource_name_from_id(relation.destination)
                 for relation in parent_relations]
            )
            error = "Multiple links in '%s': %s -> [%s]" % (
                self.render_relation_type(relation.type),
                source_resource_name,
                parent_ids_ins_string)
            ex = ParentValidationError(error)
            ex.failed_ids = [relation.destination
                             for relation in parent_relations]
            raise ex

    def _find_path(self, source, destination, relation_type):
        known_nodes = set()
        new_nodes = {source}
        paths = {(source, source): [source]}

        while new_nodes:
            known_nodes = set.union(known_nodes, new_nodes)
            with self.env.db_query as db:
                relations = dict(db("""
                    SELECT source, destination
                      FROM bloodhound_relations
                     WHERE type = '%(relation_type)s'
                       AND source IN (%(new_nodes)s)
                """ % dict(
                    relation_type=relation_type,
                    new_nodes=', '.join("'%s'" % n for n in new_nodes))
                ))
            new_nodes = set(relations.values()) - known_nodes
            for s, d in relations.items():
                paths[(source, d)] = paths[(source, s)] + [d]
            if destination in new_nodes:
                return paths[(source, destination)]

    def render_relation_type(self, end):
        return self._labels[end]

    def get_relation_types(self):
        return self._labels

    def find_blockers(self, resource_instance, is_blocker_method):
        # tbd: do we blocker finding to be recursive
        all_blockers = []
        for relation in self._select_relations_for_resource_instance(
                resource_instance):
            if self.is_blocker(relation.type):
                resource = ResourceIdSerializer.get_resource_by_id(
                    relation.destination)
                resource_instance = is_blocker_method(resource)
                if resource_instance is not None:
                    all_blockers.append(resource_instance)
                    # blockers = self._recursive_find_blockers(
                    #     relation, is_blocker_method)
                    # if blockers:
                    #     all_blockers.extend(blockers)
        return all_blockers

    def get_resource_name_from_id(self, resource_id):
        resource = ResourceIdSerializer.get_resource_by_id(resource_id)
        return get_resource_shortname(self.env, resource)


class ResourceIdSerializer(object):
    RESOURCE_ID_DELIMITER = u":"

    @classmethod
    def get_resource_by_id(cls, resource_full_id):
        """
        * resource_full_id: fully qualified resource id in format
        "product:ticket:123". In case of global environment it is ":ticket:123"
        """
        nbhprefix, realm, resource_id = cls.split_full_id(resource_full_id)
        if nbhprefix:
            neighborhood = Neighborhood('product', nbhprefix)
            return neighborhood.child(realm, id=resource_id)
        else:
            return Resource(realm, id=resource_id)

    @classmethod
    def split_full_id(cls, resource_full_id):
        return resource_full_id.split(cls.RESOURCE_ID_DELIMITER)

    @classmethod
    def get_resource_id_from_instance(cls, env, resource_instance):
        """
        * resource_instance: can be instance of a ticket, wiki page etc.
        """
        resource = resource_instance.resource
        # nbhprefix = ResourceSystem(env).neighborhood_prefix(
        #     resource.neighborhood)

        #TODO: temporary workaround for the ticket specific behavior
        #change it to generic resource behaviour
        ticket = resource_instance
        nbhprefix = ticket["product"]

        resource_full_id = cls.RESOURCE_ID_DELIMITER.join(
            (nbhprefix, resource.realm, unicode(resource.id))
        )
        return resource_full_id


class TicketRelationsSpecifics(Component):
    implements(ITicketManipulator, ITicketChangeListener)

    #ITicketChangeListener methods

    def ticket_created(self, ticket):
        pass

    def ticket_changed(self, ticket, comment, author, old_values):
        pass

    def ticket_deleted(self, ticket):
        RelationsSystem(self.env).delete_resource_relations(ticket)

    #ITicketManipulator methods

    def prepare_ticket(self, req, ticket, fields, actions):
        pass

    def validate_ticket(self, req, ticket):
        action = req.args.get('action')
        if action == 'resolve':
            blockers = RelationsSystem(self.env).find_blockers(
                ticket, self.is_blocker)
            if blockers:
                blockers_str = ', '.join(
                    get_resource_shortname(self.env, blocker_ticket.resource)
                    for blocker_ticket in unique(blockers))
                msg = ("Cannot resolve this ticket because it is "
                       "blocked by tickets [%s]"
                       % blockers_str)
                yield None, msg

    def is_blocker(self, resource):
        ticket = self._create_ticket_by_full_id(resource)
        if ticket['status'] != 'closed':
            return ticket
        return None

    def _create_ticket_by_full_id(self, resource):
        env = self._get_env_for_resource(resource)
        if resource.realm == "ticket":
            return Ticket(env, resource.id)
        else:
            raise TracError("Resource type %s is not supported by " +
                            "Bloodhound Relations" % resource.realm)

    def _get_env_for_resource(self, resource):
        if hasattr(resource, "neighborhood"):
            env = ResourceSystem(self.env).load_component_manager(
                resource.neighborhood)
        else:
            env = self.env
        return env


class TicketChangeRecordUpdater(Component):
    implements(IRelationChangingListener)

    def adding_relation(self, relation):
        self.update_tickets_change_records(
            relation, False, relation.time)

    def deleting_relation(self, relation, when):
        when_ts = to_utimestamp(when)
        self.update_tickets_change_records(relation, True, when_ts)

    def update_tickets_change_records(self, relation, is_delete, when_ts):
        relation_system = RelationsSystem(self.env)
        with self.env.db_direct_transaction as db:
            self._add_ticket_change_record(
                db,
                relation,
                relation_system,
                is_delete,
                when_ts
            )

            reverted_relation = relation_system.get_reverted_relation(relation)
            if reverted_relation:
                self._add_ticket_change_record(
                    db,
                    reverted_relation,
                    relation_system,
                    is_delete,
                    when_ts
                )

    def _get_ticket_id_and_product(self, resource_full_id):
        nbhprefix, realm, resource_id = ResourceIdSerializer.split_full_id(
            resource_full_id)
        ticket_id = None
        if realm == "ticket":
            ticket_id = int(resource_id)
        return ticket_id, nbhprefix

    def _add_ticket_change_record(
            self, db, relation, relation_system, is_delete, when_ts):
        ticket_id, product = self._get_ticket_id_and_product(relation.source)
        if ticket_id is None:
            return

        related_resource_name = relation_system.get_resource_name_from_id(
            relation.destination)
        if is_delete:
            old_value = related_resource_name
            new_value = None
        else:
            old_value = None
            new_value = related_resource_name

        db("""INSERT INTO ticket_change
            (ticket, time, author, field, oldvalue, newvalue, product)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
           (ticket_id,
            when_ts,
            relation.author,
            relation.type,
            old_value,
            new_value,
            product))

# Copied from trac/utils.py, ticket-links-trunk branch
def unique(seq):
    """Yield unique elements from sequence of hashables, preserving order.
    (New in 0.13)
    """
    seen = set()
    return (x for x in seq if x not in seen and not seen.add(x))

