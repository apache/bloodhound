# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2009 Edgewall Software
# Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
# Copyright (C) 2007 Christian Boos <cboos@edgewall.org>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.
#
# Author: Christian Boos <cboos@edgewall.org>
#         Alec Thomas <alec@swapoff.org>

from trac.core import *
from trac.util.translation import _


class ResourceNotFound(TracError):
    """Thrown when a non-existent resource is requested"""


class IResourceManager(Interface):

    def get_resource_realms():
        """Return resource realms managed by the component.

        :rtype: `basestring` generator
        """

    def get_resource_url(resource, href, **kwargs):
        """Return the canonical URL for displaying the given resource.

        :param resource: a `Resource`
        :param href: an `Href` used for creating the URL

        Note that if there's no special rule associated to this realm for
        creating URLs (i.e. the standard convention of using realm/id applies),
        then it's OK to not define this method.
        """

    def get_resource_description(resource, format='default', context=None,
                                 **kwargs):
        """Return a string representation of the resource, according to the
        `format`.

        :param resource: the `Resource` to describe
        :param format: the kind of description wanted. Typical formats are:
                       `'default'`, `'compact'` or `'summary'`.
        :param context: an optional rendering context to allow rendering rich
                        output (like markup containing links)
        :type context: `ResourceContext`

        Additional keyword arguments can be given as extra information for
        some formats.

        For example, the ticket with the id 123 is represented as:
         - `'#123'` in `'compact'` format,
         - `'Ticket #123'` for the `default` format.
         - `'Ticket #123 (closed defect): This is the summary'` for the
           `'summary'` format

        Note that it is also OK to not define this method if there's no
        special way to represent the resource, in which case the standard
        representations 'realm:id' (in compact mode) or 'Realm id' (in
        default mode) will be used.
        """

    def resource_exists(resource):
        """Check whether the given `resource` exists physically.

        :rtype: bool

        Attempting to retrieve the model object for a non-existing
        resource should raise a `ResourceNotFound` exception.
        (''since 0.11.8'')
        """


class IExternalResourceConnector(Interface):

    def get_supported_neighborhoods():
        """Return supported manager neighborhoods.

        :rtype: `basestring` generator
        """

    def load_manager(neighborhood):
        """Load the component manager identified by a given neighborhood.

        :param neighborhood: manager identifier (i.e. `Neighborhood`)
        :rtype: `trac.core.ComponentManager`
        """

    def manager_exists(neighborhood):
        """Check whether the component manager identified by 
        the given `neighborhood` exists physically.

        :param neighborhood: manager identifier (i.e. `Neighborhood`)
        :rtype: bool

        Attempting to retrieve the manager object for a non-existing
        neighborhood should raise a `ResourceNotFound` exception.
        """


