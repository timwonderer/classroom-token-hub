"""Normalize the two legitimate nondeterministic sources, then require byte equality."""
import os, re, subprocess, sys
base, S = sys.argv[1], sys.argv[2]
def q(db, sql):
    return subprocess.check_output(["psql", f"{base}/{db}", "-AtF|", "-c", sql], text=True).split("\n")[:-1]
old, new = "cth_era_v5_old_test", "cth_era_v5_new_test"
# users are matched on their username lookup digest (deterministic HMAC of the synthetic username)
key = "SELECT username_lookup_hash, id FROM users ORDER BY 1"
a = dict(r.split("|") for r in q(old, key)); b = dict(r.split("|") for r in q(new, key))
assert a.keys() == b.keys() and len(a) == 18, (len(a), len(b))
uuid_map = {a[k]: b[k] for k in a}
assert len(set(uuid_map.values())) == len(uuid_map)
ts = "SELECT DISTINCT created_at FROM issue_categories WHERE id IN (SELECT id FROM issue_categories ORDER BY id DESC LIMIT 3)"
ta, tb = q(old, ts), q(new, ts)
assert len(ta) == len(tb) == 1
dump_a = open(f"{S}/v5full_post_{old}.sql").read()
dump_b = open(f"{S}/v5full_post_{new}.sql").read()
pattern = re.compile("|".join(map(re.escape, uuid_map)))
norm_a = pattern.sub(lambda m: uuid_map[m.group(0)], dump_a)
# pg_dump prints timestamptz in the session zone; match the text form actually dumped.
fmt = lambda db: q(db, "SET TIME ZONE 'America/Los_Angeles'; " + ts)[-1]
norm_a = norm_a.replace(fmt(old), fmt(new))
changed = sum(1 for x, y in zip(dump_a.splitlines(), norm_a.splitlines()) if x != y)
print("users mapped:", len(uuid_map), "| lines normalized:", changed)
print("normalized dumps identical:", norm_a == dump_b)
if norm_a != dump_b:
    import difflib; print("".join(list(difflib.unified_diff(norm_a.splitlines(1), dump_b.splitlines(1)))[:40]))
