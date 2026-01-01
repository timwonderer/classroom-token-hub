"""
Documentation routes for Classroom Token Hub.

Serves feature-based documentation with markdown rendering,
allowing users to access help without leaving the app or losing their session.
"""

import re
from pathlib import Path
from flask import Blueprint, render_template, abort, current_app, session, request
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

        for line in front_matter.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Handle lists (basic)
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip().strip('"\'') for v in value[1:-1].split(',')]

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
            'nl2br',
        ]
    )

    html = md.convert(content)
    toc = md.toc if hasattr(md, 'toc') else ''

    return html, toc


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
            'url': f'/docs/{category}'
        })

    if page:
        page_title = page.replace('-', ' ').title()
        breadcrumbs.append({
            'title': page_title,
            'url': f'/docs/{category}/{page}'
        })

    return breadcrumbs


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
        # Normalize the path
        safe_path = Path(doc_path).with_suffix('.md')

        # Resolve absolute path
        doc_file = (DOCS_ROOT / safe_path).resolve()

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
        category = path_parts[0] if len(path_parts) > 0 else None
        page = path_parts[-1] if len(path_parts) > 1 else None

        # Build breadcrumbs
        breadcrumbs = build_breadcrumbs(category, page)

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
            user_role=user_role,
            doc_path=doc_path,
        )

    except Exception as e:
        current_app.logger.exception(f"Error rendering documentation: {e}")
        abort(500)


@docs_bp.route('/search')
def search():
    """
    Simple documentation search.

    Searches through documentation files for the query string.
    """
    query = request.args.get('q', '').strip()

    if not query:
        return render_template_with_fallback('docs/search.html', query='', results=[])

    results = []

    try:
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

    except Exception as e:
        current_app.logger.exception(f"Search failed: {e}")

    return render_template_with_fallback(
        'docs/search.html',
        query=query,
        results=results
    )
