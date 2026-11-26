-- Catalog-only fingerprint of schema public. Reads no application rows.
WITH ns AS (SELECT oid FROM pg_namespace WHERE nspname = 'public'),
objs AS (
  SELECT 'column' AS kind, c.relname || '.' || a.attname AS name,
         format_type(a.atttypid, a.atttypmod) || CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END
         || coalesce(' DEFAULT ' || pg_get_expr(d.adbin, d.adrelid), '') || CASE WHEN a.attidentity <> '' THEN ' IDENTITY ' || a.attidentity ELSE '' END AS def
  FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
  LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
  WHERE c.relnamespace = (SELECT oid FROM ns) AND c.relkind IN ('r','p','v','m') AND a.attnum > 0 AND NOT a.attisdropped
  UNION ALL
  SELECT 'relation', c.relname, c.relkind::text || CASE WHEN c.relkind IN ('v','m') THEN ' ' || pg_get_viewdef(c.oid) ELSE '' END
  FROM pg_class c WHERE c.relnamespace = (SELECT oid FROM ns) AND c.relkind IN ('r','p','v','m','S')
  UNION ALL
  SELECT 'constraint', cl.relname || '.' || co.conname, co.contype::text || ' ' || pg_get_constraintdef(co.oid) || CASE WHEN co.convalidated THEN '' ELSE ' [NOT VALIDATED]' END
  FROM pg_constraint co JOIN pg_class cl ON cl.oid = co.conrelid WHERE co.connamespace = (SELECT oid FROM ns)
  UNION ALL
  SELECT 'index', i.relname, pg_get_indexdef(i.oid)
  FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid WHERE i.relnamespace = (SELECT oid FROM ns)
  UNION ALL
  SELECT 'trigger', c.relname || '.' || t.tgname, pg_get_triggerdef(t.oid) || ' enabled=' || t.tgenabled
  FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid WHERE NOT t.tgisinternal AND c.relnamespace = (SELECT oid FROM ns)
  UNION ALL
  SELECT 'function', p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')', md5(pg_get_functiondef(p.oid))
  FROM pg_proc p WHERE p.pronamespace = (SELECT oid FROM ns)
  UNION ALL
  SELECT 'enum', t.typname, string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder)
  FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid WHERE t.typnamespace = (SELECT oid FROM ns) GROUP BY t.typname
  UNION ALL
  SELECT 'sequence', c.relname, format_type(s.seqtypid, NULL) || ' inc=' || s.seqincrement || ' min=' || s.seqmin || ' max=' || s.seqmax || ' cycle=' || s.seqcycle
  FROM pg_sequence s JOIN pg_class c ON c.oid = s.seqrelid WHERE c.relnamespace = (SELECT oid FROM ns)
  UNION ALL
  SELECT 'extension', extname, extversion FROM pg_extension
)
SELECT kind, count(*) AS n, md5(string_agg(name || '|' || md5(def), chr(10) ORDER BY name COLLATE "C")) AS kind_md5 FROM objs GROUP BY kind ORDER BY kind;
