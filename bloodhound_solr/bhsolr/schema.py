from lxml import etree
from bhsearch.whoosh_backend import WhooshBackend
from trac.core import Component, implements, TracError
import os

class SolrSchema(Component):
  instance = None

  REQUIRED_FIELDS = {"id": True,
                     "unique_id": True,
                     "type": True}

  FIELDS_TYPE_DICT = {"ID": "string",
                      "DATETIME": "date",
                      "KEYWORD": "string",
                      "TEXT": "text_general"
                      }

  def __init__(self):
    self.schema = WhooshBackend.SCHEMA
    self.schema_element = etree.Element("schema")
    self.schema_element.set("name", "Bloodhound Solr Schema")
    self.schema_element.set("version", "1")

    self.path = None
    self.fields_element = etree.SubElement(self.schema_element, "fields")
    self.unique_key_element = etree.SubElement(self.schema_element, "uniqueKey")
    self.unique_key_element.text = "unique_id"

    version_field = etree.SubElement(self.fields_element, "field")
    version_field.set("name", "_version_")
    version_field.set("type", "long")
    version_field.set("indexed", "true")
    version_field.set("stored", "true")

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
    stored_name.set("multivalued", "false")

  # @classmethod
  # def getInstance(self, env):
  #   if not self.instance:
  #     self.instance = SolrSchema(env)
  #   return self.instance

  def generate_schema(self, path=None):
    if not path:
      path = os.getcwd()

    self.add_all_fields()
    self.add_type_definitions()
    doc = etree.ElementTree(self.schema_element)

    self.path = os.path.join(path, 'schema.xml')

    out_file = open(os.path.join(path, 'schema.xml'), 'w')
    doc.write(out_file, xml_declaration=True, encoding='UTF-8', pretty_print=True)
    out_file.close()

  def add_field(self, field_name, name_attr, type_attr, indexed_attr, stored_attr, required_attr, multivalued_attr):
    field = etree.SubElement(self.fields_element, field_name)
    field.set("name", name_attr)
    field.set("type", type_attr)
    field.set("indexed", indexed_attr)
    field.set("stored", stored_attr)
    field.set("required", required_attr)
    field.set("multivalued", multivalued_attr)

  def add_all_fields(self):
    for (field_name, field_attrs) in self.schema.items():
      type_attr = SolrSchema.FIELDS_TYPE_DICT[str(field_attrs.__class__.__name__)]
      indexed_attr = str(field_attrs.indexed).lower()
      stored_attr = str(field_attrs.stored).lower()
      if field_name in SolrSchema.REQUIRED_FIELDS:
        required_attr = "true"
      else:
        required_attr = "false"

      self.add_field("field", field_name, type_attr, indexed_attr, stored_attr, required_attr, "false")


  def add_type_definitions(self):
    self.types_element = etree.SubElement(self.schema_element, "types")
    self._add_string_type_definition()
    self._add_text_general_type_definition()
    self._add_date_type_definition()
    self._add_long_type_definition()
    self._add_lowercase_type_definition()


  def _add_string_type_definition(self):
    field_type = etree.SubElement(self.types_element, "fieldType")
    field_type.set("name", "string")
    field_type.set("class", "solr.StrField")
    field_type.set("sortMissingLast", "true")


  def _add_text_general_type_definition(self):
    field_type = etree.SubElement(self.types_element, "fieldType")
    field_type.set("name", "text_general")
    field_type.set("class", "solr.TextField")
    field_type.set("positionIncrementGap", "100")

    analyzer_index = etree.SubElement(field_type, "analyzer")
    analyzer_index.set("type", "index")

    tokenizer_index = etree.SubElement(analyzer_index, "tokenizer")
    tokenizer_index.set("class", "solr.StandardTokenizerFactory")
    filter1 = etree.SubElement(analyzer_index, "filter")
    filter1.set("class", "solr.StopFilterFactory")
    filter1.set("ignoreCase", "true")
    filter1.set("words", "stopwords.txt")

    filter2 = etree.SubElement(analyzer_index, "filter")
    filter2.set("class", "solr.LowerCaseFilterFactory")

    analyzer_query = etree.SubElement(field_type, "analyzer")
    analyzer_query.set("type", "query")
    tokenizer_query = etree.SubElement(analyzer_query, "tokenizer")
    tokenizer_query.set("class", "solr.StandardTokenizerFactory")
    filter3 = etree.SubElement(analyzer_query, "filter")
    filter3.set("class", "solr.StopFilterFactory")
    filter3.set("ignoreCase", "true")
    filter3.set("words", "stopwords.txt")

    filter4 = etree.SubElement(analyzer_query, "filter")
    filter4.set("class", "solr.SynonymFilterFactory")
    filter4.set("synonyms", "synonyms.txt")
    filter4.set("ignoreCase", "true")
    filter4.set("expand", "true")

    filter5 = etree.SubElement(analyzer_query, "filter")
    filter5.set("class", "solr.LowerCaseFilterFactory")

  def _add_date_type_definition(self):
    field_type = etree.SubElement(self.types_element, "fieldType")
    field_type.set("name", "date")
    field_type.set("class", "solr.TrieDateField")
    field_type.set("precisionStep", "0")
    field_type.set("positionIncrementGap", "0")

  def _add_long_type_definition(self):
    field_type = etree.SubElement(self.types_element, "fieldType")
    field_type.set("name", "long")
    field_type.set("class", "solr.TrieLongField")
    field_type.set("precisionStep", "0")
    field_type.set("positionIncrementGap", "0")

  def _add_lowercase_type_definition(self):
    field_type = etree.SubElement(self.types_element, "fieldType")
    field_type.set("name", "lowercase")
    field_type.set("class", "solr.TextField")
    field_type.set("positionIncrementGap", "100")

    analyzer = etree.SubElement(field_type, "analyzer")
    tokenizer = etree.SubElement(analyzer, "tokenizer")
    tokenizer.set("class", "solr.KeywordTokenizerFactory")
    filter_lowercase = etree.SubElement(analyzer, "filter")
    filter_lowercase.set("class", "solr.LowerCaseFilterFactory")
