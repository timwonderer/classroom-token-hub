WITH s(v) AS (VALUES ('apple'),('Apple'),('APPLE'),('_x'),('a-b'),('ab'),('a b'),('10'),('9'),('Zoë'),('zoe'),('Émile'),('emile'),('Ångström'),('王'),('😀'),('ß'),('İstanbul'))
SELECT 'order', string_agg(v, '|' ORDER BY v) FROM s
UNION ALL SELECT 'lower', string_agg(lower(v), '|' ORDER BY v COLLATE "C") FROM s
UNION ALL SELECT 'upper', string_agg(upper(v), '|' ORDER BY v COLLATE "C") FROM s
UNION ALL SELECT 'ilike_e_acute', string_agg(v, '|' ORDER BY v COLLATE "C") FROM s WHERE v ILIKE 'é%'
UNION ALL SELECT 'regex_alpha', string_agg(v, '|' ORDER BY v COLLATE "C") FROM s WHERE v ~ '^[[:alpha:]]+$'
UNION ALL SELECT 'equality_case', (SELECT count(*)::text FROM s a JOIN s b ON a.v = b.v)
UNION ALL SELECT 'like_prefix', string_agg(v, '|' ORDER BY v COLLATE "C") FROM s WHERE v LIKE 'a%'
UNION ALL SELECT 'datcollate', datcollate || '/' || datctype FROM pg_database WHERE datname = current_database();
