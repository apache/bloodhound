
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
from trac.perm import IPermissionPolicy, PermissionSystem

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
            if action == 'TRAC_ADMIN':
                # Always lookup TRAC_ADMIN permission in global scope
                permsys = PermissionSystem(self.env.parent)
                return bool(permsys.check_permission(action, username, 
                                                resource, perm))
            elif username == self.env.product.owner:
                # Product owner granted with PRODUCT_ADMIN permission ootb
                permsys = PermissionSystem(self.env)
                # FIXME: would `action != 'TRAC_ADMIN'` be enough ?
                return True if action in permsys.get_actions() and \
                                action != 'TRAC_ADMIN' \
                            else None
