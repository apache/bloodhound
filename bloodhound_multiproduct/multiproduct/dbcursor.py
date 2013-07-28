
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

import trac.db.util
from trac.util import concurrency

import sqlparse
import sqlparse.tokens as Tokens
import sqlparse.sql as Types

from multiproduct.cache import lru_cache

__all__ = ['BloodhoundIterableCursor', 'BloodhoundConnectionWrapper', 'ProductEnvContextManager']

SKIP_TABLES = ['auth_cookie',
               'session', 'session_attribute',
               'cache',
               'repository', 'revision', 'node_change',
               'bloodhound_product', 'bloodhound_productresourcemap', 'bloodhound_productconfig',
               'sqlite_master', 'bloodhound_relations'
               ]
TRANSLATE_TABLES = ['system',
                    'ticket', 'ticket_change', 'ticket_custom',
                    'attachment',
                    'enum', 'component', 'milestone', 'version',
                    'permission',
                    'wiki',
                    'report',
                    ]
PRODUCT_COLUMN = 'product'
GLOBAL_PRODUCT = ''

# Singleton used to mark translator as unset
class empty_translator(object):
    pass

translator_not_set = empty_translator()

@lru_cache(maxsize=1000)
def translate_sql(env, sql):
    translator = None
    log = None
    if env is not None:
        # FIXME: This is the right way to do it but breaks translation
        # if trac.db.api.DatabaseManager(self.env).debug_sql:
        if (env.parent or env).config['trac'].get('debug_sql', False):
            log = env.log
        product_prefix = env.product.prefix if env.product else GLOBAL_PRODUCT
        translator = BloodhoundProductSQLTranslate(SKIP_TABLES,
                                                   TRANSLATE_TABLES,
                                                   PRODUCT_COLUMN,
                                                   product_prefix)
    if log:
        log.debug('Original SQl: %s', sql)
    realsql = translator.translate(sql) if (translator is not None) else sql
    if log:
        log.debug('SQL: %s', realsql)
    return realsql

class BloodhoundIterableCursor(trac.db.util.IterableCursor):
    __slots__ = trac.db.util.IterableCursor.__slots__ + ['_translator']
    _tls = concurrency.ThreadLocal(env=None)

    def __init__(self, cursor, log=None):
        super(BloodhoundIterableCursor, self).__init__(cursor, log=log)

    def execute(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).execute(translate_sql(self.env, sql), args=args)

    def executemany(self, sql, args=None):
        return super(BloodhoundIterableCursor, self).executemany(translate_sql(self.env, sql), args=args)

    @property
    def env(self):
        return self._tls.env

    @classmethod
    def set_env(cls, env):
        cls._tls.env = env

    @classmethod
    def get_env(cls):
        return cls._tls.env

    @classmethod
    def cache_reset(cls):
        translate_sql.clear()

# replace trac.db.util.IterableCursor with BloodhoundIterableCursor
trac.db.util.IterableCursor = BloodhoundIterableCursor

