
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

"""Tests for multiproduct/dbcursor.py"""

import unittest
from multiproduct.dbcursor import BloodhoundProductSQLTranslate, SKIP_TABLES, TRANSLATE_TABLES, PRODUCT_COLUMN

# Test case data, each section consists of list of tuples of original and correctly translated SQL statements
data = {
    # non-translated SELECTs
    'system_select_nontranslated' : [
        (
"""SELECT id,
               name,
               value
        FROM repository
        WHERE name IN ('alias',
                       'description',
                       'dir',
                       'hidden',
                       'name',
                       'type',
                       'url')""",
"""SELECT id,
               name,
               value
        FROM repository
        WHERE name IN ('alias',
                       'description',
                       'dir',
                       'hidden',
                       'name',
                       'type',
                       'url')"""
        ),
    ],

    # translated SELECTs
    'system_select_translated' : [
        (
"""SELECT TYPE, id,
                     filename,
                     time,
                     description,
                     author
        FROM attachment
        WHERE time > %s
          AND time < %s
          AND TYPE = %s""",
"""SELECT TYPE, id,
                     filename,
                     time,
                     description,
                     author
        FROM (SELECT * FROM attachment WHERE product='PRODUCT') AS attachment
        WHERE time > %s
          AND time < %s
          AND TYPE = %s"""
        ),
        (
"""SELECT name,
               due,
               completed,
               description
        FROM milestone
        WHERE name=%s""",
"""SELECT name,
               due,
               completed,
               description
        FROM (SELECT * FROM milestone WHERE product='PRODUCT') AS milestone
        WHERE name=%s"""
        ),
        (
"""SELECT COALESCE(component, ''),
               count(COALESCE(component, ''))
        FROM ticket
        GROUP BY COALESCE(component, '')""",
"""SELECT COALESCE(component, ''),
               count(COALESCE(component, ''))
        FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket
        GROUP BY COALESCE(component, '')"""
        ),
        (
"""SELECT id, time, reporter, TYPE, summary,
                                         description
        FROM ticket
        WHERE time>=%s
          AND time<=%s""",
"""SELECT id, time, reporter, TYPE, summary,
                                         description
        FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket
        WHERE time>=%s
          AND time<=%s"""
        ),
        (
"""SELECT t.id,
               tc.time,
               tc.author,
               t.type,
               t.summary,
               tc.field,
               tc.oldvalue,
               tc.newvalue
        FROM ticket_change tc
        INNER JOIN ticket t ON t.id = tc.ticket
        AND tc.time>=1351375199999999
        AND tc.time<=1354057199999999
        ORDER BY tc.time""",
"""SELECT t.id,
               tc.time,
               tc.author,
               t.type,
               t.summary,
               tc.field,
               tc.oldvalue,
               tc.newvalue
        FROM (SELECT * FROM ticket_change WHERE product='PRODUCT') AS tc
        INNER JOIN (SELECT * FROM ticket WHERE product='PRODUCT') AS t ON t.id = tc.ticket
        AND tc.time>=1351375199999999
        AND tc.time<=1354057199999999
        ORDER BY tc.time"""
        ),
        (
"""SELECT COUNT(*)
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.owner AS OWNER,
                  t.status AS status,
                  t.priority AS priority,
                  t.milestone AS milestone,
                  t.time AS time,
                  t.changetime AS changetime,
                  priority.value AS priority_value
           FROM ticket AS t
           LEFT OUTER JOIN enum AS priority ON (priority.type='priority'
                                                AND priority.name=priority)
           LEFT OUTER JOIN milestone ON (milestone.name=milestone)
           WHERE ((COALESCE(t.status,'')!=%s)
                  AND (COALESCE(t.OWNER,'')=%s))
           ORDER BY COALESCE(t.milestone,'')='',
                    COALESCE(milestone.completed,0)=0,
                    milestone.completed,
                    COALESCE(milestone.due,0)=0,
                    milestone.due,
                    t.milestone,
                    COALESCE(priority.value,'')='' DESC,CAST(priority.value AS integer) DESC,t.id) AS x""",
"""SELECT COUNT(*)
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.owner AS OWNER,
                  t.status AS status,
                  t.priority AS priority,
                  t.milestone AS milestone,
                  t.time AS time,
                  t.changetime AS changetime,
                  priority.value AS priority_value
           FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
           LEFT OUTER JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS priority ON (priority.type='priority'
                                                AND priority.name=priority)
           LEFT OUTER JOIN (SELECT * FROM milestone WHERE product='PRODUCT') AS milestone ON (milestone.name=milestone)
           WHERE ((COALESCE(t.status,'')!=%s)
                  AND (COALESCE(t.OWNER,'')=%s))
           ORDER BY COALESCE(t.milestone,'')='',
                    COALESCE(milestone.completed,0)=0,
                    milestone.completed,
                    COALESCE(milestone.due,0)=0,
                    milestone.due,
                    t.milestone,
                    COALESCE(priority.value,'')='' DESC,CAST(priority.value AS integer) DESC,t.id) AS x"""
        ),
        (
"""SELECT t.id AS id,
               t.summary AS summary,
               t.owner AS OWNER,
               t.status AS status,
               t.priority AS priority,
               t.milestone AS milestone,
               t.time AS time,
               t.changetime AS changetime,
               priority.value AS priority_value
        FROM ticket AS t
        LEFT OUTER JOIN enum AS priority ON (priority.type='priority'
                                             AND priority.name=priority)
        LEFT OUTER JOIN milestone ON (milestone.name=milestone)
        WHERE ((COALESCE(t.status,'')!=%s)
               AND (COALESCE(t.OWNER,'')=%s))
        ORDER BY COALESCE(t.milestone,'')='',
                 COALESCE(milestone.completed,0)=0,
                 milestone.completed,
                 COALESCE(milestone.due,0)=0,
                 milestone.due,
                 t.milestone,
                 COALESCE(priority.value,'')='' DESC,
                 CAST(priority.value AS integer) DESC,t.id""",
"""SELECT t.id AS id,
               t.summary AS summary,
               t.owner AS OWNER,
               t.status AS status,
               t.priority AS priority,
               t.milestone AS milestone,
               t.time AS time,
               t.changetime AS changetime,
               priority.value AS priority_value
        FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
        LEFT OUTER JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS priority ON (priority.type='priority'
                                             AND priority.name=priority)
        LEFT OUTER JOIN (SELECT * FROM milestone WHERE product='PRODUCT') AS milestone ON (milestone.name=milestone)
        WHERE ((COALESCE(t.status,'')!=%s)
               AND (COALESCE(t.OWNER,'')=%s))
        ORDER BY COALESCE(t.milestone,'')='',
                 COALESCE(milestone.completed,0)=0,
                 milestone.completed,
                 COALESCE(milestone.due,0)=0,
                 milestone.due,
                 t.milestone,
                 COALESCE(priority.value,'')='' DESC,
                 CAST(priority.value AS integer) DESC,t.id"""
        ),
       (
"""SELECT COUNT(*)
        FROM
          (SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                     time AS created,
                                                                                                                     changetime AS _changetime,
                                                                                                                                    description AS _description,
                                                                                                                                                    reporter AS _reporter
           FROM ticket t
           LEFT JOIN enum p ON p.name = t.priority
           AND p.TYPE = 'priority'
           WHERE status <> 'closed'
           ORDER BY CAST(p.value AS integer),
                    milestone,
                    t.TYPE, time ) AS tab""",
"""SELECT COUNT(*)
        FROM
          (SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                     time AS created,
                                                                                                                     changetime AS _changetime,
                                                                                                                                    description AS _description,
                                                                                                                                                    reporter AS _reporter
           FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
           LEFT JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS p  ON p.name = t.priority
           AND p.TYPE = 'priority'
           WHERE status <> 'closed'
           ORDER BY CAST(p.value AS integer),
                    milestone,
                    t.TYPE, time ) AS tab"""
       ),
        (
"""SELECT COUNT(*)
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.status AS status,
                  t.type AS TYPE,
                  t.priority AS priority,
                  t.product AS product,
                  t.milestone AS milestone,
                  t.time AS time,
                  t.changetime AS changetime,
                  t.owner AS OWNER,
                  priority.value AS priority_value
           FROM ticket AS t
           LEFT OUTER JOIN enum AS priority ON (priority.TYPE='priority'
                                                AND priority.name=priority)
           WHERE ((COALESCE(t.status,'')!=%s)
                  AND (COALESCE(t.OWNER,'')=%s))
           ORDER BY COALESCE(priority.value,'')='',
                                                CAST(priority.value AS integer),
                                                t.id) AS x""",
"""SELECT COUNT(*)
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.status AS status,
                  t.type AS TYPE,
                  t.priority AS priority,
                  t.product AS product,
                  t.milestone AS milestone,
                  t.time AS time,
                  t.changetime AS changetime,
                  t.owner AS OWNER,
                  priority.value AS priority_value
           FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
           LEFT OUTER JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS priority ON (priority.TYPE='priority'
                                                AND priority.name=priority)
           WHERE ((COALESCE(t.status,'')!=%s)
                  AND (COALESCE(t.OWNER,'')=%s))
           ORDER BY COALESCE(priority.value,'')='',
                                                CAST(priority.value AS integer),
                                                t.id) AS x"""
        ),
        (
"""SELECT t.id AS id,
               t.summary AS summary,
               t.status AS status,
               t.type AS TYPE,
               t.priority AS priority,
               t.product AS product,
               t.milestone AS milestone,
               t.time AS time,
               t.changetime AS changetime,
               t.owner AS OWNER,
               priority.value AS priority_value
        FROM ticket AS t
        LEFT OUTER JOIN enum AS priority ON (priority.TYPE='priority'
                                             AND priority.name=priority)
        WHERE ((COALESCE(t.status,'')!=%s)
               AND (COALESCE(t.OWNER,'')=%s))
        ORDER BY COALESCE(priority.value,'')='',
                                             CAST(priority.value AS integer),
                                             t.id""",
"""SELECT t.id AS id,
               t.summary AS summary,
               t.status AS status,
               t.type AS TYPE,
               t.priority AS priority,
               t.product AS product,
               t.milestone AS milestone,
               t.time AS time,
               t.changetime AS changetime,
               t.owner AS OWNER,
               priority.value AS priority_value
        FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
        LEFT OUTER JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS priority ON (priority.TYPE='priority'
                                             AND priority.name=priority)
        WHERE ((COALESCE(t.status,'')!=%s)
               AND (COALESCE(t.OWNER,'')=%s))
        ORDER BY COALESCE(priority.value,'')='',
                                             CAST(priority.value AS integer),
                                             t.id"""
        ),
        (
"""SELECT *
        FROM
          (SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                     time AS created,
                                                                                                                     changetime AS _changetime,
                                                                                                                                    description AS _description,
                                                                                                                                                    reporter AS _reporter
           FROM ticket t
           LEFT JOIN enum p ON p.name = t.priority
           AND p.TYPE = 'priority'
           WHERE status <> 'closed'
           ORDER BY CAST(p.value AS integer),
                    milestone,
                    t.TYPE, time ) AS tab LIMIT 1""",
"""SELECT *
        FROM
          (SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                     time AS created,
                                                                                                                     changetime AS _changetime,
                                                                                                                                    description AS _description,
                                                                                                                                                    reporter AS _reporter
           FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
           LEFT JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS p  ON p.name = t.priority
           AND p.TYPE = 'priority'
           WHERE status <> 'closed'
           ORDER BY CAST(p.value AS integer),
                    milestone,
                    t.TYPE, time ) AS tab LIMIT 1"""
        ),
        (
"""SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                  time AS created,
                                                                                                                  changetime AS _changetime,
                                                                                                                  description AS _description,
                                                                                                                  reporter AS _reporter
        FROM ticket t
        LEFT JOIN enum p ON p.name = t.priority
        AND p.TYPE = 'priority'
        WHERE status <> 'closed'
        ORDER BY CAST(p.value AS integer),
                 milestone,
                 t.TYPE, time""",
"""SELECT p.value AS __color__, id AS ticket, summary, component, VERSION, milestone, t.type AS TYPE, OWNER, status,
                                                                                                                  time AS created,
                                                                                                                  changetime AS _changetime,
                                                                                                                  description AS _description,
                                                                                                                  reporter AS _reporter
        FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
        LEFT JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS p ON p.name = t.priority
        AND p.TYPE = 'priority'
        WHERE status <> 'closed'
        ORDER BY CAST(p.value AS integer),
                 milestone,
                 t.TYPE, time"""
        ),
        (
"""SELECT COALESCE(version, '') ,
               count(COALESCE(version, ''))
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.owner AS owner,
                  t.type AS type,
                  t.status AS status,
                  t.priority AS priority,
                  t.milestone AS milestone,
                  t.version AS version,
                  t.time AS time,
                  t.changetime AS changetime,
                  t.product AS product,
                  priority.value AS priority_value
           FROM
             (SELECT *
              FROM ticket
              WHERE product="default") AS t
           LEFT OUTER JOIN
             (SELECT *
              FROM enum
              WHERE product="default") AS priority ON (priority.type='priority'
                                                       AND priority.name=priority)
           LEFT OUTER JOIN
             (SELECT *
              FROM version
              WHERE product="default") AS version ON (version.name=version)
           WHERE ((COALESCE(t.product,'')='default'))
           ORDER BY COALESCE(t.version,'')='',
                    COALESCE(version.time,0)=0,version.time,
                    t.version,COALESCE(priority.value,'')='',
                    CAST(priority.value AS integer),
                    t.id) AS foo
        GROUP BY COALESCE(version, '')""",
"""SELECT COALESCE(version, '') ,
               count(COALESCE(version, ''))
        FROM
          (SELECT t.id AS id,
                  t.summary AS summary,
                  t.owner AS owner,
                  t.type AS type,
                  t.status AS status,
                  t.priority AS priority,
                  t.milestone AS milestone,
                  t.version AS version,
                  t.time AS time,
                  t.changetime AS changetime,
                  t.product AS product,
                  priority.value AS priority_value
           FROM
             (SELECT *
              FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket
              WHERE product="default") AS t
           LEFT OUTER JOIN
             (SELECT *
              FROM (SELECT * FROM enum WHERE product='PRODUCT') AS enum
              WHERE product="default") AS priority ON (priority.type='priority'
                                                       AND priority.name=priority)
           LEFT OUTER JOIN
             (SELECT *
              FROM (SELECT * FROM version WHERE product='PRODUCT') AS version
              WHERE product="default") AS version ON (version.name=version)
           WHERE ((COALESCE(t.product,'')='default'))
           ORDER BY COALESCE(t.version,'')='',
                    COALESCE(version.time,0)=0,version.time,
                    t.version,COALESCE(priority.value,'')='',
                    CAST(priority.value AS integer),
                    t.id) AS foo
        GROUP BY COALESCE(version, '')"""
        ),
        (
"""SELECT w1.name, w1.time, w1.author, w1.text
        FROM wiki w1,(SELECT name, max(version) AS ver
        FROM wiki GROUP BY name) w2
        WHERE w1.version = w2.ver AND w1.name = w2.name
        AND (w1.name LIKE %s ESCAPE '/' OR w1.author LIKE %s ESCAPE '/' OR w1.text LIKE %s ESCAPE '/')""",
"""SELECT w1.name, w1.time, w1.author, w1.text
        FROM (SELECT * FROM wiki WHERE product='PRODUCT') AS w1,(SELECT name, max(version) AS ver
        FROM (SELECT * FROM wiki WHERE product='PRODUCT') AS wiki GROUP BY name)  AS w2
        WHERE w1.version = w2.ver AND w1.name = w2.name
        AND (w1.name LIKE %s ESCAPE '/' OR w1.author LIKE %s ESCAPE '/' OR w1.text LIKE %s ESCAPE '/')"""
        ),
        (
"""INSERT INTO ticket(id, type, time, changetime, component, severity, priority,
                           owner, reporter, cc, version, milestone, status, resolution,
                           summary, description, keywords)
          SELECT id, 'defect', time, changetime, component, severity, priority, owner,
                 reporter, cc, version, milestone, status, resolution, summary,
                 description, keywords FROM ticket_old
          WHERE COALESCE(severity,'') <> 'enhancement'""",
"""INSERT INTO ticket(id, type, time, changetime, component, severity, priority,
                           owner, reporter, cc, version, milestone, status, resolution,
                           summary, description, keywords, product)
          SELECT id, 'defect', time, changetime, component, severity, priority, owner,
                 reporter, cc, version, milestone, status, resolution, summary,
                 description, keywords, 'PRODUCT' FROM (SELECT * FROM "PRODUCT_ticket_old") AS ticket_old
          WHERE COALESCE(severity,'') <> 'enhancement'"""
        ),
        (
"""INSERT INTO ticket(id, type, time, changetime, component, severity, priority,
                               owner, reporter, cc, version, milestone, status, resolution,
                               summary, description, keywords)
              SELECT id, 'enhancement', time, changetime, component, 'normal', priority,
                     owner, reporter, cc, version, milestone, status, resolution, summary,
                     description, keywords FROM ticket_old
              WHERE severity = 'enhancement'""",
"""INSERT INTO ticket(id, type, time, changetime, component, severity, priority,
                               owner, reporter, cc, version, milestone, status, resolution,
                               summary, description, keywords, product)
              SELECT id, 'enhancement', time, changetime, component, 'normal', priority,
                     owner, reporter, cc, version, milestone, status, resolution, summary,
                     description, keywords, 'PRODUCT' FROM (SELECT * FROM "PRODUCT_ticket_old") AS ticket_old
              WHERE severity = 'enhancement'"""
        ),
        (
"""SELECT COUNT(*) FROM (
        SELECT  __color__, __group,
               (CASE
                 WHEN __group = 1 THEN 'Accepted'
                 WHEN __group = 2 THEN 'Owned'
                 WHEN __group = 3 THEN 'Reported'
                 ELSE 'Commented' END) AS __group__,
               ticket, summary, component, version, milestone,
               type, priority, created, _changetime, _description,
               _reporter
        FROM (
         SELECT DISTINCT CAST(p.value AS integer) AS __color__,
              (CASE
                 WHEN owner = %s AND status = 'accepted' THEN 1
                 WHEN owner = %s THEN 2
                 WHEN reporter = %s THEN 3
                 ELSE 4 END) AS __group,
               t.id AS ticket, summary, component, version, milestone,
               t.type AS type, priority, t.time AS created,
               t.changetime AS _changetime, description AS _description,
               reporter AS _reporter
          FROM ticket t
          LEFT JOIN enum p ON p.name = t.priority AND p.type = 'priority'
          LEFT JOIN ticket_change tc ON tc.ticket = t.id AND tc.author = %s
                                        AND tc.field = 'comment'
          WHERE t.status <> 'closed'
                AND (owner = %s OR reporter = %s OR author = %s)
        ) AS sub
        ORDER BY __group, __color__, milestone, type, created

        ) AS tab""",
"""SELECT COUNT(*) FROM (
        SELECT  __color__, __group,
               (CASE
                 WHEN __group = 1 THEN 'Accepted'
                 WHEN __group = 2 THEN 'Owned'
                 WHEN __group = 3 THEN 'Reported'
                 ELSE 'Commented' END) AS __group__,
               ticket, summary, component, version, milestone,
               type, priority, created, _changetime, _description,
               _reporter
        FROM (
         SELECT DISTINCT CAST(p.value AS integer) AS __color__,
              (CASE
                 WHEN owner = %s AND status = 'accepted' THEN 1
                 WHEN owner = %s THEN 2
                 WHEN reporter = %s THEN 3
                 ELSE 4 END) AS __group,
               t.id AS ticket, summary, component, version, milestone,
               t.type AS type, priority, t.time AS created,
               t.changetime AS _changetime, description AS _description,
               reporter AS _reporter
          FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS t
          LEFT JOIN (SELECT * FROM enum WHERE product='PRODUCT') AS p  ON p.name = t.priority AND p.type = 'priority'
          LEFT JOIN (SELECT * FROM ticket_change WHERE product='PRODUCT') AS tc  ON tc.ticket = t.id AND tc.author = %s
                                        AND tc.field = 'comment'
          WHERE t.status <> 'closed'
                AND (owner = %s OR reporter = %s OR author = %s)
        ) AS sub
        ORDER BY __group, __color__, milestone, type, created

        ) AS tab"""
        ),
    ],

    # custom table SELECTs
    'custom_select' : [
        (
"""SELECT bklg_id, count(*) as total
    FROM backlog_ticket
    WHERE tkt_order IS NULL OR tkt_order > -1
    GROUP BY bklg_id
""",
"""SELECT bklg_id, count(*) as total
    FROM (SELECT * FROM "PRODUCT_backlog_ticket") AS backlog_ticket
    WHERE tkt_order IS NULL OR tkt_order > -1
    GROUP BY bklg_id
"""
        ),
        (
"""SELECT bt.bklg_id, t.status, count(*) as total
    FROM backlog_ticket bt, ticket t
    WHERE t.id = bt.tkt_id
    AND (bt.tkt_order IS NULL OR bt.tkt_order > -1)
    GROUP BY bklg_id, status""",
"""SELECT bt.bklg_id, t.status, count(*) as total
    FROM (SELECT * FROM "PRODUCT_backlog_ticket") AS bt, (SELECT * FROM ticket WHERE product='PRODUCT') AS t
    WHERE t.id = bt.tkt_id
    AND (bt.tkt_order IS NULL OR bt.tkt_order > -1)
    GROUP BY bklg_id, status"""
        ),
    ],

    # non-translated INSERTs
    'system_insert_nontranslated' : [
        (
"""INSERT INTO session VALUES (%s,%s,0)""",
"""INSERT INTO session VALUES (%s,%s,0)"""
        ),
    ],

    # translated INSERTs
    'system_insert_translated' : [
        (
"""INSERT INTO ticket_custom (ticket, name, value)
          SELECT id, 'totalhours', '0' FROM ticket WHERE id NOT IN (
            SELECT ticket from ticket_custom WHERE name='totalhours'
          )""",
"""INSERT INTO ticket_custom (ticket, name, value, product)
              SELECT id, 'totalhours', '0', 'PRODUCT' FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket WHERE id NOT IN (
                SELECT ticket from (SELECT * FROM ticket_custom WHERE product='PRODUCT') AS ticket_custom WHERE name='totalhours'
              )"""
        ),
        (
"""INSERT INTO ticket_custom (ticket, name, value)
                    SELECT id, 'totalhours', '0' FROM ticket WHERE id NOT IN (
                    SELECT ticket from ticket_custom WHERE name='totalhours')""",
"""INSERT INTO ticket_custom (ticket, name, value, product)
                        SELECT id, 'totalhours', '0', 'PRODUCT' FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket WHERE id NOT IN (
                        SELECT ticket from (SELECT * FROM ticket_custom WHERE product='PRODUCT') AS ticket_custom WHERE name='totalhours')"""
        ),
        (
"""INSERT INTO session (sid, last_visit, authenticated)
                SELECT distinct s.sid,COALESCE(%s,0),s.authenticated
                FROM session_old AS s LEFT JOIN session_old AS s2
                ON (s.sid=s2.sid AND s2.var_name='last_visit')
                WHERE s.sid IS NOT NULL""",
"""INSERT INTO session (sid, last_visit, authenticated)
                SELECT distinct s.sid,COALESCE(%s,0),s.authenticated
                FROM (SELECT * FROM "PRODUCT_session_old") AS s LEFT JOIN (SELECT * FROM "PRODUCT_session_old") AS s2
                ON (s.sid=s2.sid AND s2.var_name='last_visit')
                WHERE s.sid IS NOT NULL"""
        ),
        (
"""INSERT INTO session_attribute (sid, authenticated, name, value)
        SELECT s.sid, s.authenticated, s.var_name, s.var_value
        FROM session_old s
        WHERE s.var_name <> 'last_visit' AND s.sid IS NOT NULL""",
"""INSERT INTO session_attribute (sid, authenticated, name, value)
        SELECT s.sid, s.authenticated, s.var_name, s.var_value
        FROM (SELECT * FROM "PRODUCT_session_old") AS s
        WHERE s.var_name <> 'last_visit' AND s.sid IS NOT NULL"""
        ),
        (
"""INSERT INTO wiki(version, name, time, author, ipnr, text)
                              SELECT 1 + COALESCE(max(version), 0), %s, %s, 'trac',
                                     '127.0.0.1', %s FROM wiki WHERE name=%s""",
"""INSERT INTO wiki(version, name, time, author, ipnr, text, product)
                              SELECT 1 + COALESCE(max(version), 0), %s, %s, 'trac',
                                     '127.0.0.1', %s, 'PRODUCT' FROM (SELECT * FROM wiki WHERE product='PRODUCT') AS wiki WHERE name=%s"""
        ),
        (
"""INSERT INTO permission VALUES ('dev','WIKI_VIEW')""",
"""INSERT INTO permission VALUES ('dev','WIKI_VIEW','PRODUCT')"""
        ),
        (
"""INSERT INTO permission (username, action) VALUES ('dev','WIKI_VIEW')""",
"""INSERT INTO permission (username, action, product) VALUES ('dev','WIKI_VIEW','PRODUCT')"""
        ),
    ],

    'custom_insert' : [
        (
"""INSERT INTO node_change (rev,path,kind,change,base_path,base_rev)
            SELECT rev,path,kind,change,base_path,base_rev FROM node_change_old""",
"""INSERT INTO node_change (rev,path,kind,change,base_path,base_rev)
            SELECT rev,path,kind,change,base_path,base_rev FROM (SELECT * FROM "PRODUCT_node_change_old") AS node_change_old"""
        ),
    ],

    # translated UPDATEs
    'system_update_translated' : [
        (
"""UPDATE ticket SET changetime=%s WHERE id=%s""",
"""UPDATE ticket SET changetime=%s WHERE product='PRODUCT' AND id=%s"""
        ),
        (
"""UPDATE ticket SET changetime=(
                          SELECT time FROM ticket_change WHERE ticket=%s
                          UNION
                          SELECT time FROM (
                              SELECT time FROM ticket WHERE id=%s LIMIT 1) AS t
                          ORDER BY time DESC LIMIT 1)
                          WHERE id=%s""",
"""UPDATE ticket SET changetime=(
                          SELECT time FROM (SELECT * FROM ticket_change WHERE product='PRODUCT') AS ticket_change WHERE ticket=%s
                          UNION
                          SELECT time FROM (
                              SELECT time FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket WHERE id=%s LIMIT 1) AS t
                          ORDER BY time DESC LIMIT 1)
                          WHERE product='PRODUCT' AND id=%s"""
        ),
        (
"""UPDATE component SET name=%s,owner=%s, description=%s
                          WHERE name=%s""",
"""UPDATE component SET name=%s,owner=%s, description=%s
                          WHERE product='PRODUCT' AND name=%s"""
        ),
        (
"""UPDATE milestone
                          SET name=%s, due=%s, completed=%s, description=%s
                          WHERE name=%s""",
"""UPDATE milestone
                          SET name=%s, due=%s, completed=%s, description=%s
                          WHERE product='PRODUCT' AND name=%s"""
        ),
        (
"""UPDATE wiki
        SET text=%s
            WHERE name=%s""",
"""UPDATE wiki
        SET text=%s
            WHERE product='PRODUCT' AND name=%s"""
        ),
        (
"""UPDATE ticket SET product=%s
                                  WHERE product=%s""",
"""UPDATE ticket SET product=%s
                                  WHERE product='PRODUCT' AND product=%s"""
        ),
        (
"""UPDATE ticket set changetime=%s where id=%s""",
"""UPDATE ticket set changetime=%s where product='PRODUCT' AND id=%s"""
        ),
        (
"""UPDATE
                                milestone
                           SET
                                id_project='%s' WHERE milestone='%s'""",
"""UPDATE
                                milestone
                           SET
                                id_project='%s' WHERE product='PRODUCT' AND milestone='%s'"""
        ),
        (
"""UPDATE ticket_change  SET  newvalue=%s
                               WHERE ticket=%s and author=%s and time=%s and field=%s""",
"""UPDATE ticket_change  SET  newvalue=%s
                               WHERE product='PRODUCT' AND ticket=%s and author=%s and time=%s and field=%s"""
        ),
        (
"""UPDATE ticket_change  SET oldvalue=%s, newvalue=%s
                               WHERE ticket=%s and author=%s and time=%s and field=%s""",
"""UPDATE ticket_change  SET oldvalue=%s, newvalue=%s
                               WHERE product='PRODUCT' AND ticket=%s and author=%s and time=%s and field=%s"""
        ),
        (
"""UPDATE
                                ticket_custom
                              SET
                                value = '%s'
                              WHERE
                                name = 'project' AND value = '%s'""",
"""UPDATE
                                ticket_custom
                              SET
                                value = '%s'
                              WHERE
                                product='PRODUCT' AND name = 'project' AND value = '%s'"""
        ),
    ],

    # non-translated UPDATEs
    'system_update_nontranslated' : [
        (
"""UPDATE  session_attribute
                            SET value='1'
                        WHERE   sid=%s
                            AND name='password_refreshed'""",
"""UPDATE  session_attribute
                            SET value='1'
                        WHERE   sid=%s
                            AND name='password_refreshed'"""
        ),
        (
"""UPDATE  session_attribute
                    SET value=%s""",
"""UPDATE  session_attribute
                    SET value=%s"""
        ),
        (
"""UPDATE  auth_cookie
                            SET time=%s
                        WHERE   cookie=%s""",
"""UPDATE  auth_cookie
                            SET time=%s
                        WHERE   cookie=%s"""
        ),
    ],

    # custom (plugin) table UPDATEs
    'custom_update' : [
        (
"""UPDATE subscription
                       SET format=%s
                     WHERE distributor=%s
                       AND sid=%s
                       AND authenticated=%s""",
"""UPDATE "PRODUCT_subscription"
                       SET format=%s
                     WHERE distributor=%s
                       AND sid=%s
                       AND authenticated=%s"""
        ),
        (
"""UPDATE subscription
                       SET changetime=CURRENT_TIMESTAMP,
                           priority=%s
                     WHERE id=%s""",
"""UPDATE "PRODUCT_subscription"
                       SET changetime=CURRENT_TIMESTAMP,
                           priority=%s
                     WHERE id=%s"""
        ),
        (
"""UPDATE backlog_ticket SET tkt_order = NULL WHERE tkt_id = %s""",
"""UPDATE "PRODUCT_backlog_ticket" SET tkt_order = NULL WHERE tkt_id = %s"""
        ),
        (
"""UPDATE backlog_ticket SET tkt_order = -1
                      WHERE bklg_id = %s
                      AND tkt_id IN
                      (SELECT id FROM ticket
                       WHERE status = 'closed')""",
"""UPDATE "PRODUCT_backlog_ticket" SET tkt_order = -1
                      WHERE bklg_id = %s
                      AND tkt_id IN
                      (SELECT id FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket
                       WHERE status = 'closed')"""
        ),
        (
"""UPDATE backlog_ticket SET tkt_order = -1
                         WHERE bklg_id = %s
                         AND tkt_id IN (SELECT id FROM ticket
                          WHERE status = 'closed')""",
"""UPDATE "PRODUCT_backlog_ticket" SET tkt_order = -1
                         WHERE bklg_id = %s
                         AND tkt_id IN (SELECT id FROM (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket
                          WHERE status = 'closed')"""
        ),
        (
"""UPDATE estimate SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s
        WHERE id=%s""",
"""UPDATE "PRODUCT_estimate" SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s
        WHERE id=%s"""
        ),
        (
"""UPDATE estimate_line_item SET estimate_id=%s ,
          description=%s, low=%s, high=%s
        WHERE id=%s""",
"""UPDATE "PRODUCT_estimate_line_item" SET estimate_id=%s ,
          description=%s, low=%s, high=%s
        WHERE id=%s"""
        ),
        (
"""UPDATE estimate SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s,
           diffcomment=%s, saveepoch=%s
        WHERE id=%s""",
"""UPDATE "PRODUCT_estimate" SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s,
           diffcomment=%s, saveepoch=%s
        WHERE id=%s"""
        ),
        (
"""UPDATE estimate_line_item SET estimate_id=%s ,
          description=%s, low=%s, high=%s
        WHERE id=%s""",
"""UPDATE "PRODUCT_estimate_line_item" SET estimate_id=%s ,
          description=%s, low=%s, high=%s
        WHERE id=%s"""
        ),
        (
"""UPDATE estimate SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s,
           diffcomment=%s, saveepoch=%s
        WHERE id=%s""",
"""UPDATE "PRODUCT_estimate" SET rate=%s, variability=%s, communication=%s, tickets=%s, comment=%s,
           diffcomment=%s, saveepoch=%s
        WHERE id=%s"""
        ),
    ],

    # custom CREATE TABLE
    'custom_create_table' : [
        (
"""CREATE TABLE estimate(
            id integer PRIMARY KEY,
        rate DECIMAL,
        variability DECIMAL,
        communication DECIMAL,
        tickets VARCHAR(512),
        comment VARCHAR(8000)
    )""",
"""CREATE TABLE "PRODUCT_estimate"(
            id integer PRIMARY KEY,
        rate DECIMAL,
        variability DECIMAL,
        communication DECIMAL,
        tickets VARCHAR(512),
        comment VARCHAR(8000)
    )"""
        ),
        (
"""CREATE TABLE estimate_line_item(
        id integer PRIMARY KEY,
                           estimate_id integer,
                                       description VARCHAR(2048),
                                                   low DECIMAL,
                                                       high DECIMAL
    )""",
"""CREATE TABLE "PRODUCT_estimate_line_item"(
        id integer PRIMARY KEY,
                           estimate_id integer,
                                       description VARCHAR(2048),
                                                   low DECIMAL,
                                                       high DECIMAL
    )"""
        ),
        (
"""CREATE TABLE backlog_ticket (bklg_id INTEGER NOT NULL,"
                                                          " tkt_id INTEGER NOT NULL,"
                                                          " tkt_order REAL,"
                                                          " PRIMARY KEY(bklg_id, tkt_id))""",
"""CREATE TABLE "PRODUCT_backlog_ticket" (bklg_id INTEGER NOT NULL,"
                                                          " tkt_id INTEGER NOT NULL,"
                                                          " tkt_order REAL,"
                                                          " PRIMARY KEY(bklg_id, tkt_id))"""
        ),
        (
"""CREATE TEMPORARY TABLE backlog_ticket (bklg_id INTEGER NOT NULL,"
                                         " tkt_id INTEGER NOT NULL,"
                                         " tkt_order REAL,"
                                         " PRIMARY KEY(bklg_id, tkt_id))""",
"""CREATE TEMPORARY TABLE "PRODUCT_backlog_ticket" (bklg_id INTEGER NOT NULL,"
                                         " tkt_id INTEGER NOT NULL,"
                                         " tkt_order REAL,"
                                         " PRIMARY KEY(bklg_id, tkt_id))"""
        ),
        (
"""CREATE TEMPORARY TABLE table_old AS SELECT * FROM table""",
"""CREATE TEMPORARY TABLE "PRODUCT_table_old" AS SELECT * FROM"""
""" (SELECT * FROM "PRODUCT_table") AS table""",
        ),
    ],

    # custom ALTER TABLE
    'custom_alter_table' : [
        (
"""ALTER TABLE estimate ADD COLUMN diffcomment text""",
"""ALTER TABLE "PRODUCT_estimate" ADD COLUMN diffcomment text"""
        ),
        (
"""ALTER TABLE estimate ADD COLUMN saveepoch int""",
"""ALTER TABLE "PRODUCT_estimate" ADD COLUMN saveepoch int"""
        ),
    ],

    #lowercase select (#548)
    'lowercase_tokens': [
        (
"""select * from ticket""",
"""select * from (SELECT * FROM ticket WHERE product='PRODUCT') AS ticket"""
        ),
        (
"""create temporary table table_old as select * from table""",
"""create temporary table "PRODUCT_table_old" as select * from (SELECT * FROM "PRODUCT_table") AS table""",
        )
    ],
    # insert with specified product (#601)
    'insert_with_product': [
        (
"""INSERT INTO ticket (summary, product) VALUES ('S', 'swlcu')""",
"""INSERT INTO ticket (summary, product) VALUES ('S', 'swlcu')"""
        ),
    ],

}

