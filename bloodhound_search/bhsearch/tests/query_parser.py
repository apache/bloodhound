import unittest
from bhsearch.tests.base import BaseBloodhoundSearchTest
from bhsearch.query_parser import DefaultQueryParser
from whoosh.query import terms, nary, wrappers


class MetaKeywordsParsingTestCase(BaseBloodhoundSearchTest):
    def setUp(self):
        super(MetaKeywordsParsingTestCase, self).setUp()
        self.parser = DefaultQueryParser(self.env)

    def test_can_parse_keyword_ticket(self):
        parsed_query = self.parser.parse("$ticket")
        self.assertEqual(parsed_query, terms.Term('type', 'ticket'))

    def test_can_parse_NOT_keyword_ticket(self):
        parsed_query = self.parser.parse("NOT $ticket")
        self.assertEqual(parsed_query,
                         wrappers.Not(
                             terms.Term('type', 'ticket')))

    def test_can_parse_keyword_wiki(self):
        parsed_query = self.parser.parse("$wiki")
        self.assertEqual(parsed_query, terms.Term('type', 'wiki'))

    def test_can_parse_keyword_resolved(self):
        parsed_query = self.parser.parse("$resolved")
        self.assertEqual(parsed_query,
                         nary.Or([terms.Term('status', 'resolved'),
                                  terms.Term('status', 'closed')]))

    def test_can_parse_meta_keywords_that_resolve_to_meta_keywords(self):
        parsed_query = self.parser.parse("$unresolved")
        self.assertEqual(parsed_query,
                         wrappers.Not(
                         nary.Or([terms.Term('status', 'resolved'),
                                  terms.Term('status', 'closed')])))

    def test_can_parse_complex_query(self):
        parsed_query = self.parser.parse("content:test $ticket $unresolved")

        self.assertEqual(parsed_query,
                         nary.And([
                             terms.Term('content', 'test'),
                             terms.Term('type', 'ticket'),
                             wrappers.Not(
                                 nary.Or([terms.Term('status', 'resolved'),
                                          terms.Term('status', 'closed')])
                             )
                         ]))


def suite():
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(MetaKeywordsParsingTestCase, 'test'))
    return test_suite

if __name__ == '__main__':
    unittest.main()
