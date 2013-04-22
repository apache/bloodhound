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

from whoosh.collectors import (
    FacetCollector, FilterCollector, WrappingCollector, itervalues)

# Collectors in whoosh 2.4.1 are broken. The following functions are
# monkeypatches based on the current whoosh trunk, that fix the problems with
# Filter and Facets Collectors not playing along.


def fix_wrapping_collector():
    """When filter and facets collector are used together, filter collector
    tries to access child.offset, which is not set in 2.4.1. The following
    function is taken from the trunk version of whoosh.
    """
    def WrappingCollector_set_subsearcher(self, subsearcher, offset):
        self.child.set_subsearcher(subsearcher, offset)
        self.subsearcher = subsearcher
        self.matcher = self.child.matcher
        self.offset = self.child.offset
    WrappingCollector.set_subsearcher = WrappingCollector_set_subsearcher


def fix_facets_collector():
    """When filter and facets collector are used together, filter collector
    tries to access child.offset, which is not set in 2.4.1. The following
    function is taken from the trunk version of whoosh.
    """
    def FacetsCollector_set_subsearcher(self, subsearcher, offset):
        WrappingCollector.set_subsearcher(self, subsearcher, offset)

        # Tell each categorizer about the new subsearcher and offset
        for categorizer in itervalues(self.categorizers):
            categorizer.set_searcher(self.child.subsearcher, self.child.offset)
    FacetCollector.set_subsearcher = FacetsCollector_set_subsearcher


def fix_filter_collector():
    """FilterCollector ignores filters that match no documents.
    The following function includes a patch submitted to whoosh in
    pull request #41.
    """

    def FilterCollector_collect_matches(self):
        # pylint: disable=protected-access,attribute-defined-outside-init
        child = self.child
        _allow = self._allow
        _restrict = self._restrict

        if _allow is not None or _restrict is not None:
            filtered_count = self.filtered_count
            for sub_docnum in child.matches():
                global_docnum = self.offset + sub_docnum
                if ((_allow is not None and global_docnum not in _allow)
                    or (_restrict is not None and global_docnum in _restrict)):
                    filtered_count += 1
                    continue
                child.collect(sub_docnum)
            self.filtered_count = filtered_count
        else:
            # If there was no allow or restrict set, don't do anything special,
            # just forward the call to the child collector
            child.collect_matches()
    FilterCollector.collect_matches = FilterCollector_collect_matches


def fixes_for(whoosh_version):
    if (2, 4, 0) <= whoosh_version <= (2, 4, 1):
        return (
            fix_wrapping_collector,
            fix_facets_collector,
            fix_filter_collector,
        )
