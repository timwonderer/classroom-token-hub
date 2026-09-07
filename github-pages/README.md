# GitHub Pages Site

This directory is the deployable GitHub Pages source for `classroomtokenhub.com` (see `CNAME`).
`.github/workflows/github-pages-transition.yml` uploads the whole directory as the Pages artifact,
so every file here is published.

- `index.html` — the v2 landing page, carrying the three sign-in entry points.
- `learnmore.html` — the supporting learn-more page, linked from `index.html`.
- `district.html`, `privacy.html`, `terms.html` — the district brief and legal pages. The
  application redirects `/district`, `/privacy`, and `/terms` here.
- `style.css` — shared stylesheet.

**This is the launch branch.** On `main`, `index.html` is the "launching soon" holding page and
there is no learn-more page: publishing a page with live sign-in buttons and merely not linking to
it removes the invitation to sign in while leaving the access, since an unlinked page still answers
on a direct URL. Not deploying the file is the difference between those two claims.

The landing page arrives here *as* `index.html` rather than beside it, so there is no interval in
which the front door and the holding page both exist and disagree about whether the product has
launched. There is no `landing.html` at any point: a second filename serving the same page would be
a second front door to keep in sync, and nothing ever linked to that name, since the file was never
deployed. Merging this branch is the act of launching.

The application does not serve these files. It used to, under `/gh/<path>`, so that a local
certification run could stay on a single origin; that route is gone. Two consequences follow.

First, the artifact is this directory alone, so nothing here may reference `../static/` — it cannot
resolve once published. Fonts must come from a CDN for the same reason.

Second, sign-in links must be absolute to `https://app.classroomtokenhub.com`, because the site and
the application are on different hosts. Nothing rewrites them on the way out any more, so an
absolute link here reaches production from wherever it is opened, including a local preview.

`tests/test_axe_compliance.py` audits every page in this directory against WCAG 2 A and AA by
serving it statically. It asserts its list equals the `.html` files actually present, so a page
cannot be added here without being audited — which is also what makes the launch merge safe:
`learnmore.html` fails the suite until it is listed again.