class Neighborhood(object):
    """Neighborhoods are the topmost level in the resources hierarchy. 
    They represent resources managed by a component manager, thereby
    identifying the later. As such, resource neighborhoods serve to
    the purpose of specifying absolute references to resources hosted beyond
    the boundaries of a given component manager. As a side effect they are
    the key used to load component managers at run time.
    """

    __slots__ = ('_realm', '_id')

    @property
    def is_null(self):
        return (self._realm, self._id) == (None, None)

    def __repr__(self):
        if self.is_null:
            return '<Neighborhood (null)>'
        else:
            return '<Neighborhood %s:%s>' % (self._realm, self._id)

    def __eq__(self, other):
        return isinstance(other, Neighborhood) and \
               self._realm == other._realm and \
               self._id == other._id

    def __hash__(self):
        """Hash this resource descriptor, including its hierarchy."""
        return hash((self._realm, self._id))

    @property
    def id(self):
        return None

    @id.setter
    def id(self, value):
        pass

    realm = parent = neighborhood = version = id

    # -- methods for creating other Resource identifiers

    def __new__(cls, neighborhood_or_realm=None, id=False):
        """Create a new Neighborhood object from a specification.

        :param neighborhood_or_realm: this can be either:
           - a `Neighborhood`, which is then used as a base for making a copy
           - a `basestring`, used to specify a `realm`
        :param id: the neighborhood identifier
        :param version: the version or `None` for indicating the latest version

        >>> main = Neighborhood('nbh', 'id')
        >>> repr(main)
        '<Neighborhood nbh:id>'

        >>> Neighborhood(main) is main
        True

        >>> repr(Neighborhood(None))
        '<Neighborhood (null)>'
        """
        realm = neighborhood_or_realm
        if isinstance(neighborhood_or_realm, Neighborhood):
            if id is False:
                return neighborhood_or_realm
            else: # copy and override
                realm = neighborhood_or_realm._realm
        elif id is False:
            id = None
        neighborhood = super(Neighborhood, cls).__new__(cls)
        neighborhood._realm = realm
        neighborhood._id = id
        return neighborhood

    def __call__(self, realm=False, id=False, version=False, parent=False):
        """Create a new Resource using the current resource as a template.

        Optional keyword arguments can be given to override `id` and
        `version`.

        >>> nbh = Neighborhood('nbh', 'id')
        >>> repr(nbh)
        '<Neighborhood nbh:id>'

        >>> main = nbh('wiki', 'WikiStart')
        >>> repr(main)
        "<Resource u'wiki:WikiStart' in Neighborhood nbh:id>"

        >>> Resource(main) is main
        True

        >>> main3 = Resource(main, version=3)
        >>> repr(main3)
        "<Resource u'wiki:WikiStart@3' in Neighborhood nbh:id>"

        >>> main0 = main3(version=0)
        >>> repr(main0)
        "<Resource u'wiki:WikiStart@0' in Neighborhood nbh:id>"

        In a copy, if `id` is overriden, then the original `version` value
        will not be reused.

        >>> repr(Resource(main3, id="WikiEnd"))
        "<Resource u'wiki:WikiEnd' in Neighborhood nbh:id>"

        >>> repr(nbh(None))
        '<Neighborhood nbh:id>'

        Null neighborhood will be used to put absolute resource
        references ban into relative form (i.e. `resource.neiighborhood = None`)

        >>> nullnbh = Neighborhood(None, None)
        >>> repr(nullnbh)
        '<Neighborhood (null)>'

        >>> repr(nullnbh(main))
        "<Resource u'wiki:WikiStart'>"
        >>> repr(nullnbh(main3))
        "<Resource u'wiki:WikiStart@3'>"
        >>> repr(nullnbh(main0))
        "<Resource u'wiki:WikiStart@0'>"
        """
        if (realm, id, version, parent) in ((False, False, False, False),
                                            (None, False, False, False)):
            return self
        else:
            resource = Resource(realm, id, version, parent)
            if resource.neighborhood is not self:
                resource = self._update_parents(resource)
            return resource

    def _update_parents(self, resource):
        if self.is_null and resource.neighborhood is None:
            return resource
        newresource = Resource(resource.realm, resource.id, resource.version, self)
        current = newresource
        parent = resource.parent
        while parent is not None:
            current.parent = Resource(parent.realm, parent.id, parent.version, self)
            current = current.parent
            parent = parent.parent
        return newresource

    # -- methods for retrieving children Resource identifiers

    def child(self, realm, id=False, version=False):
        """Retrieve a child resource for a secondary `realm`.

        Same as `__call__`, except that this one sets the parent to `self`.

        >>> repr(Neighborhood('realm', 'id').child('attachment', 'file.txt'))
        "<Resource u'attachment:file.txt' in Neighborhood realm:id>"
        """
        return self(realm, id, version)


