
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

from trac.db.util import IterableCursor
from trac.util import concurrency

import sqlparse
import sqlparse.tokens as Tokens
import sqlparse.sql as Types

__all__ = ['BloodhoundIterableCursor']

TRANSLATE_TABLES = ['ticket', 'enum', 'component', 'milestone', 'version', 'wiki']
PRODUCT_COLUMN = 'product'

class BloodhoundIterableCursor(IterableCursor):
    __slots__ = IterableCursor.__slots__ + ['_translator']
    _tls = concurrency.ThreadLocal(env=None)

    def __init__(self, cursor, log=None):
        super(BloodhoundIterableCursor, self).__init__(cursor, log=log)
        self._translator = None

    @property
    def translator(self):
        if not self._translator:
            from env import DEFAULT_PRODUCT
            product = self.env.product_scope if self.env else DEFAULT_PRODUCT
            self._translator = BloodhoundProductSQLTranslate(TRANSLATE_TABLES,
                                                             PRODUCT_COLUMN,
                                                             product)
        return self._translator

    def _translate_sql(self, sql):
        return self.translator.translate(sql) if (self.env and not self.env.product_aware) else sql

    def execute(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).execute(self._translate_sql(sql), args=args)

    def executemany(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).executemany(self._translate_sql(sql), args=args)

    @property
    def env(self):
        return self._tls.env

    @classmethod
    def set_env(cls, env):
        cls._tls.env = env

