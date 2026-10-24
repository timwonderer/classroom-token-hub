"""Mutation proofs for the shared artifact gate; no application/database fixtures."""
import pytest

from compare import check
from build import CACHE, ROOT, load


def test_shared_public_brand_sources_are_preserved():
    """Fail when the proof forks the shared CSS or drops public footer content."""
    import re
    site = CACHE / 'hugo'
    assert (site / 'static/assets/css/public.css').read_bytes() == (ROOT / 'github-pages/style.css').read_bytes()
    reference = re.search(r'<footer\b.*?</footer>', (ROOT / 'github-pages/learnmore.html').read_text(), re.S).group()
    actual = (site / 'layouts/_partials/footer.html').read_text()
    actual = re.sub(r'(<span id="current-year">)\d{4}(</span>)', r'\1\2', actual)
    assert actual == reference.replace('href="./', 'href="https://classroomtokenhub.com/')


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


def test_missing_self_hosted_font_is_rejected(tmp_path):
    site = artifact(tmp_path)
    (site / 'fonts.css').write_text('@font-face {src: url(missing.woff2)}')
    assert any('CSS asset' in x for x in check(site, {'index.html'}, ['#home'])['failures'])


def test_publication_policy_excludes_new_working_state_and_user_guides(tmp_path):
    builder = load(CACHE / 'zensical/docs-site/build.py')
    for name in ('INVARIANT/CORE/example.md', 'user-guides/help.md', 'ops/new.md',
                 'TRACKING/new.md', 'archive/old.md', 'unknown/new.md',
                 'TRACKING/DOCS_PLATFORM_ROADMAP.md'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Fixture')
    assert {p.as_posix() for p in builder.published_documents(tmp_path)} == {
        'INVARIANT/CORE/example.md', 'TRACKING/DOCS_PLATFORM_ROADMAP.md'}
