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

"""
Module providing a feature to generate a schema.xml file containing
the definition of a Solr schema that can be used for Bloodhound.
"""

import os

from lxml import etree

from trac.core import Component, implements, TracError
from bhsearch.whoosh_backend import WhooshBackend
from bhsolr.solr_backend import SolrBackend

class SolrSchema(Component):

    """Class for creating a schema.xml file.

    Define the fields to be written to the schema.xml file, and write
    it at a specified path.

    Class Attributes:
    REQUIRED_FIELDS -- the fields required for each searchable object
    FIELDS_TYPE_DICT -- the types each field can have, along with its
    equivalent name to be used in the Solr schema.xml file

    Instance Attributes:
    path -- the path to where tha schema should be saved
    schema -- the schema definition from bhsearch.WhooshBackend
    schema_element -- the main etree.Element for the schema.xml file
    fields_element -- the etree.SubElement for defining the fields
    unique_key_element -- the etree.SubElement for defining the unique
    key
    """

    REQUIRED_FIELDS = {
            "id": True,
            "unique_id": True,
            "type": True
            }
    FIELDS_TYPE_DICT = {
        "ID": "string",
        "DATETIME": "date",
        "KEYWORD": "string",
        "TEXT": "text_general"
        }

    def __init__(self):
        """Initialise main XML elements and set their values."""
        self.path = None

        # The main parent elements.
        self.schema = WhooshBackend.SCHEMA

        self.schema_element = etree.Element("schema")
        self.schema_element.set("name", "Bloodhound Solr Schema")
        self.schema_element.set("version", "1")

        self.fields_element = etree.SubElement(self.schema_element, "fields")

        self.unique_key_element = etree.SubElement(self.schema_element,
                                                   "uniqueKey")
        self.unique_key_element.text = SolrBackend.UNIQUE_ID

        # Children of the element containing the definitions of fields;
        # these are required so that Solr is able to validate the
        # schema.
        version_field = etree.SubElement(self.fields_element, "field")
        version_field.set("name", "_version_")
        version_field.set("type", "long")
        version_field.set("indexed", "true")
        version_field.set("stored", "true")
        version_field.set("multiValued", "false")

        root_field = etree.SubElement(self.fields_element, "field")
        root_field.set("name", "_root_")
        root_field.set("type", "string")
        root_field.set("indexed", "true")
        root_field.set("stored", "false")

        stored_name = etree.SubElement(self.fields_element, "field")
        stored_name.set("name", "_stored_name")
        stored_name.set("type", "string")
        stored_name.set("indexed", "true")
        stored_name.set("stored", "true")
        stored_name.set("required", "false")
        stored_name.set("multiValued", "false")

    def generate_schema(self, path=None):
        """Write a schema.xml file.

        Create all XML elements needed in the schema.xml file, along
        with their values and write the file.

        Keyword Arguments:
        path -- the path to where the schema.xml file should be saved
        (default None)
        """

        # If the user hasn't provided a path to where the schema.xml
        # file should be saved, then the schema.xml file will be saved
        # in the current directory.
        if not path:
          path = os.getcwd()
        self.path = os.path.join(path, 'schema.xml')

        # Adds all fields and all type definitions to the main
        # etree.Element
        self.prepare_all_fields()
        self.add_type_definitions()

        # Writes the schema file.
        doc = etree.ElementTree(self.schema_element)
        out_file = open(os.path.join(path, 'schema.xml'), 'w')
        doc.write(out_file, xml_declaration=True, encoding='UTF-8',
                  pretty_print=True)
        out_file.close()

    def add_field(
                self, field_name, name_attr, type_attr, indexed_attr,
                stored_attr, required_attr, multivalued_attr):
        """Add field to the etree.Sublement object.

        Add a child to the 'fields' SubElement, and set the
        attributes for this child.

        Keyword Arguments:
        field_name -- the name of the XML element
        name_attr -- the name of the schema field
        type_attr -- the type of the schema field
        indexed_attr -- boolean for keeping track whether the schema
        field should be indexed or not
        stored_attr -- boolean for keeping track whether the schema
        field should be stored or not
        required_attr -- boolean for keeping track whether the schema
        field is required or not
        multivalued_attr -- boolean for keeping track whether the
        schema field is multivalued or not
        """

        field = etree.SubElement(self.fields_element, field_name)
        field.set("name", name_attr)
        field.set("type", type_attr)
        field.set("indexed", indexed_attr)
        field.set("stored", stored_attr)
        field.set("required", required_attr)
        field.set("multiValued", multivalued_attr)

    def prepare_all_fields(self):
        """Prepare the attributes for each field in the schema.

        Iterate through all the schema fields, and get the values for
        each attribute needed.
        """

        for (field_name, field_attrs) in self.schema.items():
            class_name = str(field_attrs.__class__.__name__)
            type_attr = self.FIELDS_TYPE_DICT[class_name]
            indexed_attr = str(field_attrs.indexed).lower()
            stored_attr = str(field_attrs.stored).lower()

            if field_name in self.REQUIRED_FIELDS:
                required_attr = "true"
            else:
                required_attr = "false"

            # Add field to the etree.Subelement holding all fields.
            self.add_field("field", field_name, type_attr, indexed_attr,
                           stored_attr, required_attr, "false")

    def add_type_definitions(self):
        """Add definitions of all types used for the schema fields."""
        self.types_element = etree.SubElement(self.schema_element, "types")
        self._add_string_type_definition()
        self._add_text_general_type_definition()
        self._add_date_type_definition()
        self._add_long_type_definition()
        self._add_lowercase_type_definition()

    def _add_string_type_definition(self):
        """Create the XML definition of the 'string' type."""
        field_type = etree.SubElement(self.types_element, "fieldType")
        field_type.set("name", "string")
        field_type.set("class", "solr.StrField")
        field_type.set("sortMissingLast", "true")

    def _add_text_general_type_definition(self):
        """Create the XML definition of the 'text_general' type."""
        field_type = etree.SubElement(self.types_element, "fieldType")
        field_type.set("name", "text_general")
        field_type.set("class", "solr.TextField")
        field_type.set("positionIncrementGap", "100")

        analyzer_index = etree.SubElement(field_type, "analyzer")
        analyzer_index.set("type", "index")

        tokenizer_index = etree.SubElement(analyzer_index, "tokenizer")
        tokenizer_index.set("class", "solr.StandardTokenizerFactory")

        analyzer_index_filter_s = etree.SubElement(analyzer_index, "filter")
        analyzer_index_filter_s.set("class", "solr.StopFilterFactory")
        analyzer_index_filter_s.set("ignoreCase", "true")
        analyzer_index_filter_s.set("words", "stopwords.txt")

        analyzer_index_filter_l = etree.SubElement(analyzer_index, "filter")
        analyzer_index_filter_l.set("class", "solr.LowerCaseFilterFactory")

        analyzer_query = etree.SubElement(field_type, "analyzer")
        analyzer_query.set("type", "query")

        tokenizer_query = etree.SubElement(analyzer_query, "tokenizer")
        tokenizer_query.set("class", "solr.StandardTokenizerFactory")

        analyzer_query_filter_s = etree.SubElement(analyzer_query, "filter")
        analyzer_query_filter_s.set("class", "solr.StopFilterFactory")
        analyzer_query_filter_s.set("ignoreCase", "true")
        analyzer_query_filter_s.set("words", "stopwords.txt")

        analyzer_query_filter_syn = etree.SubElement(analyzer_query, "filter")
        analyzer_query_filter_syn.set("class", "solr.SynonymFilterFactory")
        analyzer_query_filter_syn.set("synonyms", "synonyms.txt")
        analyzer_query_filter_syn.set("ignoreCase", "true")
        analyzer_query_filter_syn.set("expand", "true")

        analyzer_query_filter_l = etree.SubElement(analyzer_query, "filter")
        analyzer_query_filter_l.set("class", "solr.LowerCaseFilterFactory")

    def _add_date_type_definition(self):
        """Create the XML definition of the 'date' type."""
        field_type = etree.SubElement(self.types_element, "fieldType")
        field_type.set("name", "date")
        field_type.set("class", "solr.TrieDateField")
        field_type.set("precisionStep", "0")
        field_type.set("positionIncrementGap", "0")

    def _add_long_type_definition(self):
        """Create the XML definition of the 'long' type."""
        field_type = etree.SubElement(self.types_element, "fieldType")
        field_type.set("name", "long")
        field_type.set("class", "solr.TrieLongField")
        field_type.set("precisionStep", "0")
        field_type.set("positionIncrementGap", "0")

    def _add_lowercase_type_definition(self):
        """Create the XML definition of the 'lowercase' type."""
        field_type = etree.SubElement(self.types_element, "fieldType")
        field_type.set("name", "lowercase")
        field_type.set("class", "solr.TextField")
        field_type.set("positionIncrementGap", "100")

        analyzer = etree.SubElement(field_type, "analyzer")

        tokenizer = etree.SubElement(analyzer, "tokenizer")
        tokenizer.set("class", "solr.KeywordTokenizerFactory")

        analyzer_filter_l = etree.SubElement(analyzer, "filter")
        analyzer_filter_l.set("class", "solr.LowerCaseFilterFactory")

