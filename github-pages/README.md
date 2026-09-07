# GitHub Pages Site

This directory is the deployable GitHub Pages source for `classroomtokenhub.com` (see `CNAME`).
`.github/workflows/github-pages-transition.yml` uploads the whole directory as the Pages artifact,
so every file here is published.

- `index.html` — the v2.0 holding page. It carries its own "launching soon" content and does **not**
  link onward to `landing.html`, so deploying the site does not invite anyone into the application.
- `landing.html` — the v2 landing page with sign-in entry points. Deliberately orphaned from the
  site root until launch. It is still published and still answers on a direct URL, so this is not an
  access control: whether the application is reachable is decided by the application.
- `learnmore.html` — the supporting learn-more page, linked from `landing.html`.
- `district.html`, `privacy.html`, `terms.html` — the district brief and legal pages. The
  application redirects `/district`, `/privacy`, and `/terms` here.
- `style.css` — shared stylesheet.

The application does not serve these files. It used to, under `/gh/<path>`, so that a local
certification run could stay on a single origin; that route is gone. Two consequences follow.

First, the artifact is this directory alone, so nothing here may reference `../static/` — it cannot
resolve once published. Fonts must come from a CDN for the same reason.

Second, sign-in links must be absolute to `https://app.classroomtokenhub.com`, because the site and
the application are on different hosts. Nothing rewrites them on the way out any more, so an
absolute link here reaches production from wherever it is opened, including a local preview.

`tests/test_axe_compliance.py` audits every page in this directory against WCAG 2 A and AA by
serving it statically, and fails if a page is added here without being added to its list.
