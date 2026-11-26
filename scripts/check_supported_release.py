"""Check the declared supported fresh-install release (SOP-DEP-002 §VII.B).

``migrations/fresh/supported_release.json`` is the one authoritative declaration of the
release that new installations start from. This check needs no database. It fails unless:

* the declared tag exists and points at the declared commit;
* that release's sole Alembic head is the declared revision;
* that release contains the fresh-install bundle for its head, intact (its ``schema.sql``
  hashes to the manifest's ``ddl_sha256``);
* this checkout carries the byte-identical bundle, so the CI derivation check
  (``verify_fresh_bundles.py``) covers exactly what the release ships;
* the README and the handbook each name the declared tag exactly once on their
  ``Supported fresh-install release`` line.

It does not require any other release to have a bundle.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = "migrations/fresh/supported_release.json"
DOCUMENTS = ("README.md", "docs/self-hosting/before-you-begin.md")
MARKER = re.compile(r"Supported fresh-install release:\*\*\s*\[?(v\d+\.\d+\.\d+)")


def git(*args, binary=False):
    out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=False)
    if out.returncode:
        return None
    return out.stdout if binary else out.stdout.decode().strip()


def declared_tags(text):
    """Every tag named on a ``Supported fresh-install release`` line."""
    return MARKER.findall(text)


def sole_head(revision_sources):
    """The single head of a set of revision files' source text, or None."""
    parents, revisions = set(), set()
    for source in revision_sources:
        revision, down = None, None
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "revision":
                    revision = ast.literal_eval(node.value)
                elif node.targets[0].id == "down_revision":
                    down = ast.literal_eval(node.value)
        if revision:
            revisions.add(revision)
            parents.update(down if isinstance(down, (list, tuple)) else [down] if down else [])
    heads = revisions - parents
    return heads.pop() if len(heads) == 1 else None


def check(declaration, ref_commit, release_files, release_bundle, checkout_bundle, documents):
    """Every problem with the declaration. Inputs are plain data, so each rule is testable."""
    problems = []
    tag, commit, revision = declaration.get("tag"), declaration.get("commit"), declaration.get("revision")
    if not (tag and commit and revision):
        return [f"{DECLARATION} must give tag, commit and revision"]
    if ref_commit != commit:
        problems.append(f"tag {tag} resolves to {ref_commit}, not the declared commit {commit}")
    head = sole_head(release_files)
    if head != revision:
        problems.append(f"{tag}'s sole migration head is {head}, not the declared revision {revision}")
    schema, manifest = release_bundle
    if schema is None or manifest is None:
        problems.append(f"{tag} does not contain migrations/fresh/{revision}/")
    else:
        parsed = json.loads(manifest)
        if parsed.get("revision") != revision:
            problems.append(f"{tag}'s bundle manifest names revision {parsed.get('revision')}")
        if hashlib.sha256(schema).hexdigest() != parsed.get("ddl_sha256"):
            problems.append(f"{tag}'s bundle schema.sql does not match its manifest ddl_sha256")
        if checkout_bundle != release_bundle:
            problems.append(f"this checkout's migrations/fresh/{revision}/ differs from the one {tag} ships")
    for name, text in documents.items():
        named = declared_tags(text)
        if named != [tag]:
            problems.append(f"{name} names {named or 'no'} supported fresh-install release; expected exactly [{tag!r}]")
    return problems


def main():
    declaration = json.loads((ROOT / DECLARATION).read_text())
    tag, revision = declaration.get("tag", ""), declaration.get("revision", "")
    ref_commit = git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
    listing = git("ls-tree", "--name-only", f"{tag}:migrations/versions") or ""
    release_files = [git("show", f"{tag}:migrations/versions/{name}") for name in listing.split() if name.endswith(".py")]
    bundle = f"migrations/fresh/{revision}"
    release_bundle = (git("show", f"{tag}:{bundle}/schema.sql", binary=True),
                      git("show", f"{tag}:{bundle}/manifest.json", binary=True))
    local = [ROOT / bundle / name for name in ("schema.sql", "manifest.json")]
    checkout_bundle = tuple(p.read_bytes() if p.is_file() else None for p in local)
    documents = {name: (ROOT / name).read_text(encoding="utf-8") for name in DOCUMENTS}
    problems = check(declaration, ref_commit, [f for f in release_files if f], release_bundle,
                     checkout_bundle, documents)
    if problems:
        sys.exit("Supported fresh-install release check failed:\n" + "\n".join(problems))
    print(f"Supported fresh-install release {tag} ({revision}) is declared consistently and ships its bundle.")


if __name__ == "__main__":
    main()
