from bhsearch import BHSEARCH_CONFIG_SECTION
from bhsearch.api import ISearchBackend, SCORE, QueryResult
from bhsearch.query_parser import DefaultQueryParser
from bhsearch.search_resources.ticket_search import TicketIndexer
from trac.core import Component, implements, TracError
from trac.config import Option
from trac.ticket.model import Ticket
from trac.ticket.api import TicketSystem
from trac.util.datefmt import utc
from datetime import datetime
from sunburnt import SolrInterface
from contextlib import contextmanager
from math import ceil

UNIQUE_ID = "unique_id"

HIGHLIGHTABLE_FIELDS = {"unique_id" : True,
                        "id" : True,
                        "type" : True,
                        "product" : True,
                        "milestone" : True,
                        "author" : True,
                        "component" : True,
                        "status" : True,
                        "resolution" : True,
                        "keywords" : True,
                        "summary" : True,
                        "content" : True,
                        "changes" : True,
                        "owner" : True,
                        "repository" : True,
                        "revision" : True,
                        "message" : True,
                        "name" : True}

class SolrBackend(Component):
  implements(ISearchBackend)

  server_url = Option(
      BHSEARCH_CONFIG_SECTION,
      'solr_server_url',
      doc="""Url of the server running Solr instance.""",
      doc_domain='bhsearch')


  def __init__(self):
    # resource_filename = pkg_resources.resource_filename
    # path = resource_filename(__name__, "schemadoc") # TODO: Use absolute path of schema
    self.solr_interface = SolrInterface(str(self.server_url))
    self.field_boosts = DefaultQueryParser(self.env).field_boosts


  def add_doc(self, doc, operation_context=None):
    self._reformat_doc(doc)
    doc[UNIQUE_ID] = self._create_unique_id(doc.get("product", ''),
                                            doc["type"],
                                            doc["id"])
    print doc["type"]
    self.solr_interface.add(doc)
    self.solr_interface.commit()


  def delete_doc(product, doc_type, doc_id, operation_context=None):
    unique_id = self._create_unique_id(product, doc_type, doc_id)
    self.solr_interface.delete(unique_id)


  def optimize(self):
    self.solr_interface.optimize()

  def query(self, query, query_string, sort = None, fields = None, filter = None,
            facets = None, pagenum = 1, pagelen = 20, highlight = False,
            highlight_fields = None, context = None):

    final_query_chain = self._create_query_chain(query)
    solr_query = self.solr_interface.query(final_query_chain)
    faceted_solr_query = solr_query.facet_by(facets)
    highlighted_solr_query = faceted_solr_query.highlight(HIGHLIGHTABLE_FIELDS)
    paginated_solr_query = highlighted_solr_query.paginate(rows=20000)

    results = paginated_solr_query.execute()

    return self._create_query_result(results, fields, pagenum, pagelen)

  def _create_query_result(self, results, fields, pagenum, pagelen):
    total_num, total_page_count, page_num, offset = \
                self._prepare_query_result_attributes(results, pagenum, pagelen)

    query_results = QueryResult()
    query_results.hits = total_num
    query_results.total_page_count = total_page_count
    query_results.page_number = page_num
    query_results.offset = offset

    docs = []
    highlighting = []

    for retrieved_record in results:
      result_doc = self._process_record(fields, retrieved_record)
      docs.append(result_doc)

      result_highlights = dict(retrieved_record['solr_highlights'])

      highlighting.append(result_highlights)
      query_results.docs = docs
      query_results.highlighting = highlighting

    return query_results

  def _create_query_chain(self, query):
    tokens = set([token.text for token in query.all_tokens()])
    final_query_chain = None
    for token in tokens:
      token_query_chain = self._search_fields_for_token(token)
      if final_query_chain == None:
        final_query_chain = token_query_chain
      else:
        final_query_chain |= token_query_chain

    return final_query_chain

  def _process_record(self, fields, retrieved_record):
    result_doc = dict()

    if fields:
      for field in fields:
        if field in retrieved_record:
          result_doc[field] = retrieved_record[field]
    else:
      for key, value in retrieved_record.items():
        result_doc[key] = value

    for key, value in result_doc.iteritems():
      result_doc[key] = self._from_solr_format(value)

    return result_doc

  def _from_solr_format(self, value):
    if isinstance(value, datetime):
      value = utc.localize(value)
    return value

  def _prepare_query_result_attributes(self, results, pagenum, pagelen):
    results_total_num = len(results)
    total_page_count = int(ceil(results_total_num / pagelen))
    pagenum = min(total_page_count, pagenum)

    offset = (pagenum - 1) * pagelen
    if (offset + pagelen) > results_total_num:
        pagelen = results_total_num - offset

    return results_total_num, total_page_count, pagenum, offset

  def is_index_outdated(self):
    return False

  def recreate_index(self):
    return True

  @contextmanager
  def start_operation(self):
    yield

  def _search_fields_for_token(self, token):
    query_chain = None
    for field, boost in self.field_boosts.iteritems():
      if field != 'query_suggestion_basket' and field != 'relations':
        field_token_dict = {field: token}
        if query_chain == None:
          query_chain = self.solr_interface.Q(**field_token_dict)**boost
        else:
          query_chain |= self.solr_interface.Q(**field_token_dict)**boost

    return query_chain

  def _reformat_doc(self, doc):
    for key, value in doc.items():
      if key is None:
        del doc[None]
      elif value is None:
        del doc[key]
      elif isinstance(value, basestring) and value == "":
        del doc[key]
      else:
        doc[key] = self._to_solr_format(value)

  def _to_solr_format(self, value):
    if isinstance(value, basestring):
      value = unicode(value)
    elif isinstance(value, datetime):
      value = self._convert_date_to_tz_naive_utc(value)
    return value


  def _convert_date_to_tz_naive_utc(self, value):
    if value.tzinfo:
      utc_time = value.astimezone(utc)
      value = utc_time.replace(tzinfo=None)
    return value


  def _create_unique_id(self, product, doc_type, doc_id):
    if product:
      return u"%s:%s:%s" % (product, doc_type, doc_id)
    else:
      return u"%s:%s" % (doc_type, doc_id)

  def getInstance(self):
    return self.solr_interface


