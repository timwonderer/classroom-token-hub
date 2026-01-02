"""
Documentation routes for Classroom Token Hub.

Serves feature-based documentation with markdown rendering,
allowing users to access help without leaving the app or losing their session.
"""

import re
from pathlib import Path
from flask import Blueprint, render_template, abort, current_app, session, request, url_for
import bleach
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

# HTML sanitization configuration for rendered markdown
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

    Note: Multi-line YAML lists (with dashes) are now supported.

    Returns:
        tuple: (metadata_dict, remaining_content)
    """
    if not content.startswith('---'):
        return {}, content

    try:
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        # Simple YAML parsing for basic key: value pairs and lists
        metadata = {}
        front_matter = parts[1].strip()
        current_list_key = None

        for line in front_matter.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Handle list items (YAML dash syntax)
            if line.startswith('- ') and current_list_key:
                item = line[2:].strip().strip('"\'')
                metadata[current_list_key].append(item)
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                current_list_key = None

                # Handle bracket-style lists [item1, item2]
                if value.startswith('[') and value.endswith(']'):
                    inner = value[1:-1].strip()
                    if inner:
                        value = [v.strip().strip('"\'') for v in inner.split(',')]
                    else:
                        value = []
                # Empty value indicates a multi-line list follows
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
    Convert markdown to HTML with extensions and sanitization.

    Args:
        content: Markdown text

    Returns:
        tuple: (sanitized_html_content, sanitized_toc_html)
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

    # Sanitize HTML to prevent XSS
    cleaner = bleach.Cleaner(
        tags=DOCS_ALLOWED_TAGS,
        attributes=DOCS_ALLOWED_ATTRIBUTES,
        protocols=DOCS_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )

    return cleaner.clean(html), cleaner.clean(toc)


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
        category_title = category.replace('-', ' ').replace('_', ' ').title()
        breadcrumbs.append({
            'title': category_title,
            'url': url_for('docs.view_doc', doc_path=category)
        })

    if page:
        page_title = page.replace('-', ' ').replace('_', ' ').title()
        breadcrumbs.append({
            'title': page_title,
            'url': url_for('docs.view_doc', doc_path=f'{category}/{page}')
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
    # Security: Validate input and prevent directory traversal
    try:
        # Reject paths with suspicious characters
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", doc_path):
            current_app.logger.warning(f"Invalid characters in doc path: {doc_path}")
            abort(404)

        # Reject path traversal attempts
        if '..' in doc_path or doc_path.startswith('/'):
            current_app.logger.warning(f"Path traversal attempt: {doc_path}")
            abort(404)

        # Normalize the path
        safe_path = Path(doc_path).with_suffix('.md')

        # Resolve absolute path
        doc_file = (DOCS_ROOT / safe_path).resolve()

        # Ensure the resolved path is within DOCS_ROOT
        if not doc_file.is_relative_to(DOCS_ROOT.resolve()):
            current_app.logger.warning(f"Path outside DOCS_ROOT: {doc_path}")
            abort(404)

        if not doc_file.exists():
            current_app.logger.info(f"Documentation not found: {doc_path}")
            abort(404)

        # Read and parse the file
        content = doc_file.read_text(encoding='utf-8')
        metadata, body = parse_front_matter(content)

        # Convert markdown to HTML (with sanitization)
        html_content, toc = render_markdown_content(body)

        # Determine category and page from path
        path_parts = Path(doc_path).parts
        category = None
        page = None
        if path_parts:
            # First segment is the category
            category = path_parts[0]
            # Remaining segments (if any) form the page path
            if len(path_parts) > 1:
                page = "/".join(path_parts[1:])

        # Build breadcrumbs
        breadcrumbs = build_breadcrumbs(category, page)

        # Get related articles if specified in front matter
        related_articles = []
        if 'related' in metadata:
            related_paths = metadata['related']
            if isinstance(related_paths, str):
                related_paths = [related_paths]
            
            for rel_path in related_paths:
                try:
                    # Remove leading slash and ensure proper path
                    rel_path = rel_path.lstrip('/')
                    related_articles.append({
                        'title': rel_path.replace('/', ' / ').replace('-', ' ').replace('_', ' ').title(),
                        'url': url_for('docs.view_doc', doc_path=rel_path)
                    })
                except Exception as e:
                    current_app.logger.warning(f"Error processing related article {rel_path}: {e}")

        # Get user role for UI filtering
        # Note: Role-based filtering is for UI display only, not access control.
        # All documentation is accessible to all users. The 'roles' metadata
        # is used for contextual highlighting and navigation suggestions.
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
                if not doc_file.is_relative_to(DOCS_ROOT.resolve()):
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

                    # Fallback: if no body line matched (e.g., query only in title),
                    # use description or first non-empty line as context
                    if not context:
                        description = metadata.get('description', '').strip()
                        if description:
                            context = description[:200]
                        else:
                            for line in body.split('\n'):
                                stripped = line.strip()
                                if stripped:
                                    context = stripped[:200]
                                    break

                    results.append({
                        'title': title,
                        'url': url_for('docs.view_doc', doc_path=str(rel_path.as_posix())),
                        'context': context,
                        'category': rel_path.parts[0] if len(rel_path.parts) > 1 else 'Other'
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
