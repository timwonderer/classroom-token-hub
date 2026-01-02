"""
Documentation routes for Classroom Token Hub.

Serves feature-based documentation with markdown rendering,
allowing users to access help without leaving the app or losing their session.
"""

import re
from functools import lru_cache
from pathlib import Path
from flask import Blueprint, abort, current_app, session, request, url_for
import bleach
from werkzeug.utils import safe_join
import markdown
from markdown.extensions.toc import TocExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension

from app.utils.helpers import render_template_with_fallback

# Create blueprint
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Documentation root directory
DOCS_ROOT = Path(__file__).parent.parent.parent / 'docs'

DOCS_ALLOWED_TAGS = [
    'p', 'br', 'span', 'div',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'strong', 'em', 'u', 's', 'del', 'code', 'pre',
    'ul', 'ol', 'li',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'blockquote', 'hr',
]
DOCS_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],
    'pre': ['class'],
    'span': ['class'],
    'div': ['class'],
    'table': ['class'],
    'thead': ['class'],
    'tbody': ['class'],
    'tr': ['class'],
    'th': ['align', 'class'],
    'td': ['align', 'class'],
    'ul': ['class'],
    'ol': ['class'],
    'li': ['class'],
    'h1': ['id', 'class'],
    'h2': ['id', 'class'],
    'h3': ['id', 'class'],
    'h4': ['id', 'class'],
    'h5': ['id', 'class'],
    'h6': ['id', 'class'],
}
DOCS_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto']
DOCS_CLEANER = bleach.Cleaner(
    tags=DOCS_ALLOWED_TAGS,
    attributes=DOCS_ALLOWED_ATTRIBUTES,
    protocols=DOCS_ALLOWED_PROTOCOLS,
    strip=True,
    strip_comments=True,
)


def parse_front_matter(content):
    """
    Extract YAML-style front matter from markdown content.

    Front matter format:
    ---
    title: Page Title
    category: feature-name
    roles: [teacher, student]
    related:
      - path/to/related/doc
      - another/related/doc
    ---

    Returns:
        tuple: (metadata_dict, remaining_content)
    """
    if not content.startswith('---'):
        return {}, content

    try:
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        # Simple YAML parsing (we'll just do basic key: value pairs)
        metadata = {}
        front_matter = parts[1].strip()
        current_list_key = None

        for line in front_matter.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('- ') and current_list_key:
                item = line[2:].strip().strip('"\'')
                metadata[current_list_key].append(item)
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                current_list_key = None

                # Handle lists (basic)
                if value.startswith('[') and value.endswith(']'):
                    inner = value[1:-1].strip()
                    if inner:
                        value = [v.strip().strip('"\'') for v in inner.split(',')]
                    else:
                        value = []
                elif not value:
                    metadata[key] = []
                    current_list_key = key
                    continue
                else:
                    value = value.strip('"\'')

                metadata[key] = value

        return metadata, parts[2].strip()
    except Exception as e:
        current_app.logger.warning(f"Failed to parse front matter: {e}")
        return {}, content


def render_markdown_content(content):
    """
    Convert markdown to HTML with extensions.

    Args:
        content: Markdown text

    Returns:
        tuple: (html_content, toc_html)
    """
    md = markdown.Markdown(
        extensions=[
            'extra',
            TocExtension(title='On This Page'),
            CodeHiliteExtension(linenums=False, css_class='highlight'),
            FencedCodeExtension(),
            TableExtension(),

        ]
    )

    html = md.convert(content)
    toc = md.toc if hasattr(md, 'toc') else ''

    return DOCS_CLEANER.clean(html), DOCS_CLEANER.clean(toc)


def get_docs_mtime():
    """Return the latest modification time across documentation files."""
    latest_mtime = 0
    for doc_file in DOCS_ROOT.rglob('*.md'):
        try:
            latest_mtime = max(latest_mtime, doc_file.stat().st_mtime)
        except OSError:
            continue
    return latest_mtime