class BloodhoundProductSQLTranslate(object):
    _join_statements = ['LEFT JOIN', 'LEFT OUTER JOIN',
                        'RIGHT JOIN', 'RIGHT OUTER JOIN',
                        'JOIN', 'INNER JOIN']
    _from_end_words = ['WHERE', 'GROUP', 'HAVING', 'ORDER', 'UNION']

    def __init__(self, translate_tables, product_column, product_prefix):
        self._translate_tables = translate_tables
        self._product_column = product_column
        self._product_prefix = product_prefix

    def _select_table_name_alias(self, tokens):
        return filter(lambda t: t.upper() != 'AS', [t.value for t in tokens if t.value.strip()])
    def _column_expression_name_alias(self, tokens):
        return filter(lambda t: t.upper() != 'AS', [t.value for t in tokens if t.value.strip()])

    def _patch_table_view_sql(self, name, alias=None):
        sql = '(SELECT * FROM %s WHERE %s="%s")' % (name, self._product_column, self._product_prefix)
        if alias:
            sql += ' AS %s' % alias
        return sql

    def _token_first(self, parent):
        return parent.token_first()
    def _token_next_match(self, parent, start_token, ttype, token):
        return parent.token_next_match(self._token_idx(parent, start_token), ttype, token)
    def _token_next(self, parent, from_token):
        return parent.token_next(self._token_idx(parent, from_token))
    def _token_prev(self, parent, from_token):
        return parent.token_prev(self._token_idx(parent, from_token))
    def _token_next_by_instance(self, parent, start_token, klass):
        return parent.token_next_by_instance(self._token_idx(parent, start_token), klass)
    def _token_next_by_type(self, parent, start_token, ttype):
        return parent.token_next_by_type(self._token_idx(parent, start_token), ttype)
    def _token_insert_before(self, parent, where, token):
        return parent.insert_before(where, token)
    def _token_insert_after(self, parent, where, token):
        return parent.insert_after(where, token)
    def _token_idx(self, parent, token):
        return parent.token_index(token)

    def _eval_expression_value(self, parent, token):
        if isinstance(token, Types.Parenthesis):
            t = self._token_first(token)
            if t.match(Tokens.Punctuation, '('):
                t = self._token_next(token, t)
                if t.match(Tokens.DML, 'SELECT'):
                    self._select(token, t)

    def _expression_token_unwind_hack(self, parent, token, start_token):
        # hack to workaround sqlparse bug that wrongly presents list of tokens
        # as IdentifierList in certain situations
        if isinstance(token, Types.IdentifierList):
            expression_token_idx = self._token_idx(parent, token)
            del parent.tokens[expression_token_idx]
            last_token = start_token
            for t in token.tokens:
                self._token_insert_after(parent, last_token, t)
                last_token = t
            token = self._token_next(parent, start_token)
        return token

    def _where(self, parent, where_token):
        if isinstance(where_token, Types.Where):
            token = self._token_first(where_token)
            if not token.match(Tokens.Keyword, 'WHERE'):
                raise Exception("Invalid WHERE statement")
            while token:
                self._eval_expression_value(where_token, token)
                token = self._token_next(where_token, token)
        return

    def _select_expression_tokens(self, parent, first_token, end_words):
        if isinstance(first_token, Types.IdentifierList):
            return first_token, [first_token]
        tokens = list()
        current_list = list()
        current_token = first_token
        while current_token and not current_token.match(Tokens.Keyword, end_words):
            if current_token.match(Tokens.Punctuation, ','):
                if current_list:
                    tokens.append(current_list)
                    current_list = list()
            elif current_token.is_whitespace():
                pass
            else:
                current_list.append(current_token)
            current_token = self._token_next(parent, current_token)
        if current_list:
            tokens.append(current_list)
        return current_token, tokens

    def _select_join(self, parent, start_token, end_words):
        current_token = self._select_from(parent, start_token, ['ON'], force_alias=True)
        tokens = list()
        if current_token:
            current_token = self._token_next(parent, current_token)
            while current_token and\
                  not current_token.match(Tokens.Keyword, end_words) and\
                  not isinstance(current_token, Types.Where):
                tokens.append(current_token)
                current_token = self._token_next(parent, current_token)
        return current_token

    def _select_from(self, parent, start_token, end_words, table_name_callback=None, force_alias=False):
        def inject_table_view(token, name, alias):
            if force_alias and not alias:
                alias = name
            parent.tokens[self._token_idx(parent, token)] = sqlparse.parse(self._patch_table_view_sql(name,
                                                                                                      alias=alias))[0]

        def process_table_name_tokens(token, nametokens):
            if nametokens:
                l = self._select_table_name_alias(nametokens)
                if not l:
                    raise Exception("Invalid FROM table name")
                name, alias = l[0], None
                if len(l) > 1:
                    alias = l[1]
                if name in self._translate_tables:
                    inject_table_view(token, name, alias)
                if table_name_callback:
                    table_name_callback(tablename)
            return list()

        current_token = self._token_next(parent, start_token)
        last_token = current_token
        table_name_tokens = list()
        join_tokens = list()
        while current_token and \
              not current_token.match(Tokens.Keyword, end_words) and \
              not isinstance(current_token, Types.Where):
            last_token = current_token
            next_token = self._token_next(parent, current_token)
            if current_token.is_whitespace():
                pass
            elif isinstance(current_token, Types.Identifier):
                parenthesis = filter(lambda t: isinstance(t, Types.Parenthesis), current_token.tokens)
                if parenthesis:
                    for p in parenthesis:
                        t = self._token_next(p, p.token_first())
                        if not t.match(Tokens.DML, 'SELECT'):
                            raise Exception("Invalid subselect statement")
                        self._select(p, t)
                else:
                    tablename = current_token.value.strip()
                    tablealias = current_token.get_name().strip()
                    if tablename in self._translate_tables:
                        inject_table_view(current_token, tablename, tablealias)
                    if table_name_callback:
                        table_name_callback(tablename)
            elif current_token.ttype == Tokens.Punctuation:
                if table_name_tokens:
                    next_token = self._token_next(parent, current_token)
                    table_name_tokens = process_table_name_tokens(current_token,
                                                                  table_name_tokens)
            elif current_token.match(Tokens.Keyword, ['JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER'] + self._join_statements):
                join_tokens.append(current_token.value.strip().upper())
                join = ' '.join(join_tokens)
                if join in self._join_statements:
                    join_tokens = list()
                    next_token = self._select_join(parent,
                                                   current_token,
                                                   ['JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER']
                                                    + self._join_statements
                                                    + self._from_end_words)
            elif current_token.ttype == Tokens.Keyword or \
                 current_token.ttype == Tokens.Token.Literal.Number.Integer:
                table_name_tokens.append(current_token)
            else:
                raise Exception("Failed to parse FROM table name")
            current_token = next_token

        if last_token and table_name_tokens:
            process_table_name_tokens(last_token,
                                      table_name_tokens)
        return current_token

    def _select(self, parent, start_token, insert_table=None):
        token = self._token_next(parent, start_token)
        fields_token = self._token_next(parent, token) if token.match(Tokens.Keyword, ['ALL', 'DISTINCT']) else token
        current_token, field_lists = self._select_expression_tokens(parent, fields_token, ['FROM'] + self._from_end_words)
        def handle_insert_table(table_name):
            if table_name == insert_table:
                for keyword in [self._product_column, ',', ' ']:
                    self._token_insert_before(parent, fields_token, Types.Token(Tokens.Keyword, keyword))
            return
        table_name_callback = handle_insert_table if insert_table else None
        from_token = self._token_next_match(parent, start_token, Tokens.Keyword, 'FROM')
        if not from_token:
            raise Exception("Expected FROM in SELECT")
        current_token = self._select_from(parent,
                                          from_token, self._from_end_words,
                                          table_name_callback=table_name_callback)
        if not current_token:
            return None
        while current_token:
            if isinstance(current_token, Types.Where) or \
               current_token.match(Tokens.Keyword, ['GROUP', 'HAVING', 'ORDER']):
                if isinstance(current_token, Types.Where):
                    self._where(parent, current_token)
                start_token = self._token_next(parent, current_token)
                next_token = self._token_next_match(parent,
                                                    start_token,
                                                    Tokens.Keyword,
                                                    self._from_end_words) if start_token else None
            elif current_token.match(Tokens.Keyword, ['UNION']):
                token = self._token_next(parent, current_token)
                if not token.match(Tokens.DML, 'SELECT'):
                    raise Exception("Invalid SELECT UNION statement")
                token = self._select(parent, current_token, insert_table=insert_table)
                next_token = self._token_next(parent, token) if token else None
            else:
                raise Exception("Unsupported SQL statement")
            current_token = next_token
        return current_token

    def _insert(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if not token.match(Tokens.Keyword, 'INTO'):
            raise Exception("Invalid INSERT statement")
        def insert_extra_column(tablename, columns_token):
            if tablename in self._translate_tables and\
               isinstance(columns_token, Types.Parenthesis):
                ptoken = self._token_first(columns_token)
                if not ptoken.match(Tokens.Punctuation, '('):
                    raise Exception("Invalid INSERT statement")
                for keyword in [' ', ',', self._product_column]:
                    self._token_insert_after(columns_token, ptoken, Types.Token(Tokens.Keyword, keyword))
            return
        def insert_extra_column_value(tablename, ptoken, start_token):
            if tablename in self._translate_tables:
                for keyword in [',', "'", self._product_prefix, "'"]:
                    self._token_insert_after(ptoken, start_token, Types.Token(Tokens.Keyword, keyword))
            return
        tablename = None
        table_name_token = self._token_next(parent, token)
        if isinstance(table_name_token, Types.Function):
            token = self._token_first(table_name_token)
            if isinstance(token, Types.Identifier):
                tablename = token.get_name()
                columns_token = self._token_next(table_name_token, token)
                insert_extra_column(tablename, columns_token)
                token = self._token_next(parent, table_name_token)
        else:
            tablename = table_name_token.value
            columns_token = self._token_next(parent, table_name_token)
            insert_extra_column(tablename, columns_token)
            token = self._token_next(parent, columns_token)
        if token.match(Tokens.Keyword, 'VALUES'):
            token = self._token_next(parent, token)
            while token:
                if isinstance(token, Types.Parenthesis):
                    ptoken = self._token_first(token)
                    if not ptoken.match(Tokens.Punctuation, '('):
                        raise Exception("Invalid INSERT statement")
                    insert_extra_column_value(tablename, token, ptoken)
                    while ptoken:
                        if not ptoken.match(Tokens.Punctuation, [',', '(', ')']) and \
                           not ptoken.match(Tokens.Keyword, [',', '(', ')']) and \
                           not ptoken.is_whitespace():
                            ptoken = self._expression_token_unwind_hack(token, ptoken, self._token_prev(token, ptoken))
                            self._eval_expression_value(token, ptoken)
                        ptoken = self._token_next(token, ptoken)
                elif not token.match(Tokens.Punctuation, [',', '(', ')']) and\
                     not token.match(Tokens.Keyword, [',', '(', ')']) and\
                     not token.is_whitespace():
                    raise Exception("Invalid INSERT statement, unable to parse VALUES section")
                token = self._token_next(parent, token)
        elif token.match(Tokens.DML, 'SELECT'):
            self._select(parent, token, insert_table=tablename)
        else:
            raise Exception("Invalid INSERT statement")
        return

    def _update_delete_where_limit(self, table_name, parent, start_token):
        if not start_token:
            return
        where_token = start_token if isinstance(start_token, Types.Where) \
                                  else self._token_next_by_instance(parent, start_token, Types.Where)
        if where_token:
            self._where(parent, where_token)
        if not table_name in self._translate_tables:
            return
        if where_token:
            keywords = [self._product_column, '=', "'", self._product_prefix, "'", ' ', 'AND', ' ']
            keywords.reverse()
            token = self._token_first(where_token)
            if not token.match(Tokens.Keyword, 'WHERE'):
                token = self._token_next_match(where_token, token, Tokens.Keyword, 'WHERE')
            if not token:
                raise Exception("Invalid UPDATE statement, failed to parse WHERE")
            for keyword in keywords:
                self._token_insert_after(where_token, token, Types.Token(Tokens.Keyword, keyword))
        else:
            keywords = ['WHERE', ' ', self._product_column, '=', "'", self._product_prefix, "'"]
            limit_token = self._token_next_match(parent, start_token, Tokens.Keyword, 'LIMIT')
            if limit_token:
                for keyword in keywords:
                    self._token_insert_before(parent, limit_token, Types.Token(Tokens.Keyword, keyword))
                self._token_insert_before(parent, limit_token, Types.Token(Tokens.Keyword, ' '))
            else:
                last_token = token = start_token
                while token:
                    last_token = token
                    token = self._token_next(parent, token)
                keywords.reverse()
                for keyword in keywords:
                    self._token_insert_after(parent, last_token, Types.Token(Tokens.Keyword, keyword))
        return

    def _update(self, parent, start_token):
        table_name_token = self._token_next(parent, start_token)
        if isinstance(table_name_token, Types.Identifier):
            tablename = table_name_token.get_name()
        elif isinstance(table_name_token, Types.Token):
            tablename = table_name_token.value
        else:
            raise Exception("Invalid UPDATE statement, expected table name")
        set_token = self._token_next_match(parent, table_name_token, Tokens.Keyword, 'SET')
        if set_token:
            token = set_token
            while token and \
                  not isinstance(token, Types.Where) and \
                  not token.match(Tokens.Keyword, 'LIMIT'):
                if not token.match(Tokens.Keyword, 'SET') and \
                   not token.match(Tokens.Punctuation, ','):
                    raise Exception("Invalid UPDATE statement, failed to match separator")
                column_token = self._token_next(parent, token)
                if isinstance(column_token, Types.Comparison):
                    token = self._token_next(parent, column_token)
                    continue
                equals_token = self._token_next(parent, column_token)
                if not equals_token.match(Tokens.Token.Operator.Comparison, '='):
                    raise Exception("Invalid UPDATE statement, SET equals token mismatch")
                expression_token = self._token_next(parent, equals_token)
                expression_token = self._expression_token_unwind_hack(parent, expression_token, equals_token)
                self._eval_expression_value(parent, expression_token)
                token = self._token_next(parent, expression_token)
            start_token = token
        self._update_delete_where_limit(tablename, parent, start_token)
        return

    def _delete(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if not token.match(Tokens.Keyword, 'FROM'):
            raise Exception("Invalid DELETE statement")
        table_name_token = self._token_next(parent, token)
        if isinstance(table_name_token, Types.Identifier):
            tablename = table_name_token.get_name()
        elif isinstance(table_name_token, Types.Token):
            tablename = table_name_token.value
        else:
            raise Exception("Invalid DELETE statement, expected table name")
        if not tablename in self._translate_tables:
            return
        self._update_delete_where_limit(tablename, parent, start_token)
        return

    def translate(self, sql):
        dml_handlers = {'SELECT': self._select,
                        'INSERT': self._insert,
                        'UPDATE': self._update,
                        'DELETE': self._delete,
                        }
        try:
            sql_statement = sqlparse.parse(sql)[0]
            t = sql_statement.token_first()
            if not t.match(Tokens.DML, dml_handlers.keys()):
                return sql
            dml_handlers[t.value](sql_statement, t)
            translated_sql = sqlparse.format(sql_statement.to_unicode(), reindent=True)
        except Exception:
            raise Exception("Failed to translate SQL '%s'" % sql)
        return translated_sql
