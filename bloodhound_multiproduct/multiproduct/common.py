
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

import re

from multiproduct.model import Product

PRODUCT_RE = re.compile(r'^/(?P<pid>[^/]*)(?P<pathinfo>.*)')

def match_product_path(env, req):
    """Matches a product in pathinfo, stores the associated product id and
    returns what is left"""
    pathinfo = req.path_info[:]
    match = PRODUCT_RE.match(pathinfo)
    if match:
        pid = match.group('pid')
        products = Product.select(env, where={'prefix':pid})
        if len(products) == 1:
            req.args['productid'] = match.group('pid')
            req.args['product'] = products[0].name
            pathinfo = match.group('pathinfo')
    return pathinfo
