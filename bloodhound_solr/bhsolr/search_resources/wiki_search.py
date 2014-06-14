from trac.wiki import WikiSystem, WikiPage
from bhsearch.search_resources.wiki_search import WikiIndexer
from bhsearch.search_resources.base import BaseIndexer

class WikiSearchModel(BaseIndexer):

  def get_entries_for_index(self):
    page_names = WikiSystem(self.env).get_pages()
    for page_name in page_names:
      page = WikiPage(self.env, page_name)
      yield WikiIndexer(self.env).build_doc(page)
