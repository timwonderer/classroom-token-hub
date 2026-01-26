# GitHub Pages Configuration

**Last Updated:** January 9, 2026
**Version:** 1.7.0

---

## Overview

This directory (`/docs`) serves dual purposes:
1. **Project Documentation** - Markdown files for features, guides, and technical reference
2. **GitHub Pages Site** - Static landing page at `docs/index.html`

### Important: Documentation Privacy

**Markdown files are NOT served on GitHub Pages.** Only `index.html` is accessible.

- Markdown documentation (`.md` files) exists in this directory for version control
- The landing page (`index.html`) does NOT link to local markdown files
- All documentation links point to GitHub repository URLs: `https://github.com/timwonderer/classroom-economy/blob/main/docs/...`
- Users who click "Documentation" links will view files on GitHub, not GitHub Pages
- `.nojekyll` file prevents GitHub from processing markdown files

**Why this matters:**
- Documentation is visible only through GitHub repository
- Landing page shows only the curated features and screenshots
- No accidental exposure of internal documentation
- Clean separation between public landing page and project docs

---

## GitHub Pages Setup

### Current Configuration

**Source:** `/docs` folder on `main` branch
**URL:** `https://timwonderer.github.io/classroom-economy/`
**Entry Point:** `docs/index.html`

### Enabling GitHub Pages

If not already enabled:

1. Go to repository Settings → Pages
2. Under "Source", select:
   - Branch: `main`
   - Folder: `/docs`
3. Click "Save"
4. Wait 2-3 minutes for deployment
5. Visit: `https://timwonderer.github.io/classroom-economy/`

### Landing Page Features

The `index.html` landing page includes:

**Navigation:**
- Sticky header with logo
- "Sign In" button (scrolls to sign-in section)
- "Learn More" button (scrolls to features/screenshots)

**Sign In Section:**
- Student Sign In → `/student/login`
- Teacher Sign In → `/admin/login`
- System Admin Sign In → `/sysadmin/login`

**Content Sections:**
1. **Hero** - Version badge, tagline, CTA buttons
2. **Features** - 9 feature cards with v1.7 highlights
3. **Stats** - Key metrics (41+ models, WCAG 2.1, etc.)
4. **Screenshots** - Student dashboard and store view
5. **Sign In** - Role-based login cards
6. **CTA** - Documentation and download links
7. **Footer** - Links to docs, community, legal

---

## File Structure

```
docs/
├── index.html                  # GitHub Pages landing page (THIS)
├── README.md                   # Documentation index
├── GITHUB_PAGES_SETUP.md       # Setup instructions
├── README_GITHUB_PAGES.md      # This file
├── DEPLOYMENT.md               # Production deployment
├── PWA_ICON_REQUIREMENTS.md    # PWA icons and mobile nav
├── features/                   # Feature documentation
│   ├── analytics/
│   └── rent/
├── diagnostics/                # Troubleshooting guides
├── user-guides/                # Teacher and student manuals
├── technical-reference/        # Architecture, database, API
└── operations/                 # Deployment and updates
```

---

## Production Configuration

**GitHub Pages URL:** `https://timwonderer.github.io/classroom-economy/`
**App Domain:** `https://classroomtokenhub.com`

All sign-in links on the landing page point to the production Flask application:
- Student Sign In → `https://classroomtokenhub.com/student/login`
- Teacher Sign In → `https://classroomtokenhub.com/admin/login`
- System Admin Sign In → `https://classroomtokenhub.com/sysadmin/login`

**Benefits of this setup:**
- ✅ Landing page remains accessible even if Flask server goes down
- ✅ GitHub Pages provides reliable, free hosting for landing page
- ✅ Sign-in links direct users to the production application
- ✅ Clean separation between static content (GitHub Pages) and dynamic app (Flask)

---

## User Flow Design

### Landing Page → Sign In → App

```
User visits https://timwonderer.github.io/classroom-economy/
  ↓
Sees landing page (index.html)
  ↓
Clicks "Sign In" button
  ↓
Scrolls to sign-in section
  ↓
Chooses role (Student/Teacher/Admin)
  ↓
Redirected to https://classroomtokenhub.com/student|admin|sysadmin/login
  ↓
Logs in to Flask app at classroomtokenhub.com
```

### Landing Page → Learn More → Documentation

```
User visits github.io/classroom-economy
  ↓
Sees landing page (index.html)
  ↓
Clicks "Learn More" button
  ↓
Scrolls to features and screenshots
  ↓
Can explore:
  - Feature descriptions
  - Screenshots
  - GitHub repository
  - Documentation links in footer
```

---

## Customization

### Updating Version Badge

In `index.html`, find:
```html
<span class="version-badge">🎉 Version 1.7.0 Released</span>
```

Update to new version on releases.

### Updating Features

In `index.html`, find the `.features-grid` section and add/modify feature cards:
```html
<div class="feature-card">
    <div class="feature-icon">📊</div>
    <h3>Feature Name<span class="feature-new">NEW</span></h3>
    <p>Feature description...</p>
</div>
```

### Updating Screenshots

1. Add new screenshots to `static/images/`
2. Update `index.html` in `.screenshots-grid` section:
```html
<div class="screenshot-card">
    <img src="../static/images/your-screenshot.png" alt="Description">
    <div class="screenshot-caption">Caption</div>
</div>
```

### Updating Sign-In Links

If app routes change, update in `index.html`:
```html
<a href="/student/login" class="btn btn-primary">Sign In as Student</a>
<a href="/admin/login" class="btn btn-primary">Sign In as Teacher</a>
<a href="/sysadmin/login">sign in here</a>
```

