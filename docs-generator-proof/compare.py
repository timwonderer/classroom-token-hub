"""Compare rendered artifacts with one shared structural and publication gate."""
from collections import Counter
import json
from pathlib import Path
import re

from build import CACHE, load


def check(site, expected, search):
    checker = load(CACHE / 'zensical/scripts/check_docs_site.py')
    pages = {p: checker.Page(p.read_text()) for p in site.rglob('*.html')}
    failures = []
    actual = {p.relative_to(site).as_posix() for p in pages}
    for extra in sorted(actual - expected):
        failures.append(f'Unexpected published page: {extra}')
    for missing in sorted(expected - actual):
        failures.append(f'Missing published page: {missing}')
    for path, page in pages.items():
        label = path.relative_to(site).as_posix()
        if page.headings.count(1) != 1:
            failures.append(f'{label}: expected one h1, got {page.headings.count(1)}')
        if any(b > a + 1 for a, b in zip(page.headings, page.headings[1:])):
            failures.append(f'{label}: heading level skip')
        if len(page.ids) != len(set(page.ids)):
            failures.append(f'{label}: duplicate IDs')
        for ref in page.references:
            target, fragment = checker.resolve_reference(site, path, ref)
            if target is not None:
                if not target.is_file():
                    failures.append(f'{label}: missing destination {ref}')
                elif fragment and target in pages and fragment not in pages[target].ids:
                    failures.append(f'{label}: missing anchor {ref}')
    for path in site.rglob('*.css'):
        for url, imported in re.findall(r'url\([\s\'\"]*([^\)\'\"\s]+)|@import\s+[\'\"]([^\'\"]+)', path.read_text()):
            target, _ = checker.resolve_reference(site, path, url or imported)
            if target is not None and not target.is_file():
                failures.append(f'{path.relative_to(site)}: missing CSS asset {url or imported}')
    if not search:
        failures.append('Missing search entries')
    for ref in search:
        target, fragment = checker.resolve_reference(site, site / 'index.html', ref or './')
        if target not in pages or (fragment and fragment not in pages[target].ids):
            failures.append(f'Search points outside published pages: {ref}')
    return {'pages': len(pages), 'search_entries': len(search), 'failures': failures}


def output_path(source):
    path = Path(source)
    return (path.parent / 'index.html' if path.name in ('README.md', 'index.md', '_index.md')
            else path.with_suffix('') / 'index.html').as_posix()


def main():
    zsite = CACHE / 'zensical/docs-site/build'
    hsite = CACHE / 'hugo/public'
    manifest = json.loads((CACHE / 'zensical/docs-site/.cache/pages.json').read_text())
    expected = {output_path(p) for p in manifest} | {'404.html'}
    zsearch = [p['location'] for p in json.loads((zsite / 'search.json').read_text())['items']]
    hdata = json.loads(next(hsite.glob('en.search-data.*.json')).read_text())
    hsearch = []
    for route, data in hdata.items():
        hsearch.append(route)
        hsearch.extend(route + '#' + k.split('#', 1)[0] for k in data.get('data', {}) if k)
    # Additional Hugo section indexes are generated navigation, never extra source documents.
    h_expected = expected | {output_path(p.relative_to(CACHE / 'hugo/content').as_posix())
                             for p in (CACHE / 'hugo/content').rglob('_index.md')}
    result = {'zensical': check(zsite, expected, zsearch), 'hugo': check(hsite, h_expected, hsearch)}
    checker = load(CACHE / 'zensical/scripts/check_docs_site.py')
    missing_fragments = {}
    heading_count = 0
    for source in json.loads((CACHE / 'corpus.json').read_text())['documents']:
        output = output_path(source)
        zids = set(checker.Page((zsite / output).read_text()).ids)
        hids = set(checker.Page((hsite / output).read_text()).ids)
        # Page h1 and article headings only; exclude theme-generated controls.
        text = (zsite / output).read_text()
        article = text.split('<article', 1)[-1].split('</article>', 1)[0]
        ids = set(re.findall(r'<h[1-6][^>]*id="([^"]+)"', article))
        heading_count += len(ids)
        if ids - hids:
            missing_fragments[source] = sorted(ids - hids)
        edit = 'https://github.com/timwonderer/classroom-token-hub/edit/main/docs/' + source
        for name, site in [('hugo', hsite), ('zensical', zsite)]:
            if edit not in checker.Page((site / output).read_text()).references:
                result[name]['failures'].append(f'{output}: missing canonical edit link')
    result['hugo_missing_zensical_heading_fragments'] = missing_fragments
    result['corpus_documents'] = len(json.loads((CACHE / 'corpus.json').read_text())['documents'])
    result['canonical_heading_fragments_compared'] = heading_count
    (CACHE / 'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: {'pages': value['pages'], 'search_entries': value['search_entries'],
                            'failures': len(value['failures']), 'examples': value['failures'][:8]}
                      for key, value in result.items() if key in ('hugo', 'zensical')}, indent=2))
    print('Documents with missing heading fragments:', len(missing_fragments))
    return result


if __name__ == '__main__':
    result = main()
    raise SystemExit(bool(result['hugo']['failures'] or result['zensical']['failures'] or
                          result['hugo_missing_zensical_heading_fragments']))
