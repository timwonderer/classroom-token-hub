"""Mutation proofs for the artifact gate and publication policy; no application/database fixtures."""
from pathlib import Path

import pytest

from check import check
from build import CACHE, ROOT, catalog_label, published_documents


def test_shared_public_brand_sources_are_preserved():
    """Fail when the proof forks the shared CSS or drops public footer content."""
    import re
    site = CACHE / 'hugo'
    assert (site / 'static/assets/css/public.css').read_bytes() == (ROOT / 'github-pages/style.css').read_bytes()
    reference = re.search(r'<footer\b.*?</footer>', (ROOT / 'github-pages/learnmore.html').read_text(), re.S).group()
    actual = (site / 'layouts/_partials/footer.html').read_text()
    actual = re.sub(r'(<span id="current-year">)\d{4}(</span>)', r'\1\2', actual)
    assert actual == reference.replace('href="./', 'href="https://classroomtokenhub.com/')



def test_published_artifact_carries_no_theme_branding():
    """Hextra's favicons and manifest name another product; the CTH tab icon replaces them."""
    public = CACHE / 'hugo/public'
    leaked = [p.name for p in public.iterdir() if p.name.startswith(('favicon', 'android-chrome', 'apple-touch'))
              or p.name == 'site.webmanifest']
    assert leaked == []
    assert (public / 'assets/images/icon-192.png').read_bytes() == (ROOT / 'static/images/icon-192.png').read_bytes()
    assert 'href="/docs/assets/images/icon-192.png"' in (public / 'index.html').read_text()


def test_engineering_notes_are_not_published():
    """Engineering notes (docs-site/blog) are not authorized; neither pages nor links may ship."""
    public = CACHE / 'hugo/public'
    assert not (public / 'notes').exists()
    assert not any('/docs/notes/' in p.read_text() for p in public.rglob('*.html'))


def artifact(tmp_path):
    (tmp_path / 'index.html').write_text('<h1 id="home">Home</h1>')
    return tmp_path.resolve()


def test_valid_artifact(tmp_path):
    assert check(artifact(tmp_path), {'index.html'}, ['#home'])['failures'] == []


@pytest.mark.parametrize('ref', ['missing/', '#missing'])
def test_dead_link_or_fragment_is_rejected(tmp_path, ref):
    site = artifact(tmp_path)
    (site / 'index.html').write_text(f'<h1 id="home">Home</h1><a href="{ref}">Link</a>')
    assert check(site, {'index.html'}, ['#home'])['failures']


def test_unlinked_excluded_page_is_rejected(tmp_path):
    site = artifact(tmp_path)
    (site / 'user-guides').mkdir()
    (site / 'user-guides/index.html').write_text('<h1>Should never publish</h1>')
    assert any('Unexpected published' in x for x in check(site, {'index.html'}, ['#home'])['failures'])


def test_search_leak_is_rejected(tmp_path):
    assert check(artifact(tmp_path), {'index.html'}, ['ops/private/'])['failures']


def test_missing_canonical_edit_link_is_rejected(tmp_path):
    site = artifact(tmp_path)
    (site / 'SPEC/x').mkdir(parents=True)
    (site / 'SPEC/x/index.html').write_text('<h1 id="x">X</h1>')
    failures = check(site, {'index.html', 'SPEC/x/index.html'}, ['#home'], ['SPEC/x.md'])['failures']
    assert any('missing canonical edit link' in f for f in failures)


def test_missing_self_hosted_font_is_rejected(tmp_path):
    site = artifact(tmp_path)
    (site / 'fonts.css').write_text('@font-face {src: url(missing.woff2)}')
    assert any('CSS asset' in x for x in check(site, {'index.html'}, ['#home'])['failures'])


def test_publication_policy_excludes_new_working_state_and_user_guides(tmp_path):
    for name in ('INVARIANT/CORE/example.md', 'user-guides/help.md', 'ops/new.md',
                 'TRACKING/new.md', 'archive/old.md', 'unknown/new.md',
                 'TRACKING/DOCS_PLATFORM_ROADMAP.md'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Fixture')
    assert {p.as_posix() for p in published_documents(tmp_path)} == {
        'INVARIANT/CORE/example.md', 'TRACKING/DOCS_PLATFORM_ROADMAP.md'}


def test_symlinked_source_outside_the_tree_is_rejected(tmp_path):
    outside = tmp_path / 'private.md'
    outside.write_text('# Private')
    (tmp_path / 'docs/SPEC').mkdir(parents=True)
    (tmp_path / 'docs/SPEC/leak.md').symlink_to(outside)
    with pytest.raises(ValueError):
        published_documents(tmp_path / 'docs')


def test_catalog_labels_come_from_document_titles():
    """Filename-derived labels ("Pii", "Readme", stale names) give way to each document's h1."""
    assert catalog_label(Path('INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII.md'), 'INV-ARC-005: No PII Leakage') == 'INV-ARC-005 · No PII Leakage'
    assert catalog_label(Path('FEATURE-EXECUTION/FEAT-IDEN-006_PROVISION.md'), 'FEAT-IDEN-006 — Provision Student Seat') == 'FEAT-IDEN-006 · Provision Student Seat'
    assert catalog_label(Path('SOP/SOP-DB-001_Migration_Specifications.md'), 'Database Migration Specifications') == 'SOP-DB-001 · Database Migration Specifications'
    assert catalog_label(Path('self-hosting/README.md'), 'Self-hosting Classroom Token Hub') == 'Self-hosting Classroom Token Hub'