class Resource(object):
    """Resource identifier.

    This specifies as precisely as possible *which* resource from a Trac
    environment is manipulated.

    A resource is identified by:
    (- a `project` identifier) 0.12?
     - a `realm` (a string like `'wiki'` or `'ticket'`)
     - an `id`, which uniquely identifies a resource within its realm.
       If the `id` information is not set, then the resource represents
       the realm as a whole.
     - an optional `version` information.
       If `version` is `None`, this refers by convention to the latest
       version of the resource.

    Some generic and commonly used rendering methods are associated as well
    to the Resource object. Those properties and methods actually delegate
    the real work to the Resource's manager.
    """

    __slots__ = ('realm', 'id', 'version', 'parent', 'neighborhood')

    def __repr__(self):
        path = []
        r = self
        while r:
            name = r.realm
            if r.id:
                name += ':' + unicode(r.id) # id can be numerical
            if r.version is not None:
                name += '@' + unicode(r.version)
            path.append(name or '')
            r = r.parent
        path = reversed(path)
        if self.neighborhood is None:
            return '<Resource %r>' % (', '.join(path))
        else:
            return '<Resource %r in Neighborhood %s:%s>' % (', '.join(path), 
                                                    self.neighborhood._realm,
                                                    self.neighborhood._id)

    def __eq__(self, other):
        return isinstance(other, Resource) and \
               self.realm == other.realm and \
               self.id == other.id and \
               self.version == other.version and \
               self.parent == other.parent and \
               self.neighborhood == other.neighborhood

    def __hash__(self):
        """Hash this resource descriptor, including its hierarchy."""
        path = ()
        current = self
        while current:
            path += (self.realm, self.id, self.version)
            current = current.parent
        if self.neighborhood is not None:
            # FIXME: Collisions !!!
            path = (self.neighborhood._realm, self.neighborhood._id) + path
        else:
            path = (None, None) + path
        return hash(path)

    # -- methods for creating other Resource identifiers

    def __new__(cls, resource_or_realm=None, id=False, version=False,
                parent=False):
        """Create a new Resource object from a specification.

        :param resource_or_realm: this can be either:
           - a `Resource`, which is then used as a base for making a copy
           - a `basestring`, used to specify a `realm`
        :param id: the resource identifier
        :param version: the version or `None` for indicating the latest version

        >>> main = Resource('wiki', 'WikiStart')
        >>> repr(main)
        "<Resource u'wiki:WikiStart'>"

        >>> Resource(main) is main
        True

        >>> main3 = Resource(main, version=3)
        >>> repr(main3)
        "<Resource u'wiki:WikiStart@3'>"

        >>> main0 = main3(version=0)
        >>> repr(main0)
        "<Resource u'wiki:WikiStart@0'>"

        In a copy, if `id` is overriden, then the original `version` value
        will not be reused.

        >>> repr(Resource(main3, id="WikiEnd"))
        "<Resource u'wiki:WikiEnd'>"

        >>> repr(Resource(None))
        "<Resource ''>"
        """
        realm = resource_or_realm
        if isinstance(parent, Neighborhood):
            neighborhood = parent
            parent = False
        else:
            neighborhood = None
        if isinstance(resource_or_realm, Resource):
            if id is False and version is False and parent is False:
                return resource_or_realm
            else: # copy and override
                realm = resource_or_realm.realm
            if id is False:
                id = resource_or_realm.id
            if version is False:
                if id == resource_or_realm.id:
                    version = resource_or_realm.version # could be 0...
                else:
                    version = None
            if parent is False:
                parent = resource_or_realm.parent
            neighborhood = neighborhood or resource_or_realm.neighborhood
        else:
            if id is False:
                id = None
            if version is False:
                version = None
            if parent is False:
                parent = None
            neighborhood = neighborhood or getattr(parent, 'neighborhood', None)
        resource = super(Resource, cls).__new__(cls)
        resource.realm = realm
        resource.id = id
        resource.version = version
        resource.parent = parent
        if neighborhood and neighborhood.is_null:
            neighborhood = None
        resource.neighborhood = neighborhood
        return resource

    def __call__(self, realm=False, id=False, version=False, parent=False):
        """Create a new Resource using the current resource as a template.

        Optional keyword arguments can be given to override `id` and
        `version`.
        """
        return Resource(self if realm is False else realm, id, version, parent)

    # -- methods for retrieving children Resource identifiers

    def child(self, realm, id=False, version=False):
        """Retrieve a child resource for a secondary `realm`.

        Same as `__call__`, except that this one sets the parent to `self`.

        >>> repr(Resource(None).child('attachment', 'file.txt'))
        "<Resource u', attachment:file.txt'>"
        """
        return Resource(realm, id, version, self)

