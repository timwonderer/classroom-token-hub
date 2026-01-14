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
**Status:** ✅ Complete (Smart Routing Implemented)

### User Flow Design
- Implemented "Smart Routing" on Root Path (`/`)
- **Unauthenticated:** Redirects to Marketing Site (`classroomtokenhub.com`)
- **Authenticated:** Redirects to corresponding Dashboard
- **Login Pages:** Strict "Logout on Visit" policy maintained for security.

### Implementation Verified
- [x] Step 1: Create Static Landing Page (Hosted on GitHub Pages)
- [x] Step 2: Create Authentication Selection Page (Handled by Marketing Site "Sign In" flow)
- [x] Step 3: Update Routing Logic (`main.py` updated with smart routing)
- [x] Step 4: Update Navigation (Links point to correct domains)

---

## Testing Verification
- [x] User visits canonical domain -> Marketing Site (GitHub Pages)
- [x] "Sign In" -> Redirects to App Login
- [x] Authenticated users visiting Root -> Dashboard
- [x] Authenticated users visiting Login -> Session Cleared (Security Requirement Met)

---

**Last Updated:** 2026-01-10
**Status:** Complete

