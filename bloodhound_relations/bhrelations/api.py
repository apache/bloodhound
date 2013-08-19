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
import itertools

import re
from datetime import datetime
from pkg_resources import resource_filename
from bhrelations import db_default
from bhrelations.model import Relation
from bhrelations.utils import unique
from multiproduct.api import ISupportMultiProductEnvironment
from multiproduct.model import Product
from multiproduct.env import ProductEnvironment

from trac.config import OrderedExtensionsOption, Option
from trac.core import (Component, implements, TracError, Interface,
                       ExtensionPoint)
from trac.env import IEnvironmentSetupParticipant
from trac.db import DatabaseManager
from trac.resource import (ResourceSystem, Resource, ResourceNotFound,
                           get_resource_shortname, Neighborhood)
from trac.ticket import Ticket, ITicketManipulator, ITicketChangeListener
from trac.util.datefmt import utc, to_utimestamp
from trac.web.chrome import ITemplateProvider

PLUGIN_NAME = 'Bloodhound Relations Plugin'
RELATIONS_CONFIG_NAME = 'bhrelations_links'

default_bhrelations_links = {
    'children.label': 'is a child of',
    'dependency': 'dependson,dependent',
    'dependency.validators': 'NoCycles,SingleProduct',
    'dependson.blocks': 'true',
    'dependson.label': 'depends on',
    'dependent.label': 'is a dependency of',
    'oneway': 'refersto',
    'parent_children': 'parent,children',
    'parent.exclusive': 'true',
    'parent.label': 'is a parent of',
    'parent_children.validators': 'OneToMany,SingleProduct,NoCycles',
    'refersto.label': 'refers to',
    'duplicate': 'duplicateof,duplicatedby',
    'duplicate.validators': 'ReferencesOlder',
    'duplicateof.label': 'is a duplicate of',
    'duplicatedby.label': 'is duplicated by',
}


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


