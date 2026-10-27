"""Stage the canonical developer docs and build them with Hugo + Hextra (SOP-DOC-000 §X)."""
from __future__ import annotations

from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import yaml
from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DOCS = ROOT / 'docs'
CACHE = HERE / '.cache'
SITE = CACHE / 'hugo'
HUGO = CACHE / 'tools/bin/hugo'  # installed by bootstrap.py for this platform
EDIT_URL = 'https://github.com/timwonderer/classroom-token-hub/edit/main/docs/'

# Publication allowlist (SOP-DOC-000 §X): each root, its catalog title and its catalog description.
GROUPS = (
    ('INVARIANT', 'Invariants', 'Constitutional authority: core laws and architectural invariants.'),
    ('DOMAIN', 'Domain Authority', 'Normative contracts defining what each domain owns.'),
    ('FEATURE-EXECUTION', 'Feature Execution', 'Normative execution contracts for state mutations.'),
    ('SPEC', 'Specifications', 'Technical contracts, binding when incorporated by governing authority.'),
    ('STANDARD_OPERATING_PROCEDURES', 'Standard Operating Procedures', 'Procedures for development and operations.'),
    ('MAP', 'Interface Maps', 'Informative maps of interfaces and execution paths.'),
    ('REFERENCE', 'Reference', 'Developer vocabulary is normative; other references are informative.'),
    ('PRINCIPLES', 'Principles', 'Informative rationale for design decisions.'),
    ('self-hosting', 'Self-Hosting', 'Informative guidance for running an instance.'),
    ('TRACKING', 'Tracking', 'Informative roadmap and domain plan template.'),
)
# docs/TRACKING is working state; only these two durable files publish.
PUBLISHABLE_TRACKING = frozenset({
    'TRACKING/DOCS_PLATFORM_ROADMAP.md',
    'TRACKING/DOMAIN_IMPLEMENTATION_PLAN_TEMPLATE.md',
})
PUBLIC_ROOTS = frozenset(prefix for prefix, _, _ in GROUPS if prefix != 'TRACKING')
PUBLISHABLE_ASSETS = ('assets/DOM-IDEN-001_Identity_Graph.svg',)
ID_PATTERN = re.compile(r'^((?:INV|DOM|FEAT|SPEC|SOP|MAP|REF|PRN)-[A-Z]+-\d+[A-Z]?)[_ ]')


def published_documents(docs: Path) -> list[Path]:
    """Allowlisted trees only; new working records and source assets stay private to the repo."""
    selected = []
    for path in sorted(docs.rglob('*.md')):
        relative = path.relative_to(docs)
        if relative.parts[0] in PUBLIC_ROOTS or relative.as_posix() in PUBLISHABLE_TRACKING:
            if path.is_symlink() or not path.resolve().is_relative_to(docs.resolve()):
                raise ValueError(f'Documentation source escapes canonical tree: {relative}')
            selected.append(relative)
    return selected


def frontmatter(text):
    if text.startswith('---\n'):
        head, text = text[4:].split('\n---\n', 1)
        return yaml.safe_load(head) or {}, text.lstrip('\n')
    return {}, text


def h1(text):
    match = re.search(r'^# (.+)$', text, re.M)
    return match and match.group(1)


def catalog_label(relative: Path, title: str) -> str:
    """The document's own h1, as "ID · Title" when its filename carries a document ID."""
    match = ID_PATTERN.match(relative.name)
    if not match:
        return title
    ident = match[1]
    return f"{ident} · {title[len(ident):].lstrip(':—– ') if title.startswith(ident) else title}"


def write_page(relative, metadata, body):
    """Write one Hugo page; README/index files and directory twins become section indexes."""
    target = SITE / 'content' / relative
    if relative.name in ('README.md', 'index.md'):
        target = target.with_name('_index.md')
    elif (DOCS / relative).with_suffix('').is_dir():
        target = target.with_suffix('') / '_index.md'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n\n' + body)


def route(relative: Path) -> str:
    path = relative.parent if relative.name in ('README.md', 'index.md') else relative.with_suffix('')
    return '/' + path.as_posix().strip('./') + '/' if path.as_posix() != '.' else '/'


def stage_documents(published):
    changed = set(subprocess.check_output(['git', 'diff', 'HEAD', '--name-only', '--', 'docs'], cwd=ROOT, text=True).split())
    titles = {}
    for relative in published:
        metadata, body = frontmatter((DOCS / relative).read_text())
        title = h1(body) or relative.stem.replace('_', ' ')
        titles[relative] = title
        repo_path = f'docs/{relative.as_posix()}'
        updated = subprocess.check_output(['git', 'log', '-1', '--format=%cs', '--', repo_path], cwd=ROOT, text=True).strip()
        metadata.update(title=title, type='docs', canonicalSource=relative.as_posix(), source_h1=bool(h1(body)),
                        url=route(relative), sourceEditURL=EDIT_URL + relative.as_posix(),
                        last_updated='Uncommitted changes' if repo_path in changed or not updated else updated)
        if metadata['last_updated'] != 'Uncommitted changes':
            metadata['lastmod'] = metadata['last_updated']
        # Raw HTML bypasses Hugo render hooks; resolve explicitly published illustrations.
        for asset in PUBLISHABLE_ASSETS:
            body = body.replace(f'src="{os.path.relpath(DOCS / asset, (DOCS / relative).parent)}"', f'src="/docs/{asset}"')
        write_page(relative, metadata, body)
    return titles


