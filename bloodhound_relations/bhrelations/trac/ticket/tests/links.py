from trac.ticket.model import Ticket
from trac.test import EnvironmentStub, Mock
from trac.ticket.links import LinksProvider
from trac.ticket.api import TicketSystem
from trac.ticket.query import Query
from trac.util.datefmt import utc
from copy import copy
import unittest

class TicketTestCase(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub(default_data=True)
        self.env.config.set('ticket-links', 'dependency', 'dependson,dependent')
        self.env.config.set('ticket-links', 'dependency.validator', 'no_cycle')
        self.env.config.set('ticket-links', 'parent_children', 
                                                            'parent,children')
        self.env.config.set('ticket-links', 'parent_children.validator',
                                                            'parent_child')
        self.env.config.set('ticket-links', 'children.blocks', 'true')
        self.env.config.set('ticket-links', 'children.label', 'Overridden')
        self.env.config.set('ticket-links', 'parent.copy_fields',
                                                            'summary, foo')
        self.env.config.set('ticket-links', 'oneway', 'refersto')
        self.req = Mock(href=self.env.href, authname='anonymous', tz=utc,
                        args=dict(action='dummy'))

    def _insert_ticket(self, summary, **kw):
        """Helper for inserting a ticket into the database"""
        ticket = Ticket(self.env)
        for k,v in kw.items():
            ticket[k] = v
        return ticket.insert()

    def _create_a_ticket(self):
        ticket = Ticket(self.env)
        ticket['reporter'] = 'santa'
        ticket['summary'] = 'Foo'
        ticket['foo'] = 'This is a custom field'
        return ticket

    # TicketSystem tests
    
    def test_get_ends(self):
        links_provider = LinksProvider(self.env)
        self.assertEquals(set(links_provider.get_ends()),
                          set([('dependson', 'dependent'), 
                               ('parent', 'children'), ('refersto', None)])
                          )
    
    def test_render_end(self):
        links_provider = LinksProvider(self.env)
        self.assertEquals(links_provider.render_end('refersto'), 'Refersto')
        self.assertEquals(links_provider.render_end('children'), 'Overridden')
    
    def test_is_blocker(self):
        links_provider = LinksProvider(self.env)
        self.assertFalse(links_provider.is_blocker('parent'))
        self.assertTrue(links_provider.is_blocker('children'))
        
    def test_link_ends_map(self):
        ticket_system = TicketSystem(self.env)
        self.assertEquals(ticket_system.link_ends_map,
                          {'dependson': 'dependent', 'dependent': 'dependson',
                           'parent': 'children', 'children': 'parent',
                           'refersto': None})
    
    def test_parse_links(self):
        ticket_system = TicketSystem(self.env)
        self.assertEquals([1, 2, 42], ticket_system.parse_links('1 2 42'))
        self.assertEquals([1, 2, 42], ticket_system.parse_links('#1 #2 #42'))
        self.assertEquals([1, 2, 42], ticket_system.parse_links('1, 2, 42'))
        self.assertEquals([1, 2, 42], ticket_system.parse_links('#1, #2, #42'))
        self.assertEquals([1, 2, 42], ticket_system.parse_links('#1 #2 #42 #1'))
        
    def test_get_ticket_fields(self):
        ticket_system = TicketSystem(self.env)
        fields = ticket_system.get_ticket_fields()
        link_fields = [f['name'] for f in fields if f.get('link')]
        self.assertEquals(5, len(link_fields))

    def test_update_links(self):
        ticket = self._create_a_ticket()
        ticket.insert()
        ticket = self._create_a_ticket()
        ticket['dependson'] = '#1, #2'
        ticket.insert()

        # Check if ticket link in #1 has been updated
        ticket = Ticket(self.env, 1)
        self.assertEqual(1, ticket.id)
        self.assertEqual('#2', ticket['dependent'])
        
        # Remove link from #2 to #1
        ticket = Ticket(self.env, 2)
        ticket['dependson'] = '#2'
        ticket.save_changes("me", "testing")

        # Check if ticket link in #1 has been updated
        ticket = Ticket(self.env, 1)
        self.assertEqual(1, ticket.id)
        self.assertEqual('', ticket['dependent'])
        
    def test_populate_from_linked_field(self):
        ticket = self._create_a_ticket()
        ticket.insert()
        ticket = Ticket(self.env)
        ticket.populate_from(1, link_field_name='children')
        self.assertEqual('Foo', ticket['summary'])
        self.assertEqual('#1', ticket['children'])
        
    def test_save_retrieve_links(self):
        ticket = self._create_a_ticket()
        ticket.insert()
        ticket = self._create_a_ticket()
        ticket['dependson'] = '#1, #2'
        ticket.insert()

        # Check if ticket link in #1 has been updated
        ticket = Ticket(self.env, 1)
        self.assertEqual(1, ticket.id)
        self.assertEqual('#2', ticket['dependent'])

    def test_query_by_result(self):
        ticket = self._create_a_ticket()
        ticket.insert()
        ticket = self._create_a_ticket()
        ticket['dependson'] = '#1'
        ticket.insert()
        query = Query.from_string(self.env, 'dependson=1', order='id')
        sql, args = query.get_sql()
        tickets = query.execute(self.req)
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]['id'], 2)
    
    def test_query_by_result2(self):
        ticket = self._create_a_ticket()
        ticket.insert()
        ticket = self._create_a_ticket()
        ticket['dependson'] = '#1'
        ticket.insert()
        query = Query.from_string(self.env, 'dependent=2', order='id')
        sql, args = query.get_sql()
        tickets = query.execute(self.req)
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]['id'], 1)
    
    def test_validator_links_exists(self):
        ticket1 = self._create_a_ticket()
        ticket1.insert()
        ticket2 = self._create_a_ticket()
        ticket2['dependson'] = '#1'
        links_provider = LinksProvider(self.env)
        issues = links_provider.validate_ticket(self.req, ticket2)
        self.assertEquals(sum(1 for _ in issues), 0)
        ticket2['dependson'] = '#404'
        issues = links_provider.validate_ticket(self.req, ticket2)
        self.assertEquals(sum(1 for _ in issues), 1)
        
    def test_validator_no_cyle(self):
        ticket1 = self._create_a_ticket()
        ticket1.insert()
        ticket2 = self._create_a_ticket()
        ticket2['dependson'] = '#1'
        links_provider = LinksProvider(self.env)
        issues = links_provider.validate_ticket(self.req, ticket2)
        self.assertEquals(sum(1 for _ in issues), 0)
        ticket2.insert()
        ticket1['dependson'] = '#2'
        issues = links_provider.validate_ticket(self.req, ticket1)
        self.assertEquals(sum(1 for _ in issues), 1)

    def test_validator_parent_child(self):
        ticket1 = self._create_a_ticket()
        ticket1.insert()
        ticket2 = self._create_a_ticket()
        ticket2['parent'] = '#1'
        links_provider = LinksProvider(self.env)
        issues = links_provider.validate_ticket(self.req, ticket2)
        self.assertEquals(sum(1 for _ in issues), 0)
        ticket2.insert()
        ticket1['parent'] = '#2'
        issues = links_provider.validate_ticket(self.req, ticket1)
        self.assertEquals(sum(1 for _ in issues), 1)
        ticket1['parent'] = ''
        ticket3 = self._create_a_ticket()
        ticket3['parent'] = '#1, #2'
        issues = links_provider.validate_ticket(self.req, ticket3)
        self.assertEquals(sum(1 for _ in issues), 1)
    
    def test_validator_blocker(self):
        ticket1 = self._create_a_ticket()
        ticket1['status'] = 'new'
        ticket1.insert()
        ticket2 = self._create_a_ticket()
        ticket2['children'] = '#1'
        links_provider = LinksProvider(self.env)
        self.assertEquals([1], links_provider.find_blockers(ticket2, 'children',
                                                                     []))
        req = copy(self.req) 
        req.args['action'] = 'resolve'
        issues = links_provider.validate_ticket(req, ticket2)
        self.assertEquals(sum(1 for _ in issues), 1)
        

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TicketTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