class IRelationValidator(Interface):
    """
    Extension point interface for relation validators.
    """

    def validate(relation):
        """
        Validate the relation. If relation is not valid, raise appropriate
        exception.
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
        needs_upgrade = db_installed_version < db_version or \
                        not list(self.config.options(RELATIONS_CONFIG_NAME))
        return needs_upgrade

    def upgrade_environment(self, db):
        self.log.debug("upgrading existing environment for %s plugin." %
                       PLUGIN_NAME)
        db_installed_version = self._get_version(db)
        if db_installed_version < 1:
            self._initialize_db(db)
            self._update_db_version(db, db_default.DB_VERSION)
            #add upgrade logic later if needed

        if not list(self.config.options(RELATIONS_CONFIG_NAME)):
            for option, value in default_bhrelations_links.iteritems():
                self.config.set(RELATIONS_CONFIG_NAME, option, value)
            self.config.save()
            print("Your environment has been upgraded with the default "
                  "[bhrelations_links] configuration.")

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

    def get_htdocs_dirs(self):
        return None


class RelationsSystem(Component):
    PARENT_RELATION_TYPE = 'parent'
    CHILDREN_RELATION_TYPE = 'children'

    changing_listeners = ExtensionPoint(IRelationChangingListener)
    all_validators = ExtensionPoint(IRelationValidator)
    global_validators = OrderedExtensionsOption(
        'bhrelations', 'global_validators',
        IRelationValidator,
        'NoSelfReferenceValidator, ExclusiveValidator, BlockerValidator',
        include_missing=False,
        doc="""Validators used to validate all relations,
        regardless of their type."""
    )

    duplicate_relation_type = Option(
        'bhrelations',
        'duplicate_relation',
        'duplicateof',
        "Relation type to be used with the resolve as duplicate workflow.")

    def __init__(self):
        links, labels, validators, blockers, copy_fields, exclusive = \
            self._parse_config()
        self._links = links
        self._labels = labels
        self._validators = validators
        self._blockers = blockers
        self._copy_fields = copy_fields
        self._exclusive = exclusive

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
        if relation_type not in self.link_ends_map:
            raise UnknownRelationType(relation_type)
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

    def _parse_config(self):
        links = []
        labels = {}
        validators = {}
        blockers = {}
        copy_fields = {}
        exclusive = set()

        config = self.config[RELATIONS_CONFIG_NAME]
        for name in [option for option, _ in config.options()
                     if '.' not in option]:
            reltypes = config.getlist(name)
            if not reltypes:
                continue
            if len(reltypes) == 1:
                reltypes += [None]
            links.append(tuple(reltypes))

            custom_validators = self._parse_validators(config, name)
            for rel in filter(None, reltypes):
                labels[rel] = \
                    config.get(rel + '.label') or rel.capitalize()
                blockers[rel] = \
                    config.getbool(rel + '.blocks', default=False)
                if config.getbool(rel + '.exclusive'):
                    exclusive.add(rel)
                validators[rel] = custom_validators

                # <end>.copy_fields may be absent or intentionally set empty.
                # config.getlist() will return [] in either case, so check that
                # the key is present before assigning the value
                cf_key = '%s.copy_fields' % rel
                if cf_key in config:
                    copy_fields[rel] = config.getlist(cf_key)
        return links, labels, validators, blockers, copy_fields, exclusive

    def _parse_validators(self, section, name):
        custom_validators = set(
            '%sValidator' % validator for validator in
            set(section.getlist(name + '.validators', [], ',', True)))
        validators = []
        if custom_validators:
            for impl in self.all_validators:
                if impl.__class__.__name__ in custom_validators:
                    validators.append(impl)
        return validators

    def validate(self, relation):
        """
        Validate the relation using the configured validators. Validation is
        always run on the relation with master type.
        """
        backrel = self.get_reverted_relation(relation)
        if backrel and (backrel.type, relation.type) in self._links:
            relation = backrel

        for validator in self.global_validators:
            validator.validate(relation)

        for validator in self._validators.get(relation.type, ()):
            validator.validate(relation)

    def is_blocker(self, relation_type):
        return self._blockers[relation_type]

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

    def get_resource_name(self, resource_id):
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
        if ticket.id is None:
            raise ValueError("Cannot get resource id for ticket "
                             "that does not exist yet.")
        nbhprefix = ticket["product"]

        resource_full_id = cls.RESOURCE_ID_DELIMITER.join(
            (nbhprefix, resource.realm, unicode(resource.id))
        )
        return resource_full_id


class TicketRelationsSpecifics(Component):
    implements(ITicketManipulator, ITicketChangeListener)

    def __init__(self):
        self.rls = RelationsSystem(self.env)

    #ITicketChangeListener methods
    def ticket_created(self, ticket):
        pass

    def ticket_changed(self, ticket, comment, author, old_values):
        if (
            self._closed_as_duplicate(ticket) and
            self.rls.duplicate_relation_type
        ):
            try:
                self.rls.add(ticket, ticket.duplicate,
                             self.rls.duplicate_relation_type,
                             comment, author)
            except TracError:
                pass

    def _closed_as_duplicate(self, ticket):
        return (ticket['status'] == 'closed' and
                ticket['resolution'] == 'duplicate')

    def ticket_deleted(self, ticket):
        self.rls.delete_resource_relations(ticket)

    #ITicketManipulator methods
    def prepare_ticket(self, req, ticket, fields, actions):
        pass

    def validate_ticket(self, req, ticket):
        return itertools.chain(
            self._check_blockers(req, ticket),
            self._check_open_children(req, ticket),
            self._check_duplicate_id(req, ticket),
        )

    def _check_blockers(self, req, ticket):
        if req.args.get('action') == 'resolve':
            blockers = self.rls.find_blockers(ticket, self.is_blocker)
            if blockers:
                blockers_str = ', '.join(
                    get_resource_shortname(self.env, blocker_ticket.resource)
                    for blocker_ticket in unique(blockers))
                msg = ("Cannot resolve this ticket because it is "
                       "blocked by tickets [%s]"
                       % blockers_str)
                yield None, msg

    def _check_open_children(self, req, ticket):
        if req.args.get('action') == 'resolve':
            for relation in [r for r in self.rls.get_relations(ticket)
                             if r['type'] == self.rls.CHILDREN_RELATION_TYPE]:
                ticket = self._create_ticket_by_full_id(relation['destination'])
                if ticket['status'] != 'closed':
                    msg = ("Cannot resolve this ticket because it has open"
                           "child tickets.")
                    yield None, msg

    def _check_duplicate_id(self, req, ticket):
        if req.args.get('action') == 'resolve':
            resolution = req.args.get('action_resolve_resolve_resolution')
            if resolution == 'duplicate':
                duplicate_id = req.args.get('duplicate_id')
                if not duplicate_id:
                    yield None, "Duplicate ticket ID must be provided."

                try:
                    duplicate_ticket = self.find_ticket(duplicate_id)
                    req.perm.require('TICKET_MODIFY',
                                     Resource(duplicate_ticket.id))
                    ticket.duplicate = duplicate_ticket
                except NoSuchTicketError:
                    yield None, "Invalid duplicate ticket ID."

    def find_ticket(self, ticket_spec):
        ticket = None
        m = re.match(r'#?(?P<tid>\d+)', ticket_spec)
        if m:
            tid = m.group('tid')
            try:
                ticket = Ticket(self.env, tid)
            except ResourceNotFound:
                # ticket not found in current product, try all other products
                for p in Product.select(self.env):
                    if p.prefix != self.env.product.prefix:
                        # TODO: check for PRODUCT_VIEW permissions
                        penv = ProductEnvironment(self.env.parent, p.prefix)
                        try:
                            ticket = Ticket(penv, tid)
                        except ResourceNotFound:
                            pass
                        else:
                            break

        # ticket still not found, use fallback for <prefix>:ticket:<id> syntax
        if ticket is None:
            try:
                resource = ResourceIdSerializer.get_resource_by_id(ticket_spec)
                ticket = self._create_ticket_by_full_id(resource)
            except:
                raise NoSuchTicketError
        return ticket

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

        related_resource_name = relation_system.get_resource_name(
            relation.destination)
        if is_delete:
            old_value = related_resource_name
            new_value = None
        else:
            old_value = None
            new_value = related_resource_name
        description = 'Relation "%s"' % (
            relation_system.render_relation_type(relation.type),)

        db("""INSERT INTO ticket_change
            (ticket, time, author, field, oldvalue, newvalue, product)
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
           (ticket_id,
            when_ts,
            relation.author,
            description,
            old_value,
            new_value,
            product))


class UnknownRelationType(ValueError):
    pass


class NoSuchTicketError(ValueError):
    pass
