"""
Documentation routes for Classroom Token Hub.

Serves feature-based documentation with markdown rendering,
allowing users to access help without leaving the app or losing their session.
"""

import re
from pathlib import Path
from flask import Blueprint, abort, current_app, session, request, url_for
import bleach
import markdown
import yaml
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
    Extract YAML-style front matter from markdown content using PyYAML.

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
        # Split on '---' delimiter
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {}, content

        # Parse YAML front matter using PyYAML
        front_matter = parts[1].strip()
        metadata = yaml.safe_load(front_matter) or {}

        # Ensure metadata is a dictionary
        if not isinstance(metadata, dict):
            current_app.logger.warning(f"Front matter is not a dict: {type(metadata)}")
            return {}, content

        return metadata, parts[2].strip()
    except yaml.YAMLError as e:
        current_app.logger.warning(f"Failed to parse YAML front matter: {e}")
        return {}, content
    except Exception as e:
        current_app.logger.warning(f"Unexpected error parsing front matter: {e}")
        return {}, content


def render_markdown_content(content):
    """
    Convert markdown to HTML with extensions and sanitization.

    Args:
        content: Markdown text

    Returns:
        tuple: (sanitized_html_content, sanitized_toc_html)

    Note: The 'nl2br' extension is intentionally omitted to avoid unexpected
    line breaks in formatted content like code blocks and tables. Standard
    markdown requires two spaces at the end of a line or a blank line for breaks.
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
        # Normalize basic string form and reject empty/whitespace-only paths
        doc_path = (doc_path or "").strip()
        if not doc_path:
            current_app.logger.warning("Empty doc path")
            abort(404)

        # Reject paths with suspicious characters
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", doc_path):
            current_app.logger.warning(f"Invalid characters in doc path: {doc_path}")
            abort(404)

        def resolve_doc_path(untrusted_path: str, docs_root: Path) -> Path:
            """
            Resolve an untrusted documentation path to a safe file within docs_root.
            """
            safe_rel_path = Path(untrusted_path)

            # Reject absolute paths or traversal components early
            if safe_rel_path.is_absolute() or any(part == ".." for part in safe_rel_path.parts):
                current_app.logger.warning(f"Path traversal attempt: {untrusted_path}")
                abort(404)

            # Resolve absolute path under the documentation root and ensure containment
            root_resolved = docs_root.resolve()
            candidate = (root_resolved / safe_rel_path).with_suffix('.md').resolve()
            try:
                candidate.relative_to(root_resolved)
            except ValueError:
                current_app.logger.warning(f"Path outside DOCS_ROOT: {untrusted_path}")
                abort(404)

            return candidate

        docs_root = DOCS_ROOT
        doc_file = resolve_doc_path(doc_path, docs_root)

        if not doc_file.exists():
            current_app.logger.info(f"Documentation not found: {doc_path}")
            abort(404)

        # Read and parse the file
        try:
            content = doc_file.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            current_app.logger.error(f"File encoding error for {doc_path}: {e}")
            abort(500, description="Unable to read documentation file (encoding error)")

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

    except (OSError, IOError) as e:
        current_app.logger.error(f"File system error rendering {doc_path}: {e}")
        abort(500, description="Unable to access documentation file")
    except Exception as e:
        current_app.logger.exception(f"Unexpected error rendering documentation: {e}")
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
        # Note: This implementation reads all files on every search request.
        # For production with many documentation files, consider implementing
        # a search index (in-memory or cached) built at startup for better performance.
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
            except (UnicodeDecodeError, OSError, IOError) as e:
                current_app.logger.warning(f"Error reading file {doc_file}: {e}")
                continue
            except Exception as e:
                current_app.logger.warning(f"Unexpected error searching {doc_file}: {e}")
                continue

    except (OSError, IOError) as e:
        current_app.logger.error(f"File system error during search: {e}")
    except Exception as e:
        current_app.logger.exception(f"Unexpected error during search: {e}")

    return render_template_with_fallback(
        'docs/search.html',
        query=query,
        results=results
    )
