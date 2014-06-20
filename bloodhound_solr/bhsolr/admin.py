r"""Administration commands for Bloodhound Solr Search."""
from trac.core import Component, implements
from trac.admin import IAdminCommandProvider
from bhsolr.api import BloodhoundSolrApi

class BloodhoundSolrSearchAdmin(Component):
  """Bloodhound Solr Search administration component."""
  implements(IAdminCommandProvider)

  # IAdminCommandProvider methods
  def get_admin_commands(self):
    yield ('bhsolr populate_index', '', 'Populate Solr search index',
      None, BloodhoundSolrApi(self.env).populate_index)
    yield ('bhsolr optimize', '', 'Optimize Solr search index',
      None, BloodhoundSearchApi(self.env).optimize)