def stage_navigation(published, titles):
    """Home, the full catalog and one page per category; the hero owns the h1 on home and catalog."""
    generated = {'type': 'docs', 'source_h1': True, 'sourceEditURL': ''}
    write_page(Path('index.md'), {'title': 'Developer documentation', 'type': 'home', 'url': '/',
                                  'description': 'Invariants, domain authority, feature contracts, and operating procedures.'}, '')
    catalog = [f'{len(published)} documents, generated from the published source set. '
               'This catalog is navigation; SOP-DOC-001 is the canonical index of record.\n']
    for prefix, title, description in GROUPS:
        paths = [p for p in published if p.parts[0] == prefix]
        slug = title.lower().replace(' ', '-')
        lines = [f'# {title}\n', description + '\n']
        lines += [f'- [{catalog_label(p, titles[p])}](../{p.as_posix()})' for p in paths]
        write_page(Path('category') / f'{slug}.md',
                   {**generated, 'title': title, 'canonicalSource': f'category/{slug}.md', 'url': f'/category/{slug}/'},
                   '\n'.join(lines) + '\n')
        catalog += [f'\n## {title}\n', description + '\n']
        catalog += [f'- [{catalog_label(p, titles[p])}]({p.as_posix()})' for p in paths]
    write_page(Path('documents.md'), {**generated, 'title': 'All documents', 'canonicalSource': 'documents.md',
                                      'url': '/documents/', 'layout': 'catalog'}, '\n'.join(catalog) + '\n')
    for weight, (prefix, title, description) in enumerate(GROUPS, 1):
        section = SITE / 'content' / prefix / '_index.md'
        if section.exists():
            metadata, body = frontmatter(section.read_text())
            section.write_text('---\n' + yaml.safe_dump({**metadata, 'weight': weight, 'linkTitle': title}, sort_keys=False) + '---\n\n' + body)
        else:
            write_page(Path(prefix) / '_index.md', {'title': title, 'weight': weight, 'type': 'docs'}, description + '\n')
    # Explicit nested sections keep all documents reachable in the native sidebar.
    for directory in sorted((SITE / 'content').rglob('*')):
        if directory.is_dir() and not (directory / '_index.md').exists():
            metadata = {'title': directory.name.replace('_', ' ').title(), 'type': 'docs'}
            if directory.name == 'category':
                metadata['sidebar'] = {'exclude': True}
            (directory / '_index.md').write_text('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n\n')


def stage_theme():
    shutil.copy2(HERE / 'hugo.yaml', SITE / 'hugo.yaml')
    for directory in ('layouts', 'assets'):
        shutil.copytree(HERE / directory, SITE / directory)
    (SITE / 'assets/js').mkdir(exist_ok=True)
    shutil.copy2(CACHE / 'tools/flexsearch.bundle.min.js', SITE / 'assets/js/flexsearch.bundle.min.js')
    (SITE / 'themes').mkdir()
    (SITE / 'themes/hextra').symlink_to(CACHE / 'hextra', target_is_directory=True)
    static = SITE / 'static'
    (static / 'assets/css').mkdir(parents=True)
    shutil.copytree(HERE / 'brand/fonts', static / 'assets/fonts')
    # The application's tab icon, so every CTH surface shows the same one.
    (static / 'assets/images').mkdir()
    shutil.copy2(ROOT / 'static/images/icon-192.png', static / 'assets/images/icon-192.png')
    for asset in PUBLISHABLE_ASSETS:
        (static / asset).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DOCS / asset, static / asset)
    # Use current brand tokens/fonts and the existing Jinja wordmark macro.
    for name in ('tokens.css', 'fonts.css'):
        shutil.copy2(HERE / 'brand/css' / name, static / 'assets/css' / name)
    # SPEC-DES-001 §XIII: consume the public stylesheet without a divergent copy.
    shutil.copy2(ROOT / 'github-pages/style.css', static / 'assets/css/public.css')
    footers = re.findall(r'<footer\b.*?</footer>', (ROOT / 'github-pages/learnmore.html').read_text(), re.S)
    assert len(footers) == 1, 'The public reference must have exactly one footer'
    footer = footers[0].replace('href="./', 'href="https://classroomtokenhub.com/')
    footer = footer.replace('<span id="current-year"></span>', f'<span id="current-year">{date.today().year}</span>')
    (SITE / 'layouts/_partials/footer.html').write_text(footer)
    hero = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=True).get_template('macros/docs_hero.html').module.docs_hero
    (SITE / 'layouts/_partials/cth-hero.html').write_text(str(hero(
        'Developer documentation', 'Invariants, domain authority, feature contracts, and operating procedures.')))
    (SITE / 'layouts/_partials/cth-catalog-hero.html').write_text(str(hero(
        'All documents', 'Explore the contracts, architecture, and operating procedures behind Classroom Token Hub.')))


def prepare():
    published = published_documents(DOCS)
    if not published or not PUBLISHABLE_TRACKING <= {p.as_posix() for p in published}:
        raise ValueError('Published documentation or deliberate tracking exceptions are missing')
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    stage_theme()
    stage_navigation(published, stage_documents(published))
    provenance = {
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'documents': {p.as_posix(): hashlib.sha256((DOCS / p).read_bytes()).hexdigest() for p in published},
    }
    (CACHE / 'corpus.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return published


def main():
    published = prepare()
    start = time.monotonic()
    result = subprocess.run([str(HUGO), '--gc'], cwd=SITE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (CACHE / 'hugo-build.log').write_text(result.stdout)
    report = {'documents': len(published), 'exit_code': result.returncode, 'seconds': round(time.monotonic() - start, 2)}
    (CACHE / 'build-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if result.returncode:
        raise SystemExit(result.stdout)


if __name__ == '__main__':
    main()