class IResourceChangeListener(Interface):
    """Extension point interface for components that require notification
    when resources are created, modified, or deleted.

    'resource' parameters is instance of the a resource e.g. ticket, milestone
    etc.
    'context' is an action context, may contain author, comment etc. Context
    content depends on a resource type.
    """

    def match_resource(resource):
        """Return whether the listener wants to process the given resource."""

    def resource_created(resource, context):
        """
        Called when a resource is created.
        """

    def resource_changed(resource, old_values, context):
        """Called when a resource is modified.

        `old_values` is a dictionary containing the previous values of the
        resource properties that changed. Properties are specific for resource
        type.
        """

    def resource_deleted(resource, context):
        """Called when a resource is deleted."""

    def resource_version_deleted(resource, context):
        """Called when a version of a resource has been deleted."""


class ResourceSystem(Component):
    """Resource identification and description manager.

    This component makes the link between `Resource` identifiers and their
    corresponding manager `Component`.
    """

    resource_connectors = ExtensionPoint(IExternalResourceConnector)
    resource_managers = ExtensionPoint(IResourceManager)
    change_listeners = ExtensionPoint(IResourceChangeListener)


    def __init__(self):
        self._resource_managers_map = None
        self._resource_connector_map = None

    # Public methods

    def get_resource_manager(self, realm):
        """Return the component responsible for resources in the given `realm`

        :param realm: the realm name
        :return: a `Component` implementing `IResourceManager` or `None`
        """
        # build a dict of realm keys to IResourceManager implementations
        if not self._resource_managers_map:
            map = {}
            for manager in self.resource_managers:
                for manager_realm in manager.get_resource_realms() or []:
                    map[manager_realm] = manager
            self._resource_managers_map = map
        return self._resource_managers_map.get(realm)

    def get_known_realms(self):
        """Return a list of all the realm names of resource managers."""
        realms = []
        for manager in self.resource_managers:
            for realm in manager.get_resource_realms() or []:
                realms.append(realm)
        return realms

    def get_resource_connector(self, realm):
        """Return the component responsible for loading component managers
         given the neighborhood `realm`

        :param realm: the realm name
        :return: a `ComponentManager` implementing `IExternalResourceConnector`
                 or `None`
        """
        # build a dict of neighborhood realm keys to target implementations
        if not self._resource_connector_map:
            map = {}
            for connector in self.resource_connectors:
                for conn_realm in connector.get_supported_neighborhoods() or []:
                    map[conn_realm] = connector
            self._resource_connector_map = map
        return self._resource_connector_map.get(realm)

    def get_known_neighborhoods(self):
        """Return a list of all the realm names of neighborhoods."""
        realms = []
        for connector in self.resource_connectors:
            for realm in manager.get_supported_neighborhoods() or []:
                realms.append(realm)
        return realms

    def load_component_manager(self, neighborhood, default=None):
        """Load the component manager identified by a given instance of
        `Neighborhood` class.

        :throws ResourceNotFound: if there is no connector for neighborhood
        """
        if neighborhood is None or neighborhood._realm is None:
            if default is not None:
                return default
            else:
                raise ResourceNotFound('Unexpected neighborhood %s' % 
                                       (neighborhood,))
        c = self.get_resource_connector(neighborhood._realm)
        if c is None:
            raise ResourceNotFound('Missing connector for neighborhood %s' % 
                                   (neighborhood,))
        return c.load_manager(neighborhood)

    def neighborhood_prefix(self, neighborhood):
        return '' if neighborhood is None \
                  else '[%s:%s] ' % (neighborhood._realm,
                                     neighborhood._id or '') 

    # -- Utilities to trigger resources event notifications

    def resource_created(self, resource, context=None):
        for listener in self.change_listeners:
            if listener.match_resource(resource):
                listener.resource_created(resource, context)

    def resource_changed(self, resource, old_values, context=None):
        for listener in self.change_listeners:
            if listener.match_resource(resource):
                listener.resource_changed(resource, old_values, context)

    def resource_deleted(self, resource, context=None):
        for listener in self.change_listeners:
            if listener.match_resource(resource):
                listener.resource_deleted(resource, context)

    def resource_version_deleted(self, resource, context=None):
        for listener in self.change_listeners:
            if listener.match_resource(resource):
                listener.resource_version_deleted(resource, context)