---

## Styling

### Color Scheme

Defined in CSS `:root` variables:
```css
--primary: #1a4d47;       /* Main brand color */
--secondary: #d4a574;     /* Accent color */
--accent: #4a9d94;        /* Feature highlights */
--text-dark: #2c3e50;     /* Body text */
--text-light: #6c757d;    /* Secondary text */
```

### Responsive Design

Mobile breakpoint: `768px`
- Hero text scales down
- Navigation stacks vertically
- Screenshot grid becomes single column
- Feature cards remain responsive (auto-fit)

---

## Testing Locally

### Option 1: Python Simple Server

```bash
cd docs
python3 -m http.server 8000
```
Visit: `http://localhost:8000`

### Option 2: Live Server (VS Code)

1. Install "Live Server" extension
2. Right-click `docs/index.html`
3. Select "Open with Live Server"

### Option 3: Flask App

The landing page can also be integrated into the Flask app as the root route `/`.

---

## Integration with Flask App (Part 3)

### Option A: GitHub Pages Primary (Current)

- GitHub Pages hosts landing page
- Flask app handles authentication and app routes
- Sign-in links point to Flask app routes

**Pros:**
- Simple deployment
- GitHub handles hosting
- No changes to Flask app needed

**Cons:**
- Two separate sites
- Different domains (unless custom domain)

### Option B: Flask Serves Landing Page (Future)

- Copy `docs/index.html` to `templates/landing.html`
- Create route: `@main_bp.route('/')`
- Update asset paths to use Flask's `url_for('static', ...)`

**Pros:**
- Single deployment
- One domain
- Better integration

**Cons:**
- More complex deployment
- Need to manage static assets

---

## Deployment Checklist

Before deploying GitHub Pages updates:

- [ ] Version badge updated
- [ ] Feature list reflects latest release
- [ ] Screenshots are current
- [ ] All links tested and working
- [ ] Responsive design verified on mobile
- [ ] Footer links point to correct docs
- [ ] Sign-in routes match app routes
- [ ] Tested locally with HTTP server

---

## Maintenance

### When to Update

**On Major Releases (1.x.0):**
- Update version badge
- Add new feature cards
- Update statistics if changed
- Add new screenshots

**On Minor Releases (1.x.y):**
- Update version in footer
- Optional: Update feature descriptions

**As Needed:**
- Fix broken links
- Update screenshots
- Refresh content
- Improve SEO/metadata

### Link Health

Periodically check:
- All external links (GitHub, docs)
- All internal anchors (#signin, #learn-more)
- Sign-in routes match app
- Image paths resolve correctly

---

## SEO & Metadata

### Current Meta Tags

```html
<meta name="description" content="...">
<meta name="keywords" content="...">
<meta property="og:*" content="...">   <!-- Open Graph -->
<meta property="twitter:*" content="...">  <!-- Twitter Cards -->
```

### Improving SEO

1. Keep description under 160 characters
2. Use relevant keywords
3. Update Open Graph images
4. Add structured data (optional)
5. Submit to Google Search Console

---

## Custom Domain (Optional)

To use custom domain (e.g., `classroomtokenhub.com`):

1. **Configure DNS:**
   - Add CNAME record: `www` → `timwonderer.github.io`
   - Add A records to GitHub Pages IPs

2. **Add CNAME file:**
   ```bash
   echo "www.classroomtokenhub.com" > docs/CNAME
   ```

3. **Enable in GitHub:**
   - Settings → Pages → Custom domain
   - Enter: `www.classroomtokenhub.com`
   - Check "Enforce HTTPS"

4. **Wait for DNS propagation** (24-48 hours)

---

## Troubleshooting

### Page Not Loading

**Check:**
- GitHub Pages enabled in settings?
- Correct branch and folder selected?
- Wait 2-3 minutes after enabling
- Check GitHub Actions for build errors

**Solutions:**
- Force rebuild: Make dummy commit to docs/
- Clear browser cache
- Check repository visibility (public?)

### Links Not Working

**Check:**
- Absolute vs. relative paths
- Case sensitivity in filenames
- Trailing slashes
- URL encoding

**Solutions:**
- Test all links locally first
- Use browser dev tools to inspect 404s
- Verify routes exist in Flask app

### Styles Not Applying

**Check:**
- CSS syntax errors
- Browser compatibility
- Cached old styles

**Solutions:**
- Validate CSS
- Hard refresh (Ctrl+Shift+R)
- Test in multiple browsers

### Images Not Loading

**Check:**
- File paths relative to `docs/index.html`
- File names (case-sensitive)
- Image formats supported

**Solutions:**
- Use `../static/images/` for images
- Verify files exist in repository
- Check file permissions

---

## Related Documentation

- **[GitHub Pages Setup](GITHUB_PAGES_SETUP.md)** - Detailed setup instructions
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment
- **[Documentation Plan](../DOCUMENTATION_UPDATE_PLAN.md)** - Part 2 & 3 plan

---

## Next Steps: Part 3

Part 3 will implement Flask integration:

1. **Create authentication selection page** in Flask templates
2. **Add root route** that serves landing page or redirects
3. **Update navigation** to include "Home" link
4. **Test complete flow** from landing → sign in → app

---

**Status:** Part 2 Complete - GitHub Pages Ready
**Next:** Part 3 - Flask Landing Page Integration
**Last Updated:** January 9, 2026
