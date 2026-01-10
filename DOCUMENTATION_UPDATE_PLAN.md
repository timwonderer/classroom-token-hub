# Documentation Update Plan for v1.7 Release

**Created:** 2026-01-09
**Target Version:** 1.7.0
**Status:** Planning

---

## Overview

This document outlines the three-part plan to:
1. Update documentation to reflect v1.7 features
2. Update GitHub Pages with recent changes
3. Implement a landing page architecture with routing to sign-in or documentation

---

## Part 1: Documentation Updates for v1.7

### Recent Features to Document (from CHANGELOG)

#### Analytics Dashboard (Phase 1-3)
- **New Models:** `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
- **Features:**
  - System health observability dashboard
  - CWI-relative metrics (no absolute balances/rankings)
  - Participation rate, money velocity, CWI deviation bands
  - Budget survival pass rate
  - Trend analysis (improving/stable/worsening)
  - Visual alerts with explanations
  - Event annotation system
  - Weekly and monthly time windows
- **Routes:** `/admin/analytics`
- **Documentation Needed:**
  - Teacher manual section on analytics
  - Feature guide for analytics interpretation
  - Diagnostic guide for analytics troubleshooting

#### Mobile Navigation Enhancement
- **Features:**
  - Floating hamburger menu for mobile (<768px)
  - Slide-out sidebar with smooth animation
  - Help buttons visible as icon-only on mobile
  - Contextual help links
  - PWA compatibility
- **Documentation Needed:**
  - Update mobile experience sections
  - Add mobile navigation screenshots
  - Update PWA documentation

#### Rent Itemization Feature
- **New Model:** `RentItem`
- **Features:**
  - Teachers specify what rent pays for
  - Store integration with auto-sync
  - Student view of itemized breakdown
  - Store price comparison
  - Purchase duration options (per_use vs per_period)
  - Dynamic purchase restrictions based on rent status
- **Documentation Needed:**
  - Teacher guide for rent itemization setup
  - Student guide for understanding rent items
  - Feature guide for rent management
  - Diagnostic troubleshooting

#### Rent Privilege Badges
- **Features:**
  - Visual indicators on student detail page
  - Green badges for rent-covered privileges
  - Blue badges for individually purchased items
  - Expiration tracking
- **Documentation Needed:**
  - Update student management documentation
  - Add screenshots of privilege badges

#### Issue Resolution System (v1.5)
- **Models:** `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
- **Features:**
  - Student issue reporting
  - Transaction-specific issues
  - Attendance/tap event issues
  - Teacher review queue
  - Resolution actions (reverse, adjust, deny)
  - Escalation to developer
- **Documentation Status:** ✅ Already documented (v1.5)
- **Action:** Verify completeness

#### ToS Acknowledgment Modal
- **Features:**
  - Modal during admin signup
  - Checkbox for ToS/Privacy Policy
  - `tos_accepted` timestamp recorded
- **Documentation Needed:**
  - Update admin signup documentation

### Files to Update

#### User Guides
- [ ] `docs/user-guides/teacher_manual.md` - Add analytics, rent itemization, mobile navigation sections
- [ ] `docs/user-guides/student_guide.md` - Add rent itemization, privilege badges, mobile navigation

#### Feature Guides
- [ ] Create `docs/features/analytics/interpreting-analytics.md` - How to read the analytics dashboard
- [ ] Update `docs/features/rent/managing-rent.md` - Add itemization features
- [ ] Create `docs/features/rent/itemization-guide.md` - Complete rent itemization setup guide

#### Diagnostic Guides
- [ ] Create `docs/diagnostics/teacher-analytics.md` - Analytics troubleshooting
- [ ] Update `docs/diagnostics/teacher-rent-insurance.md` - Add rent itemization issues
- [ ] Update `docs/diagnostics/student-rent-insurance.md` - Add rent privilege questions

#### Technical Reference
- [ ] `docs/technical-reference/database_schema.md` - Document new models (AnalyticsSnapshot, AnalyticsEvent, AnalyticsAlert, RentItem)
- [ ] `docs/technical-reference/api_reference.md` - Document analytics API endpoints

#### Main Documentation
- [ ] `README.md` - Update version to 1.7.0, add analytics to features list
- [ ] `CHANGELOG.md` - Finalize v1.7.0 section, move from Unreleased to versioned release
- [ ] `DEVELOPMENT.md` - Update current version, mark v1.7 as complete

---

## Part 2: GitHub Pages Update

### Current GitHub Pages Setup