def manager_for_neighborhood(compmgr, neighborhood):
    """Instantiate a given component manager identified by
    target neighborhood.
    
    :param compmgr: Source component manager.
    :param neighborhood: Target neighborhood
    :throws ResourceNotFound: if there is no connector for neighborhood
    """
    rsys = ResourceSystem(compmgr)
    return rsys.load_component_manager(neighborhood, compmgr)


# -- Utilities for manipulating resources in a generic way

def get_resource_url(env, resource, href, **kwargs):
    """Retrieve the canonical URL for the given resource.

    This function delegates the work to the resource manager for that
    resource if it implements a `get_resource_url` method, otherwise
    reverts to simple '/realm/identifier' style URLs.

    :param env: the `Environment` where `IResourceManager` components live
    :param resource: the `Resource` object specifying the Trac resource
    :param href: an `Href` object used for building the URL

    Additional keyword arguments are translated as query parameters in the URL.

    >>> from trac.test import EnvironmentStub
    >>> from trac.web.href import Href
    >>> env = EnvironmentStub()
    >>> href = Href('/trac.cgi')
    >>> main = Resource('generic', 'Main')
    >>> get_resource_url(env, main, href)
    '/trac.cgi/generic/Main'

    >>> get_resource_url(env, main(version=3), href)
    '/trac.cgi/generic/Main?version=3'

    >>> get_resource_url(env, main(version=3), href)
    '/trac.cgi/generic/Main?version=3'

    >>> get_resource_url(env, main(version=3), href, action='diff')
    '/trac.cgi/generic/Main?action=diff&version=3'

    >>> get_resource_url(env, main(version=3), href, action='diff', version=5)
    '/trac.cgi/generic/Main?action=diff&version=5'

    """
    try:
        rsys = ResourceSystem(manager_for_neighborhood(env,
                                                       resource.neighborhood))
    except ResourceNotFound:
        pass
    else:
        if rsys.env is not env:
            # Use absolute href for external resources
            href = rsys.env.abs_href
        manager = rsys.get_resource_manager(resource.realm)
        if manager and hasattr(manager, 'get_resource_url'):
            return manager.get_resource_url(resource, href, **kwargs)
    args = {'version': resource.version}
    args.update(kwargs)
    return href(resource.realm, resource.id, **args)

def get_resource_description(env, resource, format='default', **kwargs):
    """Retrieve a standardized description for the given resource.

    This function delegates the work to the resource manager for that
    resource if it implements a `get_resource_description` method,
    otherwise reverts to simple presentation of the realm and identifier
    information.

    :param env: the `Environment` where `IResourceManager` components live
    :param resource: the `Resource` object specifying the Trac resource
    :param format: which formats to use for the description

    Additional keyword arguments can be provided and will be propagated
    to resource manager that might make use of them (typically, a `context`
    parameter for creating context dependent output).

    >>> from trac.test import EnvironmentStub
    >>> env = EnvironmentStub()
    >>> main = Resource('generic', 'Main')
    >>> get_resource_description(env, main)
    u'generic:Main'

    >>> get_resource_description(env, main(version=3))
    u'generic:Main'

    >>> get_resource_description(env, main(version=3), format='summary')
    u'generic:Main at version 3'

    """
    try:
        rsys = ResourceSystem(manager_for_neighborhood(env,
                                                       resource.neighborhood))
    except ResourceNotFound:
        pass
    else:
        manager = rsys.get_resource_manager(resource.realm)
        if manager and hasattr(manager, 'get_resource_description'):
            return manager.get_resource_description(resource, format, **kwargs)
    nbhprefix = rsys.neighborhood_prefix(resource.neighborhood) 

    name = u'%s%s:%s' % (nbhprefix, resource.realm, resource.id)
    if format == 'summary':
        name = _('%(name)s at version %(version)s',
                 name=name, version=resource.version)
    return name

