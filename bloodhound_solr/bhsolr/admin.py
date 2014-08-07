from trac.core import Component, implements
from bhsolr.schema import SolrSchema
from trac.admin import IAdminCommandProvider

class BloodhoundSolrAdmin(Component):

    implements(IAdminCommandProvider)

    # IAdminCommandProvider methods
    def get_admin_commands(self):
        yield ('bhsolr generate_schema', '<path>',
               'Generate Solr schema',
               None, SolrSchema(self.env).generate_schema)


