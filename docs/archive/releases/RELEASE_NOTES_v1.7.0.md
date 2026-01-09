# Release Notes - Version 1.7.0

**Release Date**: TBD (January 2026)  
**Focus**: Analytics Dashboard, Rent Itemization, Mobile Navigation, and Documentation Organization

---

## Highlights

- **Analytics Dashboard** - System health observability with CWI-relative metrics and actionable insights
- **Rent Itemization** - Teachers can specify what rent pays for and offer items as store alternatives
- **Enhanced Mobile Navigation** - Full navigation menu accessible on mobile devices and PWA
- **Rent Privilege Badges** - Visual indicators showing active rent privileges on student detail pages
- **Documentation Organization** - Improved repository structure with archived historic files

---

## New Features

### Analytics Dashboard (Phase 1-3)

System health observability dashboard per analytics specification, providing teachers with actionable insights about their classroom economy.

**Key Features**:
- Three new database models: `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
- Analytics computation engine with CWI-relative metrics (no absolute balances/rankings)
- System health metrics:
  - Participation rate
  - Money velocity
  - CWI deviation bands
  - Budget survival pass rate
- Trend analysis: tracks improving/stable/worsening patterns across periods
- Visual alerts with explanations (what changed, why it matters, suggested actions)
- Event annotation system for rent changes, wage changes, inflation events
- Metrics precomputed and cached by time window for 5-second readability
- Weekly and monthly time window views
- All metrics properly scoped by `join_code` for multi-tenancy compliance

**Access**: Dashboard route at `/admin/analytics`

**API Endpoints**: Snapshot data and alerts available via API

**Database Migration**: `a7b8c9d0e1f2_add_analytics_models`

**Design Principle**: "Something is drifting — and I know what lever to pull"

**Privacy**: No student names in default views, no leaderboards, no comparative rankings per specification

**Testing**: Comprehensive test coverage for analytics engine

---

### Rent Itemization (MVP)

Teachers can now specify what rent pays for and offer items as store alternatives, creating flexible rent payment options.

**Key Features**:
- New `RentItem` model to track itemized rent components (e.g., Desk, Chair, Locker)
- Teachers can add/remove/reorder rent items in Rent Settings page
- Optional store integration: mark items as "Available in Store" with custom pricing
- Automated sync: items marked for store availability automatically create/update StoreItem records
- StoreItem created with `limit_per_student=1` to enforce single-purchase behavior
- Store items inherit block visibility from rent settings
- Student rent view displays itemized breakdown showing what rent includes
- Students see store price comparison for items available separately
- Pro tip message encourages rent payment by showing total value comparison
- Manual pricing (teacher sets store price manually)

**Database Migration**: `6feaa660d6c3_add_rent_item_table`

**Future Enhancement**: Automatic pricing calculator (coming in future release)

---

### Enhanced Purchase Restrictions

"Prevent Purchase When Late" toggle now has dynamic behavior based on itemization status.

**Behavior**:
- **When rent itemization is disabled**: Blocks ALL store purchases when student is late on rent (original behavior)
- **When rent itemization is enabled**: Students late on rent can ONLY purchase items covered by rent (at à la carte prices), all other store items blocked

**Incentive Structure**: 
- Pay rent to get everything included
- Or buy individual rent items at higher prices while missing out on other store items

**Implementation**: 
- UI dynamically updates toggle label and description based on itemization status
- JavaScript updates label when items are added/removed dynamically
- Implemented in `/api/purchase-item` endpoint with proper rent late detection and item validation

---

### Purchase Duration Options for Rent Items

Teachers can now choose how long individually-purchased rent items last.

**Options**:
- **Per Use**: Student must buy each time they want to use it (unlimited purchases allowed)
- **Per Rent Period**: Student buys once and can use until next rent is due (limit 1, expires when rent comes due)

**Features**:
- Radio button selector in rent itemization UI with clear explanations
- Store items automatically configured with appropriate purchase limits based on duration type
- Purchase API calculates expiration dates for "per_period" items based on rent frequency settings
- Automated expiration when next rent payment is due

**Database Migration**: `h7i8j9k0l1m2_add_purchase_duration_to_rent_items`

---

### Rent Privilege Badges

Visual indicators on student detail page showing active rent privileges.

**Badge Types**:
- **Green badges**: Privileges covered by paid rent (automatic for rent-paying students)
- **Blue badges**: Privileges purchased individually (shows "(Purchased)" label)

**Features**:
- Displays all "per_period" rent items that students currently have access to
- Badges only show for non-expired privileges
- Rent-paying students automatically receive all per-period privilege badges
- Teachers can quickly see which students have which privileges at a glance
- Hover over badges to see item descriptions

---

### Mobile Navigation Enhancement

Full navigation menu now accessible on mobile devices and PWA, resolving a critical usability limitation.

**Key Features**:
- Added floating hamburger menu button that appears on mobile (<768px)
- Sidebar slides in from left with smooth animation and backdrop overlay
- Help buttons now visible as icon-only on mobile screens
- Contextual help links show icon on mobile, hiding text to save space
- Same template works for desktop, mobile, and PWA - no separate mobile templates needed
- Sidebar automatically closes when clicking navigation links or backdrop

**Impact**: Resolves PWA limitation where full navigation menu was previously inaccessible

---

## Bug Fixes

### Analytics Events Value Display
Show zero-value economy changes in the analytics events timeline by checking for `None` instead of falsy values.

**Impact**: Zero-value events (like setting rent to $0) were not being displayed in the analytics timeline.

---

### EasyMDE Form Submission

Fixed issue where forms with EasyMDE markdown editors could not be submitted due to hidden required fields.

**Problem**: EasyMDE markdown editor hides the underlying textarea, causing browser validation to fail on required fields. This resulted in the console error: "An invalid form control with name='[field]' is not focusable"

**Resolution**:
- Removed HTML `required` attribute from hidden textareas after editor initialization
- Server-side validation via `DataRequired()` still enforces required fields
- Applied fix to insurance claim form (`student_file_claim.html`) and issue submission form (`student_submit_issue.html`)

---

## Documentation & Repository Organization

### Documentation Organization

Improved repository structure and documentation consistency.

**Changes**:
- Moved historic audit files to `docs/archive/`:
  - `MULTI_TENANCY_AUDIT_RESULTS.md`
  - `MULTI_TENANCY_VIOLATIONS_AUDIT.md`
  - `SECURITY_FIXES_SUMMARY.md`
  - `MIGRATION_TOTP_ENCRYPTION.md`
  - `IMPLEMENTATION_PROGRESS.md`
- Consolidated duplicate documentation with pointers to canonical versions:
  - Root `CHANGELOG.md` is source of truth (per Keep a Changelog standard)
  - Root `CLAUDE.md` is source of truth (for AI assistants)
  - Root `PROJECT_HISTORY.md` is source of truth (project philosophy)
- Updated documentation routing to include analytics specification
- Updated all references to moved files in CHANGELOG and release notes
- Improved navigation and file organization

---

## Database Migrations

This release includes three database migrations:

1. **`a7b8c9d0e1f2_add_analytics_models`** - Analytics dashboard tables
2. **`6feaa660d6c3_add_rent_item_table`** - Rent itemization support
3. **`h7i8j9k0l1m2_add_purchase_duration_to_rent_items`** - Purchase duration field

**Migration Command**:
```bash
flask db upgrade
```

**Rollback** (if needed):
```bash
flask db downgrade
```

---

## Upgrade Notes

### For Existing Deployments

1. **Pull latest code**:
   ```bash
   git pull origin main
   ```

2. **Run database migrations**:
   ```bash
   flask db upgrade
   ```

3. **Restart application**:
   ```bash
   sudo systemctl restart classroom-token-hub
   ```

### Breaking Changes

None. This release is fully backward compatible.

### New Routes

- `/admin/analytics` - Analytics dashboard (teachers only)
- API endpoints for analytics data (internal use)

### Documentation Updates

If you have bookmarked any of the following documentation files, note they have been moved:
- `MULTI_TENANCY_AUDIT_RESULTS.md` → `docs/archive/MULTI_TENANCY_AUDIT_RESULTS.md`
- `MULTI_TENANCY_VIOLATIONS_AUDIT.md` → `docs/archive/MULTI_TENANCY_VIOLATIONS_AUDIT.md`
- `SECURITY_FIXES_SUMMARY.md` → `docs/archive/SECURITY_FIXES_SUMMARY.md`
- `MIGRATION_TOTP_ENCRYPTION.md` → `docs/archive/MIGRATION_TOTP_ENCRYPTION.md`
- `IMPLEMENTATION_PROGRESS.md` → `docs/archive/IMPLEMENTATION_PROGRESS.md`

---

## Testing

All new features have been tested with:
- Unit tests for analytics computation engine
- Integration tests for rent itemization
- Manual testing for mobile navigation
- Multi-tenancy compliance verification

---

## Known Limitations

### Rent Itemization
- Manual pricing only (teacher sets store price manually)
- Automatic pricing calculator planned for future release

### Analytics Dashboard
- Phase 1-3 complete (system health metrics)
- Future phases may include additional metrics and visualizations

---

## Contributors

Thanks to all contributors who helped with this release through testing, feedback, and code review.

---

## What's Next

Version 1.8.0 will focus on:
- Additional analytics features
- Enhanced reporting capabilities
- Performance optimizations
- User experience improvements

See [DEVELOPMENT.md](../../DEVELOPMENT.md) for the full roadmap.

---

**Last Updated**: 2026-01-09
**Release Status**: Draft (pending testing and final review)
