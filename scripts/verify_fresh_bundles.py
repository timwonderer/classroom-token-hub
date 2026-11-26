"""Prove every committed release bundle is derived from this checkout's migration lineage.

For each ``migrations/fresh/<revision>/`` the generator re-derives the bundle from the
committed lineage at ``--source-sha`` (a private PostgreSQL 14 cluster, no application
configuration) and the result must equal what is committed: ``schema.sql`` byte for
byte, and every derived manifest field. A bundle that was hand-edited, generated from
a different lineage, or left behind by a changed migration fails. Provenance fields
(``source_sha``, or ``release_sha`` in bundles generated before it was renamed) must
name a commit that is an ancestor of ``--source-sha``.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from fresh_database import ROOT, require
from generate_fresh_database import generate

# Manifest fields that are a function of the lineage and PostgreSQL 14 alone.
DERIVED = ("revision", "schema_sha256", "ddl_sha256", "empty_schema_sha256", "categories", "sequences")


def source_of(manifest):
    """The commit a bundle was derived from (``release_sha`` before the F2 rename)."""
    return manifest.get("source_sha") or manifest.get("release_sha")


def compare(committed_dir, derived_dir):
    """Every way the derived bundle differs from the committed one."""
    problems = []
    if (committed_dir / "schema.sql").read_bytes() != (derived_dir / "schema.sql").read_bytes():
        problems.append("schema.sql differs from the lineage's derivation")
    committed = json.loads((committed_dir / "manifest.json").read_text())
    derived = json.loads((derived_dir / "manifest.json").read_text())
    problems += [f"manifest {key} differs" for key in DERIVED if committed.get(key) != derived.get(key)]
    return problems


def verify(sha):
    bundles = sorted(p for p in (ROOT / "migrations" / "fresh").iterdir() if (p / "manifest.json").is_file())
    require(bundles, "no committed bundle to verify")
    failures = []
    for bundle in bundles:
        manifest = json.loads((bundle / "manifest.json").read_text())
        require(manifest.get("revision") == bundle.name, f"{bundle.name}: manifest names another revision")
        origin = source_of(manifest)
        if not origin or subprocess.run(["git", "-C", ROOT, "merge-base", "--is-ancestor", origin, sha]).returncode:
            failures.append(f"{bundle.name}: source commit {origin!r} is not an ancestor of {sha}")
        with tempfile.TemporaryDirectory(prefix="cth-verify-", dir="/tmp") as tmp:
            derived = Path(tmp) / "bundle"
            generate(sha, derived, revision=bundle.name)
            failures += [f"{bundle.name}: {problem}" for problem in compare(bundle, derived)]
        print(f"{bundle.name}: checked")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True, help="the commit whose lineage must reproduce every bundle")
    failures = verify(parser.parse_args().source_sha)
    if failures:
        sys.exit("Release bundle derivation failed:\n" + "\n".join(failures))
    print("Every committed release bundle is derived from this lineage.")


if __name__ == "__main__":
    main()
