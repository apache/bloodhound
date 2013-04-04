from functools import wraps

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

"""Permission components for Bloodhound product environments"""

__all__ = 'ProductPermissionPolicy',

from trac.core import Component, implements
from trac.perm import IPermissionPolicy, PermissionSystem, PermissionError

#--------------------------
# Permission components
#--------------------------

class MultiproductPermissionPolicy(Component):
    """Apply product policy in product environments to deal with TRAC_ADMIN,
    PRODUCT_ADMIN and alike.
    """
    implements(IPermissionPolicy)

    # IPermissionPolicy methods
    def check_permission(self, action, username, resource, perm):
        # FIXME: Better handling of recursive imports
        from multiproduct.env import ProductEnvironment

        if isinstance(self.env, ProductEnvironment):
            permsys = PermissionSystem(self.env.parent)
            if permsys.check_permission('TRAC_ADMIN', username):
                return action in PermissionSystem(self.env).get_actions() \
                        or None     # FIXME: maybe False is better
            elif username == self.env.product.owner:
                # Product owner granted with PRODUCT_ADMIN permission ootb
                permsys = PermissionSystem(self.env)
                # FIXME: would `action != 'TRAC_ADMIN'` be enough ?
                return True if action in permsys.get_actions() and \
                                action != 'TRAC_ADMIN' \
                            else None


#--------------------------
# Impersonation helpers
#--------------------------

class SudoPermissionContext(object):
    """Allows a permitted user (by default `PRODUCT_ADMIN`) to execute
    a command as if temporarily granted with `TRAC_ADMIN` or other specific
    permission. There is also support to revoke some actions unconditionally.
    
    These objects will act as context managers wrapping the permissions cache
    of the target request object. Entering the same context more than once
    is not supported and will result in unexpected behavior.
    """
    def __init__(self, req, require=None, grant=None, revoke=None):
        grant = frozenset(grant if grant is not None else ('TRAC_ADMIN',))
        revoke = frozenset(revoke or [])
        if grant & revoke:
            raise ValueError('Impossible to grant and revoke (%s)' %
                             ', '.join(sorted(grant & revoke)))

        self.grant = grant
        self.revoke = revoke
        if req:
            self._expand_perms(req.perm.env)
        else:
            self._expanded = False
        self._perm = None
        self.req = req
        self.require_actions = frozenset(('PRODUCT_ADMIN',) if require is None 
                                         else ([require] 
                                               if isinstance(require, basestring)
                                               else require))

    @property
    def perm(self):
        return self._perm

    @perm.setter
    def perm(self, perm):
        if perm and not self._expanded:
            self._expand_perms(perm.env)
        self._perm = perm

    def __getattr__(self, attrnm):
        # Actually PermissionCache.__slots__ but this will be faster
        if attrnm in ('env', 'username', '_resource', '_cache'):
            try:
                return getattr(self.perm, attrnm)
            except AttributeError:
                pass
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, attrnm))

    def __enter__(self):
        if self.req is None:
            # e.g. instances returned by __call__
            raise ValueError('Context manager not bound to request object')
        req = self.req
        for action in self.require_actions:
            req.perm.require(action)
        self.perm = req.perm
        req.perm = self
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.req.perm = self.perm
        self.perm = None

    # Internal methods

    @property
    def is_active(self):
        """Determine whether this context is active
        """
        return self.req and self.perm

    def _expand_perms(self, env):
        permsys = PermissionSystem(env)
        grant = frozenset(permsys.expand_actions(self.grant))
        revoke = frozenset(permsys.expand_actions(self.revoke))
        # Double check ambiguous action lists
        if grant & revoke:
            raise ValueError('Impossible to grant and revoke (%s)' %
                             ', '.join(sorted(grant & revoke)))
        self.grant = grant
        self.revoke = revoke
        self._expanded = True

    def __assert_require(f):
        @wraps(f)
        def __require(self, *args, **kwargs):
            # FIXME : No check ? Transform into assert statement ?
            if not self.perm:
                raise RuntimeError('Permission check out of context')
            if not self.is_active:
                for action in self.require_actions:
                    self.perm.require(action)
            return f(self, *args, **kwargs)

        return __require

    # PermissionCache methods
    @__assert_require
    def __call__(self, realm_or_resource, id=False, version=False):
        newperm = self.perm(realm_or_resource, id, version)
        if newperm is self.perm:
            return self
        else:
            newctx = SudoPermissionContext(None, self.require_actions, self.grant,
                                           self.revoke)
            newctx.perm = newperm
            return newctx

    @__assert_require
    def has_permission(self, action, realm_or_resource=None, id=False,
                       version=False):
        return action in self.grant or \
               (action not in self.revoke and 
                self.perm.has_permission(action, realm_or_resource, id, 
                                         version))

    __contains__ = has_permission

    @__assert_require
    def require(self, action, realm_or_resource=None, id=False, version=False):
        if action in self.grant:
            return
        if action in self.revoke:
            resource = self._normalize_resource(realm_or_resource, id, version)
            raise PermissionError(action, resource, self.perm.env)
        self.perm.require(action, realm_or_resource, id, version)

    assert_permission = require

    @__assert_require
    def permissions(self):
        """Deprecated (but still used by the HDF compatibility layer)
        """
        self.perm.env.log.warning("perm.permissions() is deprecated and "
                             "is only present for HDF compatibility")
        permsys = PermissionSystem(self.perm.env)
        actions = permsys.get_user_permissions(self.perm.username)
        return [action for action in actions if action in self]

    del __assert_require


sudo = SudoPermissionContext
