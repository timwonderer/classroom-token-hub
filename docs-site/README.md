# Developer Documentation Site

Docusaurus workspace that publishes the developer-facing documentation tree to
GitHub Pages at <https://classroomtokenhub.com/docs/>.

## What this site publishes

Content is read directly out of `../docs`. Nothing is copied or mirrored, so
there is never a second, drifting version of a normative document.

| Published                                   | Not published                          |
|---------------------------------------------|----------------------------------------|
| `docs/INVARIANT/` (INV-CORE, INV-ARC)        | `docs/user-guides/` — the Flask app owns it |
| `docs/DOMAIN/` (DOM-*)                       | `docs/archive/` — superseded v1 material |
| `docs/FEATURE-EXECUTION/` (FEAT-*)           | `docs/assets/`                          |
| `docs/SPEC/`, `docs/STANDARD_OPERATING_PROCEDURES/` |                                 |
| `docs/MAP/`, `docs/REFERENCE/`, `docs/PRINCIPLES/`  |                                 |
| `docs/TRACKING/`, `docs/ops/`, `docs/self-hosting/` |                                 |

### The serving boundary

The application serves exactly one documentation tree — `docs/user-guides`, the
in-app help centre at `app.classroomtokenhub.com/docs/`. Everything else is
developer-facing and belongs here. This is an ownership split, not access
control: the repository is public either way. Serving the same file from both
places would mean two renderers, two navigations, and two sets of stale links.

The boundary is enforced in three places, which must agree:

- `app/utils/helpers.py` — `is_user_guide_doc_path`, `docs_url_for`
- `app/routes/docs.py` — `_redirect_to_public_docs`
- `docusaurus.config.js` — the docs plugin `exclude` list

`tests/dom/docs/test_docs_platform_split.py` pins that agreement.

## Local development

Requires Node.js 20 or newer.

```bash
cd docs-site
npm install
npm run start
```

The dev server mounts the site at its configured base URL, so the local entry
point is <http://127.0.0.1:3000/docs/>.

To reproduce the deployed output:

```bash
npm run build
npm run serve
```

`npm run build` fails on a broken internal link, a broken anchor, or a broken
relative markdown link. A renamed or deleted document under `docs/` therefore
breaks the Pages build rather than shipping a dead link.

## Brand conformance

`SPEC-DES-001` §XIII: this workspace keeps its own stylesheet and sits outside
the runtime token layer, but it is a brand surface and must not contradict the
canonical values in §VI.4.

- `src/css/tokens.css` is the only place a design value appears as a literal.
  It transcribes the base layer plus the Teacher (Advisor Green) theme from
  `static/css/tokens.css` — a documentation reader holds no role, so the site
  carries the default identity.
- `src/css/custom.css` maps Infima's variables onto those tokens and states no
  value of its own. Infima declares its palette at `:root:not(#\#):not(#\#)`,
  two id-worth of specificity, so overrides here carry the same escape hatch.
- `src/css/fonts.css` serves the same self-hosted woff2 files the application
  ships — Inter, Atkinson Hyperlegible Next, IBM Plex Mono. Material Symbols is
  subset to the three glyphs the wordmark uses (1.6KB, not 3.9MB). Refresh the
  application's copies with `scripts/vendor_fonts.py` and re-copy them into
  `src/fonts/`.
- The brand mark is the three-row text wordmark (§IX), rendered in
  `src/pages/index.js` to match `templates/macros/docs_hero.html`. No logo file
  is used, and none may be added.
- The colour-mode switch is off. The design system defines one identity per
  role and all three are light; a dark theme would have to invent brand values
  §VI.4 does not define.

`tests/dom/docs/test_docs_site_brand_conformance.py` compares this site's
tokens against the application's and fails on drift.

## Configuration

| Environment variable   | Default                              | Purpose                                   |
|------------------------|--------------------------------------|-------------------------------------------|
| `DOCS_SITE_URL`        | `https://classroomtokenhub.com`      | Canonical origin used for absolute URLs    |
| `DOCS_SITE_BASE_URL`   | `/docs/`                             | Path the site is mounted at                |
| `APP_DOCS_ORIGIN`      | `https://app.classroomtokenhub.com`  | Where the in-app help centre is linked from |

## Deployment

`.github/workflows/github-pages.yml` assembles one Pages artifact:

```text
/           github-pages/        static marketing and policy pages
/docs/      docs-site/build/     this site
```

It runs on pushes to `main` that touch `docs/`, `docs-site/`, or
`github-pages/`, and builds (without deploying) on matching pull requests.

## Forwarding from the app

`route-map.json` holds *exceptions only*. A developer-facing path requested at
`app.classroomtokenhub.com/docs/<path>` forwards to `<docs site>/<path>`
unchanged, because this site publishes the tree at its repository-relative
paths. Entries exist only for documents whose path changed on the way over
(for example the retired `ARC-*` namespace). `docs/user-guides` is never listed:
forwarding it would take the working help centre off the application.

Forwarding is active only when `EXTERNAL_DOCS_BASE_URL` is set on the app.
