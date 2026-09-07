# GitHub Pages Site

This directory is the deployable GitHub Pages source for `classroomtokenhub.com` (see `CNAME`).
`.github/workflows/github-pages-transition.yml` uploads the whole directory as the Pages artifact,
so every file here is published.

- `index.html` — the v2.0 "launching soon" holding page.
- `district.html`, `privacy.html`, `terms.html` — the district brief and legal pages. The
  application redirects `/district`, `/privacy`, and `/terms` here.
- `style.css` — shared stylesheet.

The v2 landing page and its learn-more companion are **not here before launch**. They live on
`launch/v2-landing-pages`, whose entire diff against this branch is those two files plus their
entries in the audit list, and they arrive when that branch is merged. Orphaning them from the site
root was considered first and rejected: an unlinked page is not an unreachable one, so publishing
`landing.html` with its three sign-in buttons and merely not linking to it would have removed the
invitation to sign in while leaving the access, at a direct URL, to anyone who guessed the filename.
Not deploying the file is the difference between those two claims.

The application does not serve these files. It used to, under `/gh/<path>`, so that a local
certification run could stay on a single origin; that route is gone. Two consequences follow.

First, the artifact is this directory alone, so nothing here may reference `../static/` — it cannot
resolve once published. Fonts must come from a CDN for the same reason.

Second, sign-in links must be absolute to `https://app.classroomtokenhub.com`, because the site and
the application are on different hosts. Nothing rewrites them on the way out any more, so an
absolute link here reaches production from wherever it is opened, including a local preview.

`tests/test_axe_compliance.py` audits every page in this directory against WCAG 2 A and AA by
serving it statically. It asserts its list equals the `.html` files actually present, so a page
cannot be added here without being audited — which is also what makes the launch merge safe: the two
returning pages fail the suite until they are listed again.
