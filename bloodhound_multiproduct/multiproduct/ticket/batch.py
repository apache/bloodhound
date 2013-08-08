from trac.ticket.batch import BatchModifyModule
from trac.util.translation import _
from trac.web.chrome import add_script_data
from multiproduct.env import ProductEnvironment


class ProductBatchModifyModule(BatchModifyModule):
    def add_template_data(self, req, data, tickets):
        if isinstance(self.env, ProductEnvironment):
            super(ProductBatchModifyModule, self).add_template_data(
                req, data, tickets)
            return

        data['batch_modify'] = True
        data['query_href'] = req.session['query_href'] or req.href.query()

        tickets_by_product = {}
        for t in tickets:
            tickets_by_product.setdefault(t['product'], []).append(t)

        data['action_controls'] = []
        global_env = ProductEnvironment.lookup_global_env(self.env)
        tmpenv = self.env
        for k,v in tickets_by_product.iteritems():
            self.env = ProductEnvironment(global_env, k)
            data['action_controls'] += self._get_action_controls(req, v)
        self.env = tmpenv
        batch_list_modes = [
            {'name': _("add"), 'value': "+"},
            {'name': _("remove"), 'value': "-"},
            {'name': _("add / remove"), 'value': "+-"},
            {'name': _("set to"), 'value': "="},
        ]
        add_script_data(req, batch_list_modes=batch_list_modes,
                             batch_list_properties=self._get_list_fields())

import trac.ticket.batch
trac.ticket.batch.BatchModifyModule = ProductBatchModifyModule
trac.ticket.BatchModifyModule = ProductBatchModifyModule

