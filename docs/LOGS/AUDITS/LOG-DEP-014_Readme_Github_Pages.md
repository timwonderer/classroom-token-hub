# GitHub Pages Configuration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-014| 1.1 | 2026-03-08 | 1.0 |Normative|

**Last Updated:** February 9, 2026  
**Version:** 1.8.0

---

## Overview

The `/docs` directory serves two purposes:

1. **Project Documentation** - Markdown files for guides, diagnostics, and technical reference
2. **GitHub Pages Site** - Static landing pages (`index.html` and `about.html`)

### Documentation Privacy

**Markdown files are NOT served on GitHub Pages.** Only static HTML assets are public.

- `.nojekyll` prevents GitHub from rendering markdown
- Docs links on the landing pages point to the GitHub repository or the app docs route
- Internal and operational docs remain in the repo, not on the public site

---

## GitHub Pages Setup

**Source:** `/docs` folder on `main` branch  
**URL:** `https://timwonderer.github.io/classroom-economy/`  
**Entry Points:** `docs/index.html`, `docs/about.html`

### Enabling GitHub Pages

1. Repository Settings → Pages
2. Source:
   - Branch: `main`
   - Folder: `/docs`
3. Save and wait 2-3 minutes for deployment

---

## Landing Pages

### `index.html`

Minimal sign-in hub:

- Student sign-in link
- Teacher sign-in link
- About page link

### `about.html`

Marketing and feature overview page:

- Version banner and release highlights
- Feature grid and system stats
- Screenshots section
- Sign-in call-to-action

---

## Production Links

**App Domain:** `https://app.classroomtokenhub.com`

Sign-in links:

- Student → `https://app.classroomtokenhub.com/student/login`
- Teacher → `https://app.classroomtokenhub.com/admin/login`
- System Admin → `https://app.classroomtokenhub.com/sysadmin/login` (about page only)

Docs links:

- App docs → `https://app.classroomtokenhub.com/docs`
- GitHub docs → repository markdown URLs

---

## File Structure

```
docs/
├── index.html                  # GitHub Pages landing page
├── about.html                  # GitHub Pages marketing page
├── style.css                   # Shared landing page styles
├── .nojekyll                   # Prevents GitHub from rendering markdown
├── README.md                   # Documentation index
├── user-guides/                # User-facing guides and diagnostics
├── technical-reference/        # Architecture, database, API
├── development/                # Internal policies and standards
├── operations/                 # Deployment and maintenance
├── security/                   # Security audits and reports
└── archive/                    # Historical and frozen docs
```

---

## Updating for New Releases

1. **Update version banner** in `about.html`
2. **Refresh feature highlights** if the release adds visible functionality
3. **Verify sign-in and docs links** still point to current routes
4. **Update screenshots** if UI changes are significant

---

## Testing Locally

```bash
cd docs
python3 -m http.server 8000
```

Visit: `http://localhost:8000`

---

## Related Documentation

- **[GitHub Pages Setup](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-007_Github_Pages_Setup.md)** - Setup steps and troubleshooting
- **[Deployment Guide](../../STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md)** - Production deployment
- **[Documentation Index](../../README.md)** - Full docs map

---

**Status:** GitHub Pages Active  
**Next Review:** Next major release