def get_resource_name(env, resource):
    return get_resource_description(env, resource)

def get_resource_shortname(env, resource):
    return get_resource_description(env, resource, 'compact')

def get_resource_summary(env, resource):
    return get_resource_description(env, resource, 'summary')

def get_relative_resource(resource, path=''):
    """Build a Resource relative to a reference resource.

    :param path: path leading to another resource within the same realm.
    """
    if path in (None, '', '.'):
        return resource
    else:
        base = unicode(resource.id if path[0] != '/' else '').split('/')
        for comp in path.split('/'):
            if comp == '..':
                if base:
                    base.pop()
            elif comp and comp != '.':
                base.append(comp)
        return resource(id='/'.join(base) if base else None)

def get_relative_url(env, resource, href, path='', **kwargs):
    """Build an URL relative to a resource given as reference.

    :param path: path leading to another resource within the same realm.

    >>> from trac.test import EnvironmentStub
    >>> env = EnvironmentStub()
    >>> from trac.web.href import Href
    >>> href = Href('/trac.cgi')
    >>> main = Resource('wiki', 'Main', version=3)

    Without parameters, return the canonical URL for the resource, like
    `get_resource_url` does.

    >>> get_relative_url(env, main, href)
    '/trac.cgi/wiki/Main?version=3'

    Paths are relative to the given resource:

    >>> get_relative_url(env, main, href, '.')
    '/trac.cgi/wiki/Main?version=3'

    >>> get_relative_url(env, main, href, './Sub')
    '/trac.cgi/wiki/Main/Sub'

    >>> get_relative_url(env, main, href, './Sub/Infra')
    '/trac.cgi/wiki/Main/Sub/Infra'

    >>> get_relative_url(env, main, href, './Sub/')
    '/trac.cgi/wiki/Main/Sub'

    >>> mainsub = main(id='Main/Sub')
    >>> get_relative_url(env, mainsub, href, '..')
    '/trac.cgi/wiki/Main'

    >>> get_relative_url(env, main, href, '../Other')
    '/trac.cgi/wiki/Other'

    References always stay within the current resource realm:

    >>> get_relative_url(env, mainsub, href, '../..')
    '/trac.cgi/wiki'

    >>> get_relative_url(env, mainsub, href, '../../..')
    '/trac.cgi/wiki'

    >>> get_relative_url(env, mainsub, href, '/toplevel')
    '/trac.cgi/wiki/toplevel'

    Extra keyword arguments are forwarded as query parameters:

    >>> get_relative_url(env, main, href, action='diff')
    '/trac.cgi/wiki/Main?action=diff&version=3'

    """
    return get_resource_url(env, get_relative_resource(resource, path),
                            href, **kwargs)

def render_resource_link(env, context, resource, format='default'):
    """Utility for generating a link `Element` to the given resource.

    Some component manager may directly use an extra `context` parameter
    in order to directly generate rich content. Otherwise, the textual output
    is wrapped in a link to the resource.
    """
    from genshi.builder import Element, tag
    link = get_resource_description(env, resource, format, context=context)
    if not isinstance(link, Element):
        link = tag.a(link, href=get_resource_url(env, resource, context.href))
    return link

def resource_exists(env, resource):
    """Checks for resource existence without actually instantiating a model.

        :return: `True` if the resource exists, `False` if it doesn't
        and `None` in case no conclusion could be made (i.e. when
        `IResourceManager.resource_exists` is not implemented).

        >>> from trac.test import EnvironmentStub
        >>> env = EnvironmentStub()

        >>> resource_exists(env, Resource('dummy-realm', 'dummy-id')) is None
        True
        >>> resource_exists(env, Resource('dummy-realm'))
        False
    """
    try:
        rsys = ResourceSystem(manager_for_neighborhood(env,
                                                       resource.neighborhood))
    except ResourceNotFound:
        return False
    manager = ResourceSystem(env).get_resource_manager(resource.realm)
    if manager and hasattr(manager, 'resource_exists'):
        return manager.resource_exists(resource)
    elif resource.id is None:
        return False