**Branch:** `github-pages`
**File:** No standalone `index.html` found yet (need to create or locate)
**Template:** `templates/docs/index.html` (Jinja template for in-app documentation)
**Setup Guide:** `docs/GITHUB_PAGES_SETUP.md` exists

### GitHub Pages Structure Analysis

The current setup appears to use the Flask app's template system for documentation. We need to determine:
1. Is there a static GitHub Pages site in the `github-pages` branch?
2. Does the documentation live only within the app?
3. Where should the landing page be hosted?

### Actions Needed

#### Option A: Separate Static Landing Page (Recommended)
1. Create `docs/index.html` as a static landing page
2. Configure GitHub Pages to serve from `/docs` folder
3. Landing page includes:
   - Hero section with version badge
   - Feature highlights
   - Two CTA buttons: "Sign In" and "Learn More"
   - "Sign In" → `/admin/login` or `/student/login`
   - "Learn More" → `/docs/help` (in-app documentation)

#### Option B: App-Integrated Landing Page
1. Create a new Flask route `/` that serves landing page
2. Landing page rendered as Jinja template
3. Same button structure as Option A
4. Requires app to be primary entry point

**Recommendation:** Option A for simplicity and GitHub Pages hosting

### GitHub Pages Content to Update

- [ ] Version badge (1.6.0 → 1.7.0)
- [ ] Feature list (add analytics, rent itemization, mobile nav)
- [ ] Screenshots (update to reflect new UI)
- [ ] Statistics (update model count: 41+ models, new features)
- [ ] Release notes link
- [ ] Documentation links

---

## Part 3: Landing Page Architecture

### User Flow Design

```
User visits canonical domain (e.g., classroomtokenhub.com or github.io page)
  ↓
Landing Page
  ├─→ [Sign In] Button → Authentication selection page
  │     ↓
  │     Choose role:
  │     - Student Sign In → /student/login
  │     - Teacher Sign In → /admin/login
  │     - System Admin → /sysadmin/login
  │
  └─→ [Learn More] Button → In-app documentation (/docs/help)
        ↓
        Browse:
        - Student diagnostics
        - Teacher diagnostics
        - Feature guides
        - Technical reference
```

### Implementation Plan

#### Step 1: Create Static Landing Page

File: `docs/index.html`

**Sections:**
1. **Hero Section**
   - Logo/title: "Classroom Token Hub"
   - Tagline: "An interactive banking and classroom management platform for teaching financial literacy"
   - Version badge: "v1.7.0"
   - Two prominent CTAs: "Sign In" and "Learn More"

2. **Features Overview**
   - 6-8 key features with icons
   - Analytics Dashboard
   - Attendance Tracking
   - Classroom Store
   - Banking Simulation
   - Hall Pass System
   - Insurance System
   - Rent Management
   - Mobile PWA

3. **Statistics**
   - 41+ Database Models
   - Full PWA Support
   - Multi-Tenancy Architecture
   - WCAG 2.1 AA Accessibility

4. **Quick Links**
   - GitHub Repository
   - Documentation
   - Release Notes
   - License Information

5. **Footer**
   - License: PolyForm Noncommercial 1.0.0
   - Version information
   - Last updated date

#### Step 2: Create Authentication Selection Page

File: `templates/auth_selection.html` (or use existing login pages)

**Option 1: Unified Selection Page**
- Single page with three large cards:
  - Student Sign In
  - Teacher Sign In
  - System Admin Sign In
- Each card links to respective login page

**Option 2: Direct Links (Simpler)**
- Landing page "Sign In" button goes to dropdown menu or modal
- User selects role, then redirected to appropriate login

**Recommendation:** Option 2 (simpler, less friction)

#### Step 3: Update Routing Logic

**Flask Routes to Add/Modify:**

```python
# app/routes/main.py

@main_bp.route('/')
def index():
    """Landing page - static redirect to GitHub Pages or serve template"""
    # Option A: Redirect to GitHub Pages
    return redirect('https://username.github.io/classroom-economy/')

    # Option B: Serve landing page template
    return render_template('landing.html')

@main_bp.route('/auth')
def auth_selection():
    """Authentication selection page"""
    return render_template('auth_selection.html')
```

**Update existing login routes to handle referrer:**
- If referrer is landing page, show "Back to Home" link
- Breadcrumb navigation: Home > Sign In > [Role]

#### Step 4: Update Navigation

**Add to all templates:**
- Logo link goes to landing page (/)
- "Home" link in breadcrumb navigation
- "Back to Home" option in user menus