@lru_cache(maxsize=1)
def build_search_index(latest_mtime):
    """
    Build a cached search index of documentation content.

    Cache invalidates when any doc file mtime changes.
    """
    docs_index = []

    for doc_file in DOCS_ROOT.rglob('*.md'):
        try:
            if not doc_file.is_relative_to(DOCS_ROOT):
                continue

            content = doc_file.read_text(encoding='utf-8')
            metadata, body = parse_front_matter(content)
            title = metadata.get('title', doc_file.stem)
            rel_path = doc_file.relative_to(DOCS_ROOT).with_suffix('')

            docs_index.append({
                'title': title,
                'title_lower': title.lower(),
                'body': body,
                'body_lower': body.lower(),
                'body_lines': body.split('\n'),
                'rel_path': str(rel_path),
                'category': rel_path.parts[0] if len(rel_path.parts) > 1 else 'Other',
            })
        except Exception as e:
            current_app.logger.warning(f"Error indexing {doc_file}: {e}")
            continue

    return docs_index


def get_doc_metadata(doc_path):
    """
    Get metadata for a documentation file.

    Args:
        doc_path: Path object to the markdown file

    Returns:
        dict: Metadata including title, category, roles, etc.
    """
    if not doc_path.exists():
        return None

    content = doc_path.read_text(encoding='utf-8')
    metadata, _ = parse_front_matter(content)

    # Extract title from first H1 if not in front matter
    if 'title' not in metadata:
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            metadata['title'] = match.group(1)
        else:
            metadata['title'] = doc_path.stem.replace('_', ' ').replace('-', ' ').title()

    return metadata


def build_breadcrumbs(category, page=None):
    """
    Build breadcrumb navigation for documentation pages.

    Args:
        category: Category name (e.g., 'getting-started', 'store')
        page: Optional page name within category

    Returns:
        list: List of dicts with 'title' and 'url' keys
    """
    breadcrumbs = []

    if category:
        category_title = category.replace('-', ' ').title()
        breadcrumbs.append({
            'title': category_title,
            'url': url_for('docs.view_doc', doc_path=category)
        })

    if page:
        page_title = page.replace('-', ' ').title()
        breadcrumbs.append({
            'title': page_title,
            'url': url_for('docs.view_doc', doc_path=f'{category}/{page}')
        })

    return breadcrumbs


def get_related_articles(related_paths):
    """
    Get metadata for related article paths.

    Args:
        related_paths: List of related doc paths or string

    Returns:
        list: List of dicts with 'title' and 'url' for each related article
    """
    if not related_paths:
        return []

    # Handle string (single path) or list
    if isinstance(related_paths, str):
        related_paths = [related_paths]

    articles = []
    for path in related_paths:
        try:
            # Remove leading slash if present
            path = path.lstrip('/')

            # Try to find the file
            doc_file = (DOCS_ROOT / path).with_suffix('.md')

            if not doc_file.exists():
                current_app.logger.warning(f"Related article not found: {path}")
                continue

            # Get metadata
            metadata = get_doc_metadata(doc_file)
            if metadata:
                articles.append({
                    'title': metadata.get('title', path),
                    'url': f'/docs/{path}'
                })
        except Exception as e:
            current_app.logger.warning(f"Error loading related article {path}: {e}")
            continue

    return articles


# -------------------- ROUTES --------------------

@docs_bp.route('/')
def index():
    """Documentation homepage with categories."""
    return render_template_with_fallback('docs/index.html')