class BloodhoundConnectionWrapper(object):

    def __init__(self, connection, env):
        self.connection = connection
        self.env = env

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, query, params=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.connection.execute(query, params=params)

    __call__ = execute

    def executemany(self, query, params=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.connection.executemany(query, params=params)

    def cursor(self):
        return BloodhoundCursorWrapper(self.connection.cursor(), self.env)

class BloodhoundCursorWrapper(object):

    def __init__(self, cursor, env):
        self.cursor = cursor
        self.env = env

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def __iter__(self):
        return self.cursor.__iter__()

    def execute(self, sql, args=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.cursor.execute(sql, args=args)

    def executemany(self, sql, args=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.cursor.executemany(sql, args=args)

class ProductEnvContextManager(object):
    """Wrap an underlying database context manager so as to keep track
    of (nested) product context.
    """
    def __init__(self, context, env=None):
        """Initialize product database context.

        :param context: Inner database context (e.g. `QueryContextManager`,
                        `TransactionContextManager` )
        :param env:     An instance of either `trac.env.Environment` or 
                        `multiproduct.env.ProductEnvironment` used to 
                        reduce the scope of database queries. If set 
                        to `None` then SQL queries will not be translated,
                        which is equivalent to having direct database access.
        """
        self.db_context = context
        self.env = env

    def __enter__(self):
        """Keep track of previous product context and override it with `env`;
        then enter the inner database context.
        """
        return BloodhoundConnectionWrapper(self.db_context.__enter__(), self.env)

    def __exit__(self, et, ev, tb): 
        """Uninstall current product context by restoring the last one;
        then leave the inner database context.
        """
        return self.db_context.__exit__(et, ev, tb)

    def __call__(self, *args, **kwargs):
        """Forward attribute access to nested database context on failure.
        """
        BloodhoundIterableCursor.set_env(self.env)
        return self.db_context(*args, **kwargs)

    def __getattr__(self, attrnm):
        """Forward attribute access to nested database context on failure.
        """
        return getattr(self.db_context, attrnm)

    def execute(self, sql, params=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.db_context.execute(sql, params=params)

    def executemany(self, sql, params=None):
        BloodhoundIterableCursor.set_env(self.env)
        return self.db_context.executemany(sql, params=params)


class BloodhoundProductSQLTranslate(object):
    _join_statements = ['LEFT JOIN', 'LEFT OUTER JOIN',
                        'RIGHT JOIN', 'RIGHT OUTER JOIN',
                        'JOIN', 'INNER JOIN']
    _from_end_words = ['WHERE', 'GROUP', 'HAVING', 'ORDER', 'UNION', 'LIMIT']

    def __init__(self, skip_tables, translate_tables, product_column, product_prefix):
        self._skip_tables = skip_tables
        self._translate_tables = translate_tables
        self._product_column = product_column
        self._product_prefix = product_prefix

    def _sqlparse_underline_hack(self, token):
        underline_token = lambda token: token.ttype == Tokens.Token.Error and token.value == '_'
        identifier_token = lambda token: isinstance(token, Types.Identifier) or isinstance(token, Types.Token)
        def prefix_token(token, prefix):
            if identifier_token(token):
                if isinstance(token, Types.IdentifierList):
                    token = token.tokens[0]
                token.value = prefix + token.value
                token.normalized = token.value.upper() if token.ttype in Tokens.Keyword \
                                                            else token.value
                if hasattr(token, 'tokens'):
                    if len(token.tokens) != 1:
                        raise Exception("Internal error, invalid token list")
                    token.tokens[0].value, token.tokens[0].normalized = token.value, token.normalized
            return

        if hasattr(token, 'tokens') and token.tokens and len(token.tokens):
            current = self._token_first(token)
            while current:
                leftover = None
                if underline_token(current):
                    prefix = ''
                    while underline_token(current):
                        prefix += current.value
                        prev = current
                        current = self._token_next(token, current)
                        self._token_delete(token, prev)
                        # expression ends with _ ... push the token to parent
                        if not current:
                            return prev
                    prefix_token(current, prefix)
                else:
                    leftover = self._sqlparse_underline_hack(current)
                    if leftover:
                        leftover.parent = token
                        self._token_insert_after(token, current, leftover)
                current = leftover if leftover else self._token_next(token, current)
        return None

    def _select_table_name_alias(self, tokens):
        return filter(lambda t: t.upper() != 'AS', [t.value for t in tokens if t.value.strip()])
    def _column_expression_name_alias(self, tokens):
        return filter(lambda t: t.upper() != 'AS', [t.value for t in tokens if t.value.strip()])

    def _select_alias_sql(self, alias):
        return ' AS %s' % alias

    def _translated_table_view_sql(self, name, alias=None):
        sql = "(SELECT * FROM %s WHERE %s='%s')" % (name, self._product_column, self._product_prefix)
        if alias:
            sql += self._select_alias_sql(alias)
        return sql

    def _prefixed_table_entity_name(self, tablename):
        return '"%s_%s"' % (self._product_prefix, tablename) if self._product_prefix else tablename

    def _prefixed_table_view_sql(self, name, alias):
        return '(SELECT * FROM %s) AS %s' % (self._prefixed_table_entity_name(name),
                                             alias)

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
    def _token_delete(self, parent, token):
        idx = self._token_idx(parent, token)
        del parent.tokens[idx]
        return idx
    def _token_insert(self, parent, idx, token):
        parent.tokens.insert(idx, token)

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
            idx = self._token_delete(parent, token)
            for t in token.tokens:
                self._token_insert(parent, idx, t)
                idx += 1
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
            return first_token, [list(first_token.flatten())]
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
            while current_token and \
                  not current_token.match(Tokens.Keyword, end_words) and \
                  not isinstance(current_token, Types.Where):
                tokens.append(current_token)
                current_token = self._token_next(parent, current_token)
        return current_token

    def _select_from(self, parent, start_token, end_words, table_name_callback=None, force_alias=False):
        def inject_table_view(token, name, alias):
            if name in self._skip_tables:
                pass
            elif name in self._translate_tables:
                if force_alias and not alias:
                    alias = name
                parent.tokens[self._token_idx(parent, token)] = sqlparse.parse(self._translated_table_view_sql(name,
                                                                                                               alias=alias))[0]
                if table_name_callback:
                    table_name_callback(name)
            else:
                if not alias:
                    alias = name
                parent.tokens[self._token_idx(parent, token)] = sqlparse.parse(self._prefixed_table_view_sql(name,
                                                                                                             alias))[0]
                if table_name_callback:
                    table_name_callback(name)

        def inject_table_alias(token, alias):
            parent.tokens[self._token_idx(parent, token)] = sqlparse.parse(self._select_alias_sql(alias))[0]

        def process_table_name_tokens(nametokens):
            if nametokens:
                l = self._select_table_name_alias(nametokens)
                if not l:
                    raise Exception("Invalid FROM table name")
                name, alias = l[0], None
                alias = l[1] if len(l) > 1 else name
                if not name in self._skip_tables:
                    token = nametokens[0]
                    for t in nametokens[1:]:
                        self._token_delete(parent, t)
                    inject_table_view(token, name, alias)
            return list()

        current_token = self._token_next(parent, start_token)
        prev_token = start_token
        table_name_tokens = list()
        join_tokens = list()
        while current_token and \
              not current_token.match(Tokens.Keyword, end_words) and \
              not isinstance(current_token, Types.Where):
            next_token = self._token_next(parent, current_token)
            if current_token.is_whitespace():
                pass
            elif isinstance(current_token, Types.IdentifierList):
                current_token = self._expression_token_unwind_hack(parent, current_token, prev_token)
                continue
            elif isinstance(current_token, Types.Identifier):
                parenthesis = filter(lambda t: isinstance(t, Types.Parenthesis), current_token.tokens)
                if parenthesis:
                    for p in parenthesis:
                        t = self._token_next(p, self._token_first(p))
                        if not t.match(Tokens.DML, 'SELECT'):
                            raise Exception("Invalid subselect statement")
                        self._select(p, t)
                else:
                    tablename = current_token.value.strip()
                    tablealias = current_token.get_name().strip()
                    if tablename == tablealias:
                        table_name_tokens.append(current_token)
                    else:
                        inject_table_view(current_token, tablename, tablealias)
            elif isinstance(current_token, Types.Parenthesis):
                t = self._token_next(current_token, self._token_first(current_token))
                if t.match(Tokens.DML, 'SELECT'):
                    identifier_token = self._token_next(parent, current_token)
                    as_token = None
                    if identifier_token.match(Tokens.Keyword, 'AS'):
                        as_token = identifier_token
                        identifier_token = self._token_next(parent, identifier_token)
                    if not isinstance(identifier_token, Types.Identifier):
                        raise Exception("Invalid subselect statement")
                    next_token = self._token_next(parent, identifier_token)
                    self._select(current_token, t)
                    if as_token:
                        self._token_delete(parent, as_token)
                    inject_table_alias(identifier_token, identifier_token.value)
            elif current_token.ttype == Tokens.Punctuation:
                if table_name_tokens:
                    next_token = self._token_next(parent, current_token)
                    table_name_tokens = process_table_name_tokens(table_name_tokens)
            elif current_token.match(Tokens.Keyword, ['JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER'] + self._join_statements):
                join_tokens.append(current_token.value.strip().upper())
                join = ' '.join(join_tokens)
                if join in self._join_statements:
                    join_tokens = list()
                    table_name_tokens = process_table_name_tokens(table_name_tokens)
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
            prev_token = current_token
            current_token = next_token
        if prev_token:
            process_table_name_tokens(table_name_tokens)
        return current_token

    def _select(self, parent, start_token, insert_table=None):
        token = self._token_next(parent, start_token)
        fields_token = self._token_next(parent, token) if token.match(Tokens.Keyword, ['ALL', 'DISTINCT']) else token
        current_token, field_lists = self._select_expression_tokens(parent, fields_token, ['FROM'] + self._from_end_words)
        def handle_insert_table(table_name):
            if insert_table and insert_table in self._translate_tables:
                if not field_lists or not field_lists[-1]:
                    raise Exception("Invalid SELECT field list")
                last_token = list(field_lists[-1][-1].flatten())[-1]
                for keyword in ["'", self._product_prefix, "'", ' ', ',']:
                    self._token_insert_after(last_token.parent, last_token, Types.Token(Tokens.Keyword, keyword))
            return
        table_name_callback = handle_insert_table if insert_table else None
        from_token = self._token_next_match(parent, start_token, Tokens.Keyword, 'FROM')
        if not from_token:
            # FROM not always required, example would be SELECT CURRVAL('"ticket_id_seq"')
            return current_token
        current_token = self._select_from(parent,
                                          from_token, self._from_end_words,
                                          table_name_callback=table_name_callback)
        if not current_token:
            return None
        while current_token:
            if isinstance(current_token, Types.Where) or \
               current_token.match(Tokens.Keyword, ['GROUP', 'HAVING', 'ORDER', 'LIMIT']):
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

    def _replace_table_entity_name(self, parent, token, table_name, entity_name=None):
        if not entity_name:
            entity_name = table_name
        next_token = self._token_next(parent, token)
        if not table_name in self._skip_tables + self._translate_tables:
            token_to_replace = parent.tokens[self._token_idx(parent, token)]
            if isinstance(token_to_replace, Types.Function):
                t = self._token_first(token_to_replace)
                if isinstance(t, Types.Identifier):
                    token_to_replace.tokens[self._token_idx(token_to_replace, t)] = Types.Token(Tokens.Keyword,
                                                                                                self._prefixed_table_entity_name(entity_name))
            elif isinstance(token_to_replace, Types.Identifier) or isinstance(token_to_replace, Types.Token):
                parent.tokens[self._token_idx(parent, token_to_replace)] = Types.Token(Tokens.Keyword,
                                                                                       self._prefixed_table_entity_name(entity_name))
            else:
                raise Exception("Internal error, invalid table entity token type")
        return next_token

    def _insert(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if not token.match(Tokens.Keyword, 'INTO'):
            raise Exception("Invalid INSERT statement")
        def insert_extra_column(tablename, columns_token):
            if tablename in self._translate_tables and \
               isinstance(columns_token, Types.Parenthesis):
                ptoken = self._token_first(columns_token)
                if not ptoken.match(Tokens.Punctuation, '('):
                    raise Exception("Invalid INSERT statement, expected parenthesis around columns")
                ptoken = self._token_next(columns_token, ptoken)
                last_token = ptoken
                while ptoken:
                    if isinstance(ptoken, Types.IdentifierList):
                        if any(i.get_name() == 'product'
                               for i in ptoken.get_identifiers()
                               if isinstance(i, Types.Identifier)):
                            return True
                    last_token = ptoken
                    ptoken = self._token_next(columns_token, ptoken)
                if not last_token or \
                   not last_token.match(Tokens.Punctuation, ')'):
                    raise Exception("Invalid INSERT statement, unable to find column parenthesis end")
                for keyword in [',', ' ', self._product_column]:
                    self._token_insert_before(columns_token, last_token, Types.Token(Tokens.Keyword, keyword))
            return False
        def insert_extra_column_value(tablename, ptoken, before_token):
            if tablename in self._translate_tables:
                for keyword in [',', "'", self._product_prefix, "'"]:
                    self._token_insert_before(ptoken, before_token, Types.Token(Tokens.Keyword, keyword))
            return
        tablename = None
        table_name_token = self._token_next(parent, token)
        has_product_column = False
        if isinstance(table_name_token, Types.Function):
            token = self._token_first(table_name_token)
            if isinstance(token, Types.Identifier):
                tablename = token.get_name()
                columns_token = self._replace_table_entity_name(table_name_token, token, tablename)
                if columns_token.match(Tokens.Keyword, 'VALUES'):
                    token = columns_token
                else:
                    has_product_column = insert_extra_column(tablename, columns_token)
                    token = self._token_next(parent, table_name_token)
        else:
            tablename = table_name_token.value
            columns_token = self._replace_table_entity_name(parent, table_name_token, tablename)
            if columns_token.match(Tokens.Keyword, 'VALUES'):
                token = columns_token
            else:
                has_product_column = insert_extra_column(tablename, columns_token)
                token = self._token_next(parent, columns_token)
        if has_product_column:
            pass  # INSERT already has product, no translation needed
        elif token.match(Tokens.Keyword, 'VALUES'):
            separators = [',', '(', ')']
            token = self._token_next(parent, token)
            while token:
                if isinstance(token, Types.Parenthesis):
                    ptoken = self._token_first(token)
                    if not ptoken.match(Tokens.Punctuation, '('):
                        raise Exception("Invalid INSERT statement")
                    last_token = ptoken
                    while ptoken:
                        if not ptoken.match(Tokens.Punctuation, separators) and \
                           not ptoken.match(Tokens.Keyword, separators) and \
                           not ptoken.is_whitespace():
                            ptoken = self._expression_token_unwind_hack(token, ptoken, self._token_prev(token, ptoken))
                            self._eval_expression_value(token, ptoken)
                        last_token = ptoken
                        ptoken = self._token_next(token, ptoken)
                    if not last_token or \
                       not last_token.match(Tokens.Punctuation, ')'):
                        raise Exception("Invalid INSERT statement, unable to find column value parenthesis end")
                    insert_extra_column_value(tablename, token, last_token)
                elif not token.match(Tokens.Punctuation, separators) and\
                     not token.match(Tokens.Keyword, separators) and\
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

    def _get_entity_name_from_token(self, parent, token):
        tablename = None
        if isinstance(token, Types.Identifier):
            tablename = token.get_name()
        elif isinstance(token, Types.Function):
            token = self._token_first(token)
            if isinstance(token, Types.Identifier):
                tablename = token.get_name()
        elif isinstance(token, Types.Token):
            tablename = token.value
        return tablename

    def _update(self, parent, start_token):
        table_name_token = self._token_next(parent, start_token)
        tablename = self._get_entity_name_from_token(parent, table_name_token)
        if not tablename:
            raise Exception("Invalid UPDATE statement, expected table name")
        token = self._replace_table_entity_name(parent, table_name_token, tablename)
        set_token = self._token_next_match(parent, token, Tokens.Keyword, 'SET')
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
        tablename = self._get_entity_name_from_token(parent, table_name_token)
        if not tablename:
            raise Exception("Invalid DELETE statement, expected table name")
        start_token = self._replace_table_entity_name(parent, table_name_token, tablename)
        self._update_delete_where_limit(tablename, parent, start_token)
        return

    def _create(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if token.match(Tokens.Keyword, 'TEMPORARY'):
            token = self._token_next(parent, token)
        if token.match(Tokens.Keyword, 'TABLE'):
            token = self._token_next(parent, token)
            while token.match(Tokens.Keyword, ['IF', 'NOT', 'EXIST']) or \
                  token.is_whitespace():
                token = self._token_next(parent, token)
            table_name = self._get_entity_name_from_token(parent, token)
            if not table_name:
                raise Exception("Invalid CREATE TABLE statement, expected table name")

            as_token = self._token_next_match(parent, token,
                                              Tokens.Keyword, 'AS')
            self._replace_table_entity_name(parent, token, table_name)

            if as_token:
                select_token = self._token_next_match(parent, as_token,
                                                      Tokens.DML, 'SELECT')
                if select_token:
                    return self._select(parent, select_token)
        elif token.match(Tokens.Keyword, ['UNIQUE', 'INDEX']):
            if token.match(Tokens.Keyword, 'UNIQUE'):
                token = self._token_next(parent, token)
            if token.match(Tokens.Keyword, 'INDEX'):
                index_token = self._token_next(parent, token)
                index_name = self._get_entity_name_from_token(parent, index_token)
                if not index_name:
                    raise Exception("Invalid CREATE INDEX statement, expected index name")
                on_token = self._token_next_match(parent, index_token, Tokens.Keyword, 'ON')
                if not on_token:
                    raise Exception("Invalid CREATE INDEX statement, expected ON specifier")
                table_name_token = self._token_next(parent, on_token)
                table_name = self._get_entity_name_from_token(parent, table_name_token)
                if not table_name:
                    raise Exception("Invalid CREATE INDEX statement, expected table name")
                self._replace_table_entity_name(parent, table_name_token, table_name)
                self._replace_table_entity_name(parent, index_token, table_name, entity_name=index_name)
        return

    def _alter(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if token.match(Tokens.Keyword, 'TABLE'):
            token = self._token_next(parent, token)
            table_name = self._get_entity_name_from_token(parent, token)
            if not table_name:
                raise Exception("Invalid CREATE TABLE statement, expected table name")
            token = self._replace_table_entity_name(parent, token, table_name)
            if token.match(Tokens.Keyword.DDL, ['ADD', 'DROP']) or\
               token.match(Tokens.Keyword, ['ADD', 'DROP']):
                token = self._token_next(parent, token)
                if token.match(Tokens.Keyword, 'CONSTRAINT'):
                    token = self._token_next(parent, token)
                    constraint_name = self._get_entity_name_from_token(parent, token)
                    if not constraint_name:
                        raise Exception("Invalid ALTER TABLE statement, expected constraint name")
                    self._replace_table_entity_name(parent, token, table_name, constraint_name)
        return

    def _drop(self, parent, start_token):
        token = self._token_next(parent, start_token)
        if token.match(Tokens.Keyword, 'TABLE'):
            token = self._token_next(parent, token)
            while token.match(Tokens.Keyword, ['IF', 'EXIST']) or\
                  token.is_whitespace():
                token = self._token_next(parent, token)
            table_name = self._get_entity_name_from_token(parent, token)
            if not table_name:
                raise Exception("Invalid DROP TABLE statement, expected table name")
            self._replace_table_entity_name(parent, token, table_name)
        return

    def translate(self, sql):
        dml_handlers = {'SELECT': self._select,
                        'INSERT': self._insert,
                        'UPDATE': self._update,
                        'DELETE': self._delete,
                        }
        ddl_handlers = {'CREATE': self._create,
                        'ALTER': self._alter,
                        'DROP': self._drop,
                        }
        try:
            formatted_sql = lambda sql: sql.to_unicode()
            sql_statement = sqlparse.parse(sql)[0]
            if '_' in sql:
                self._sqlparse_underline_hack(sql_statement)
            t = sql_statement.token_first()
            if t.match(Tokens.DML, dml_handlers.keys()):
                dml_handlers[t.normalized](sql_statement, t)
                sql = formatted_sql(sql_statement)
            elif t.match(Tokens.DDL, ddl_handlers.keys()):
                ddl_handlers[t.normalized](sql_statement, t)
                sql = formatted_sql(sql_statement)
            else:
                pass
        except Exception, ex:
            raise Exception("Failed to translate SQL '%s', exception '%s'" % (sql, ex.message))
        return sql