**Landing Page Navigation:**
- Sticky header with "Sign In" and "Learn More" buttons
- Smooth scroll to sections
- Mobile-responsive hamburger menu

---

## Implementation Timeline

### Phase 1: Documentation Updates (Week 1)
- Day 1-2: Audit existing docs, identify gaps
- Day 3-4: Write new feature documentation
- Day 5: Update technical reference docs
- Day 6: Update main docs (README, CHANGELOG, DEVELOPMENT)
- Day 7: Review and polish

### Phase 2: GitHub Pages Update (Week 2)
- Day 1: Verify GitHub Pages setup
- Day 2: Create/update static landing page HTML
- Day 3: Add updated screenshots
- Day 4: Update version information
- Day 5: Test GitHub Pages deployment
- Day 6: Configure custom domain (if applicable)
- Day 7: Final QA

### Phase 3: Landing Page Integration (Week 2-3)
- Day 1-2: Design landing page layout
- Day 3: Implement authentication selection
- Day 4: Update Flask routing
- Day 5: Add navigation links
- Day 6: Test complete user flow
- Day 7: Deploy and monitor

---

## Testing Checklist

### Documentation Testing
- [ ] All new documentation renders correctly
- [ ] All links work (no 404s)
- [ ] Screenshots are current and accurate
- [ ] Code examples are tested and work
- [ ] Markdown formatting is correct
- [ ] Navigation structure is logical

### GitHub Pages Testing
- [ ] Landing page loads correctly
- [ ] All sections display properly
- [ ] CTAs work as expected
- [ ] Mobile responsive design verified
- [ ] Page loads quickly (< 3 seconds)
- [ ] Analytics tracking (if configured)

### Landing Page Flow Testing
- [ ] User can access landing page
- [ ] "Sign In" button works
- [ ] "Learn More" button works
- [ ] Authentication selection displays correctly
- [ ] Each login type redirects properly
- [ ] Back navigation works
- [ ] Breadcrumb navigation is accurate
- [ ] Mobile experience is smooth
- [ ] PWA installation still works

---

## Success Criteria

### Documentation
- ✅ All v1.7 features fully documented
- ✅ No broken links
- ✅ All screenshots current
- ✅ Technical accuracy verified

### GitHub Pages
- ✅ Landing page deployed and accessible
- ✅ Version information current (v1.7.0)
- ✅ All CTAs functional
- ✅ Mobile responsive

### Landing Page Architecture
- ✅ Clear user flow (domain → landing → sign in/learn more)
- ✅ Authentication selection works
- ✅ Navigation between sections seamless
- ✅ No broken user journeys

---

## Rollback Plan

If issues arise during implementation:

1. **Documentation:** Revert to previous commit
2. **GitHub Pages:** Use GitHub's environment history to rollback
3. **Landing Page:** Disable route, redirect to existing login pages

---

## Notes and Considerations

### Domain Configuration
- If using custom domain, update CNAME file
- Configure DNS properly (A records or CNAME)
- Enable HTTPS enforcement

### SEO Considerations
- Add meta tags to landing page
- Include proper page titles and descriptions
- Add Open Graph tags for social sharing
- Create sitemap.xml

### Analytics
- Consider adding Google Analytics or Plausible
- Track button clicks (Sign In, Learn More)
- Monitor landing page bounce rate

### Accessibility
- Ensure landing page meets WCAG 2.1 AA
- Test with screen readers
- Verify keyboard navigation
- Check color contrast ratios

### Performance
- Optimize images for web
- Minify CSS/JS if applicable
- Enable caching headers
- Use CDN for static assets (if needed)

---

## Questions to Resolve

1. **Domain Strategy:**
   - Will the app have a custom domain?
   - Should GitHub Pages be primary entry point?
   - Or should the Flask app serve the landing page?

2. **Authentication Flow:**
   - Should there be a unified selection page?
   - Or direct links to each login type?
   - Should students see teacher/admin options?

3. **Documentation Hosting:**
   - Keep in-app documentation (/docs/help)?
   - Mirror on GitHub Pages?
   - Use GitHub Pages exclusively?

4. **GitHub Pages Branch:**
   - Use existing `github-pages` branch?
   - Or serve from `/docs` folder in main branch?

---

**Next Steps:**
1. Review this plan with team/stakeholders
2. Answer outstanding questions
3. Begin Phase 1: Documentation Updates
4. Set up GitHub Pages if not already configured
5. Design and implement landing page

---

**Last Updated:** 2026-01-09
**Document Owner:** Development Team
**Status:** Draft - Awaiting Review