@docs_bp.route('/<path:doc_path>')
def view_doc(doc_path):
    """
    Render a markdown documentation file as HTML.

    URL structure:
    - /docs/getting-started/overview
    - /docs/store/creating-basic-items
    - /docs/technical-reference/architecture

    Args:
        doc_path: Path to the documentation file (without .md extension)
    """
    # Security: Prevent directory traversal
    try:
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", doc_path):
            current_app.logger.warning(f"Invalid doc path requested: {doc_path}")
            abort(404)

        if any(part in {".", ".."} for part in Path(doc_path).parts):
            current_app.logger.warning(f"Path traversal attempt: {doc_path}")
            abort(404)

        # Normalize the path
        safe_path = Path(doc_path).with_suffix('.md')

        # Resolve absolute path
        joined_path = safe_join(str(DOCS_ROOT), str(safe_path))
        if not joined_path:
            current_app.logger.warning(f"Path traversal attempt: {doc_path}")
            abort(404)

        doc_file = Path(joined_path).resolve()

        # Ensure the resolved path is within DOCS_ROOT
        if not doc_file.is_relative_to(DOCS_ROOT.resolve()):
            current_app.logger.warning(f"Path traversal attempt: {doc_path}")
            abort(404)

        if not doc_file.exists():
            current_app.logger.info(f"Documentation not found: {doc_path}")
            abort(404)

        # Read and parse the file
        content = doc_file.read_text(encoding='utf-8')
        metadata, body = parse_front_matter(content)

        # Convert markdown to HTML
        html_content, toc = render_markdown_content(body)

        # Determine category and page from path
        path_parts = Path(doc_path).parts
        category = None
        page = None
        if path_parts:
            category = path_parts[0]
            if len(path_parts) > 1:
                page = "/".join(path_parts[1:])

        # Build breadcrumbs
        breadcrumbs = build_breadcrumbs(category, page)

        # Get related articles
        related_paths = metadata.get('related', [])
        related_articles = get_related_articles(related_paths)

        # Get user role for filtering
        user_role = None
        if session.get('admin_id'):
            user_role = 'teacher'
        elif session.get('student_id'):
            user_role = 'student'
        elif session.get('sysadmin_id'):
            user_role = 'sysadmin'

        return render_template_with_fallback(
            'docs/view.html',
            content=html_content,
            toc=toc,
            title=metadata.get('title', doc_path),
            category=category,
            current_category=category,
            breadcrumbs=breadcrumbs,
            roles=metadata.get('roles', []),
            related=related_articles,
            user_role=user_role,
            doc_path=doc_path,
        )

    except (FileNotFoundError, UnicodeDecodeError) as e:
        # Treat file access/decoding problems as missing documentation
        current_app.logger.warning(f"Documentation file error for '{doc_path}': {e}")
        abort(404)
    except Exception as e:
    # Ensure documentation root exists and is accessible
    if not DOCS_ROOT.exists() or not DOCS_ROOT.is_dir():
        current_app.logger.error(f"Documentation root '{DOCS_ROOT}' does not exist or is not a directory")
        abort(500)

    results = []

    # Search through all markdown files
    for doc_file in DOCS_ROOT.rglob('*.md'):
        try:
            # Skip if not relative to DOCS_ROOT (safety check)
            if not doc_file.is_relative_to(DOCS_ROOT):
                continue

            content = doc_file.read_text(encoding='utf-8')
            metadata, body = parse_front_matter(content)

            # Search in title and content (case-insensitive)
            title = metadata.get('title', doc_file.stem)

            if query.lower() in title.lower() or query.lower() in body.lower():
                # Get relative path for URL
                rel_path = doc_file.relative_to(DOCS_ROOT).with_suffix('')

                # Find context around the match
                context = ''
                for line in body.split('\n'):
                    if query.lower() in line.lower():
                        context = line.strip()[:200]
                        break

                results.append({
                    'title': title,
                    'url': f'/docs/{rel_path}',
                    'context': context,
                    'category': rel_path.parts[0] if len(rel_path.parts) > 0 else 'Other'
                })
        except Exception as e:
            current_app.logger.warning(f"Error searching {doc_file}: {e}")
            continue
    return render_template_with_fallback(
        'docs/search.html',
        query=query,
        results=results
    )
