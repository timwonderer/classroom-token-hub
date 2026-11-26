SELECT 'schemas' AS k, string_agg(nspname, ',' ORDER BY nspname COLLATE "C") AS v FROM pg_namespace WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema'
UNION ALL SELECT 'rls_policies', count(*)::text FROM pg_policy
UNION ALL SELECT 'rls_enabled_tables', coalesce(string_agg(relname, ',' ORDER BY relname COLLATE "C"), '') FROM pg_class WHERE relrowsecurity AND relnamespace = 'public'::regnamespace
UNION ALL SELECT 'rules', count(*)::text FROM pg_rewrite r JOIN pg_class c ON c.oid = r.ev_class WHERE c.relnamespace = 'public'::regnamespace AND r.rulename <> '_RETURN'
UNION ALL SELECT 'comments_md5', md5(coalesce(string_agg(c.relname || ':' || d.objsubid || ':' || d.description, '|' ORDER BY c.relname COLLATE "C", d.objsubid), '')) FROM pg_description d JOIN pg_class c ON c.oid = d.objoid AND d.classoid = 'pg_class'::regclass WHERE c.relnamespace = 'public'::regnamespace
UNION ALL SELECT 'column_collations', coalesce(string_agg(c.relname || '.' || a.attname || '=' || co.collname, ',' ORDER BY c.relname COLLATE "C", a.attname COLLATE "C"), '') FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_collation co ON co.oid = a.attcollation WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'r' AND a.attnum > 0 AND co.collname <> 'default'
UNION ALL SELECT 'reloptions', coalesce(string_agg(relname || '=' || array_to_string(reloptions, ';'), ',' ORDER BY relname COLLATE "C"), '') FROM pg_class WHERE relnamespace = 'public'::regnamespace AND reloptions IS NOT NULL
UNION ALL SELECT 'event_triggers', count(*)::text FROM pg_event_trigger
UNION ALL SELECT 'db_settings', count(*)::text FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase WHERE d.datname = current_database()
UNION ALL SELECT 'public_tables', count(*)::text FROM pg_tables WHERE schemaname = 'public';
