"""Unpublished, same-corpus comparison; never changes the selected docs renderer."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import yaml
from jinja2 import Environment, FileSystemLoader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / '.cache'


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frontmatter(text):
    if text.startswith('---\n'):
        head, text = text[4:].split('\n---\n', 1)
        return yaml.safe_load(head) or {}, text.lstrip('\n')
    return {}, text


def write_markdown(path, metadata, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\n' + yaml.safe_dump(metadata, sort_keys=False) + '---\n\n' + body)


def run(command, cwd, name):
    start = time.monotonic()
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (CACHE / f'{name}.log').write_text(result.stdout)
    return {'exit_code': result.returncode, 'seconds': round(time.monotonic() - start, 2)}


def prepare(prototype):
    """Snapshot current sources, retain prototype implementation, and record provenance."""
    snapshot = CACHE / 'zensical'
    snapshot.mkdir(parents=True, exist_ok=True)
    if (snapshot / 'docs').exists():
        shutil.rmtree(snapshot / 'docs')
    shutil.copytree(ROOT / 'docs', snapshot / 'docs')
    site = snapshot / 'docs-site'
    # Copy only generator inputs, not the prototype's old corpus or build results.
    for directory in ('src', 'overrides', 'pages', 'blog', 'tests'):
        target = site / directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(prototype / 'docs-site' / directory, target)
    for name in ('build.py', 'requirements.txt', 'requirements-validation.txt'):
        shutil.copy2(prototype / 'docs-site' / name, site / name)
    (snapshot / 'scripts').mkdir(exist_ok=True)
    for name in ('docs_heading_ids.py', 'check_docs_site.py', 'check_docs_site_accessibility.py'):
        shutil.copy2(prototype / 'scripts' / name, snapshot / 'scripts' / name)
    shutil.copy2(prototype / 'zensical.toml', snapshot / 'zensical.toml')
    builder = load(site / 'build.py')
    # Metadata belongs to the real current checkout, never to the disposable snapshot.
    builder.subprocess = SimpleNamespace(check_output=lambda command, **kwargs: subprocess.check_output(
        command, **{**kwargs, 'cwd': ROOT}))
    config, published = builder.prepare()
    hashes = {p.as_posix(): hashlib.sha256((snapshot / 'docs' / p).read_bytes()).hexdigest() for p in published}
    provenance = {
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'prototype_path': str(prototype), 'documents': hashes,
        'prototype_inputs': {str(p.relative_to(prototype)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [prototype / 'docs-site/build.py', prototype / 'zensical.toml']},
    }
    (CACHE / 'corpus.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return snapshot, builder


def prepare_hugo(snapshot, builder):
    site = CACHE / 'hugo'
    if site.exists():
        shutil.rmtree(site)
    site.mkdir()
    shutil.copy2(HERE / 'hugo.yaml', site / 'hugo.yaml')
    for directory in ('layouts', 'assets'):
        shutil.copytree(HERE / directory, site / directory)
    (site / 'assets/js').mkdir(exist_ok=True)
    shutil.copy2(CACHE / 'tools/flexsearch.bundle.min.js', site / 'assets/js/flexsearch.bundle.min.js')
    (site / 'themes').mkdir()
    (site / 'themes/hextra').symlink_to(CACHE / 'hextra', target_is_directory=True)
    source = snapshot / 'docs-site/.cache/source'
    (site / 'static/assets/css').mkdir(parents=True)
    shutil.copytree(ROOT / 'docs-site/src/fonts', site / 'static/assets/fonts')
    for asset in builder.PUBLISHABLE_ASSETS:
        target = site / 'static' / asset
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / asset, target)
    # Use current brand tokens/fonts and the existing Jinja wordmark macro.
    for name in ('tokens.css', 'fonts.css'):
        shutil.copy2(ROOT / 'docs-site/src/css' / name, site / 'static/assets/css' / name)
    # SPEC-DES-001 §XIII: consume the public stylesheet without a divergent copy.
    shutil.copy2(ROOT / 'github-pages/style.css', site / 'static/assets/css/public.css')
    footers = re.findall(r'<footer\b.*?</footer>', (ROOT / 'github-pages/learnmore.html').read_text(), re.S)
    assert len(footers) == 1, 'The public reference must have exactly one footer'
    footer = footers[0].replace('href="./', 'href="https://classroomtokenhub.com/')
    footer = footer.replace('<span id="current-year"></span>', f'<span id="current-year">{date.today().year}</span>')
    (site / 'layouts/_partials/footer.html').write_text(footer)
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=True)
    hero = env.get_template('macros/docs_hero.html').module.docs_hero(
        'Developer documentation', 'Invariants, domain authority, feature contracts and operating procedures.')
    (site / 'layouts/_partials/cth-hero.html').write_text(str(hero))
    catalog_hero = env.get_template('macros/docs_hero.html').module.docs_hero(
        'All documents', 'Explore the contracts, architecture and operating procedures behind Classroom Token Hub.')
    (site / 'layouts/_partials/cth-catalog-hero.html').write_text(str(catalog_hero))
    paths = sorted(source.rglob('*.md'))
    for path in paths:
        relative = path.relative_to(source)
        metadata, body = frontmatter(path.read_text())
        match = re.search(r'^# (.+)$', body, re.M)
        title = match.group(1) if match else builder.document_label(relative)
        # Only the home hero owns its h1; document headings remain canonical content.
        if match and relative.as_posix() in ('index.md', 'documents.md'):
            body = body[:match.start()] + body[match.end():]
        original = relative.as_posix()
        route = relative.with_suffix('').as_posix()
        if relative.name in ('README.md', 'index.md'):
            route = relative.parent.as_posix()
        edit = metadata.get('edit_url') or (f'https://github.com/timwonderer/classroom-token-hub/edit/main/docs/{original}'
                                            if (snapshot / 'docs' / relative).is_file() else '')
        metadata.update(title=title, type='docs', canonicalSource=original, source_h1=bool(match),
                        url='/'+route.strip('./')+'/' if route != '.' else '/', sourceEditURL=edit)
        if original == 'index.md':
            metadata['type'] = 'home'
        elif original == 'documents.md':
            metadata['layout'] = 'catalog'
        # Raw HTML bypasses Hugo render hooks; resolve explicitly published illustrations.
        for asset in builder.PUBLISHABLE_ASSETS:
            relative_asset = os.path.relpath(source / asset, path.parent)
            body = body.replace(f'src="{relative_asset}"', f'src="/docs/{asset}"')
        if metadata.get('last_updated') and metadata['last_updated'] != 'Uncommitted changes':
            metadata['lastmod'] = metadata['last_updated']
        target = site / 'content' / relative
        if relative.name in ('README.md', 'index.md'):
            target = target.with_name('_index.md')
        elif path.with_suffix('').is_dir():
            target = target.with_suffix('') / '_index.md'
        write_markdown(target, metadata, body)
    for weight, (prefix, title, description) in enumerate(builder.GROUPS, 1):
        section = site / 'content' / prefix / '_index.md'
        if not section.exists():
            write_markdown(section, {'title': title, 'weight': weight, 'type': 'docs'}, description+'\n')
        else:
            metadata, body = frontmatter(section.read_text())
            metadata.update(weight=weight, linkTitle=title)
            write_markdown(section, metadata, body)
    # Explicit nested sections keep all documents reachable in the native sidebar.
    for directory in sorted((site / 'content').rglob('*')):
        if directory.is_dir() and not (directory / '_index.md').exists():
            metadata = {'title': directory.name.replace('_', ' ').title(), 'type': 'docs'}
            if directory.name == 'category':
                metadata['sidebar'] = {'exclude': True}
            write_markdown(directory / '_index.md', metadata, '')
    return site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prototype', type=Path, required=True)
    args = parser.parse_args()
    CACHE.mkdir(exist_ok=True)
    snapshot, builder = prepare(args.prototype.resolve())
    hugo = prepare_hugo(snapshot, builder)
    results = {
        'zensical': run([sys.executable, '-m', 'zensical', 'build', '-f', '.zensical-build.toml'], snapshot, 'zensical-build'),
        'hugo': run([str(CACHE / 'tools/hugo-extracted/Payload/hugo'), '--gc'], hugo, 'hugo-build'),
    }
    (CACHE / 'build-results.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
