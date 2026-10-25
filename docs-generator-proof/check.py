"""Validate the built Hugo artifact: publication scope, links, anchors, assets, headings, search (SOP-DOC-000 §X–XI)."""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin, urlsplit

from build import CACHE, EDIT_URL, SITE

ORIGIN = 'https://classroomtokenhub.com'


class Page(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.ids, self.headings, self.references = [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if re.fullmatch(r'h[1-6]', tag):
            self.headings.append(int(tag[1]))
        self.references += [attrs[a] for a in ('href', 'src') if attrs.get(a)]


def resolve_reference(site: Path, source: Path, reference: str):
    """The local file a reference points at, or None when it leaves the docs artifact."""
    url = urlsplit(urljoin(f'{ORIGIN}/docs/{source.relative_to(site).as_posix()}', reference))
    if url.scheme not in {'http', 'https'} or url.netloc != urlsplit(ORIGIN).netloc or not url.path.startswith('/docs/'):
        return None, ''  # Other public pages are assembled outside the docs generator.
    target = (site / unquote(url.path.removeprefix('/docs/'))).resolve()
    if not target.is_relative_to(site.resolve()):
        raise ValueError(f'Reference escapes site: {reference}')
    if target.is_dir() or (not target.exists() and not target.suffix):
        target /= 'index.html'
    return target, unquote(url.fragment)


def output_path(source: str) -> str:
    path = Path(source)
    return (path.parent / 'index.html' if path.name in ('README.md', 'index.md', '_index.md')
            else path.with_suffix('') / 'index.html').as_posix()


def check(site, expected, search, documents=()):
    """Every failure found; `expected` is the full set of pages the artifact may contain."""
    site = site.resolve()
    pages = {p: Page(p.read_text()) for p in site.rglob('*.html')}
    failures = []
    actual = {p.relative_to(site).as_posix() for p in pages}
    failures += [f'Unexpected published page: {p}' for p in sorted(actual - expected)]
    failures += [f'Missing published page: {p}' for p in sorted(expected - actual)]
    for path, page in pages.items():
        label = path.relative_to(site).as_posix()
        if page.headings.count(1) != 1:
            failures.append(f'{label}: expected one h1, got {page.headings.count(1)}')
        if any(b > a + 1 for a, b in zip(page.headings, page.headings[1:])):
            failures.append(f'{label}: heading level skip')
        if duplicates := [i for i, n in Counter(page.ids).items() if n > 1]:
            failures.append(f'{label}: duplicate IDs {duplicates}')
        for ref in page.references:
            target, fragment = resolve_reference(site, path, ref)
            if target is not None:
                if not target.is_file():
                    failures.append(f'{label}: missing destination {ref}')
                elif fragment and target in pages and fragment not in pages[target].ids:
                    failures.append(f'{label}: missing anchor {ref}')
    for path in site.rglob('*.css'):
        for url, imported in re.findall(r'url\([\s\'"]*([^)\'"\s]+)|@import\s+[\'"]([^\'"]+)', path.read_text()):
            target, _ = resolve_reference(site, path, url or imported)
            if target is not None and not target.is_file():
                failures.append(f'{path.relative_to(site)}: missing CSS asset {url or imported}')
    if not search:
        failures.append('Missing search entries')
    for ref in search:
        target, fragment = resolve_reference(site, site / 'index.html', ref or './')
        if target not in pages or (fragment and fragment not in pages[target].ids):
            failures.append(f'Search points outside published pages: {ref}')
    for source in documents:
        page = pages.get(site / output_path(source))
        if page and EDIT_URL + source not in page.references:
            failures.append(f'{output_path(source)}: missing canonical edit link')
    return {'pages': len(pages), 'search_entries': len(search), 'failures': failures}


def main():
    site = SITE / 'public'
    content = SITE / 'content'
    # The artifact may hold exactly the staged pages (allowlisted documents plus generated navigation).
    expected = {output_path(p.relative_to(content).as_posix()) for p in content.rglob('*.md')} | {'404.html'}
    search = []
    for route, data in json.loads(next(site.glob('en.search-data.*.json')).read_text()).items():
        search.append(route)
        search += [route + '#' + key.split('#', 1)[0] for key in data.get('data', {}) if key]
    documents = json.loads((CACHE / 'corpus.json').read_text())['documents']
    result = check(site, expected, search, documents)
    (CACHE / 'check-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({**result, 'failures': len(result['failures']), 'examples': result['failures'][:10]}, indent=2))
    return result


if __name__ == '__main__':
    raise SystemExit(bool(main()['failures']))
