SELECT string_agg(x || '=' || (x ~ '^ledger-credit:v1:[1-9][0-9]*$')::text, ' | ' ORDER BY ord) AS locator_pattern
FROM unnest(ARRAY['ledger-credit:v1:1','ledger-credit:v1:907','ledger-credit:v1:0','ledger-credit:v1:01','LEDGER-CREDIT:v1:1','ledger-credit:V1:1','ledger-credit:v1:٣','ledger-credit:v1:１','ledger-credit:v1:1²','ledger-credit:v1:','ledger-credit:v1:12a']) WITH ORDINALITY AS t(x, ord)