class DbCursorTestCase(unittest.TestCase):
    """Unit tests covering the BloodhoundProductSQLTranslate"""
    def setUp(self):
        self.translator = BloodhoundProductSQLTranslate(SKIP_TABLES, TRANSLATE_TABLES, PRODUCT_COLUMN, 'PRODUCT')
        for section in data.keys():
            if not getattr(self, 'test_%s' % section, None):
                raise Exception("Section '%s' not covered in test case" % section)

    def tearDown(self):
        pass

    def _run_test(self, section):
        for (sql, translated_sql_check) in data[section]:
            translated_sql = self.translator.translate(sql)
            stripped_sql_check = '\n'.join([l.strip() for l in translated_sql_check.splitlines()])
            stripped_translated_sql = '\n'.join([l.strip() for l in translated_sql.splitlines()])
            self.assertEquals(stripped_sql_check, stripped_translated_sql)

    def test_system_select_nontranslated(self):
        self._run_test('system_select_nontranslated')

    def test_system_select_translated(self):
        self._run_test('system_select_translated')

    def test_custom_select(self):
        self._run_test('custom_select')

    def test_system_insert_nontranslated(self):
        self._run_test('system_insert_nontranslated')

    def test_system_insert_translated(self):
        self._run_test('system_insert_translated')

    def test_custom_insert(self):
        self._run_test('custom_insert')

    def test_system_update_translated(self):
        self._run_test('system_update_translated')

    def test_system_update_nontranslated(self):
        self._run_test('system_update_nontranslated')

    def test_custom_update(self):
        self._run_test('custom_update')

    def test_custom_create_table(self):
        self._run_test('custom_create_table')

    def test_custom_alter_table(self):
        self._run_test('custom_alter_table')

    def test_lowercase_tokens(self):
        self._run_test('lowercase_tokens')

    def test_insert_with_product(self):
        self._run_test('insert_with_product')

if __name__ == '__main__':
    unittest.main()


