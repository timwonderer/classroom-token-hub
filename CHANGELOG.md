# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.


## [Unreleased]

### Fixed
- **P0: Duplicate auto-tap-out events causing payroll overpayment** - Added idempotency check to prevent race conditions when multiple sources (student browser polling, scheduled job, admin dashboard) call auto-tap-out logic simultaneously. Previously, duplicate "Daily limit reached" tap-out events would be created, causing payroll to count the same session multiple times and resulting in massive overpayment. Now checks if a daily limit tap-out already exists before creating a new one. Includes cleanup script (`cleanup_duplicate_tapouts.py`) to fix existing duplicate records. See `DUPLICATE_TAPOUT_BUG_REPORT.md` for full details.
- **Void redemption creating transactions without join_code** - Fixed `/api/reject-redemption` endpoint creating refund transactions with `join_code=NULL` when voiding redemptions for legacy StudentItem records. Added fallback logic to resolve join_code from TeacherBlock or current session when StudentItem.join_code is NULL, preventing balance fix warnings for teachers. This resolves the "Fix Student Balances" alert appearing after voiding old redemptions.
- **Void transaction CSRF 400 error** - Fixed student detail page void transaction button failing with 400 error. Added missing X-CSRFToken header to fetch request in `voidTransaction()` JavaScript function. Teachers can now successfully void transactions from student detail pages.
- **Rent payment showing wrong period when overdue** - Fixed rent page displaying next month's due date when student is overdue, causing confusion about which period payment covers. Now correctly shows the overdue period's due date with "OVERDUE" badge. Students paying late rent now see they're paying for the current/past period (which grants benefits immediately) instead of the next upcoming period. Fixes issue where students thought they were pre-paying for next month when actually paying for overdue current month.

## [1.8.0] - 2026-02-09

### Added
- **Rent Item Types (Privilege / Per-Use / Hall Pass)** - Extended itemized rent with three distinct item types
  - **Privilege**: Shows as a badge on the roster when rent is paid; optionally listed in store for individual purchase
  - **Per-Use**: Grants free store redemptions when rent is paid (single-use by default, or limited uses when set); always listed in store with "Rent Perk" badge; cannot be deleted from store (only via rent settings)
  - **Hall Pass**: Tops off student hall passes when rent is paid using source-tracking model (rent-granted vs purchased passes tracked separately via `StudentBlock.rent_hall_passes`)
  - **Mid-period edit guardrail**: Once any student has paid rent for the current period, item type, use limits, and hall pass counts are locked; only cosmetic changes (name, description, price) are allowed
  - **Store integration**: Per-use items marked `is_rent_linked` on `StoreItem`, preventing accidental deletion; admin store shows "Rent Perk" badge with disabled delete buttons for linked items
  - **Multi-use item tracking**: Added `uses_remaining` to `StudentItem` for per-use rent items with limited uses
  - **Free uses from rent**: When rent is fully paid, per-use items grant a free `StudentItem` with `uses_remaining` set (default 1); students can redeem these at no cost via the store
  - **Free purchase flow**: Store purchase route checks for active rent-granted uses before charging; shows "Free use (rent perk)" message
  - **Student shop indicators**: Rent-linked items show free uses remaining badge; "Included in your rent!" only shown for privilege-type items
  - **Models**: Added `rent_item_type`, `use_limit`, `hall_pass_count` to `RentItem`; `is_rent_linked` to `StoreItem`; `rent_hall_passes` to `StudentBlock`; `uses_remaining` to `StudentItem`
  - **Migrations**: `c2d9cf951ddc`, `9b0e06f05fcf`, `2765a36d76ff` (all idempotent)
- **Pre-paid Rent Coverage Period Tracking** - Rent payments now explicitly track which period they cover
  - Added `coverage_month` and `coverage_year` columns to `RentPayment` model
  - Paying rent on the due date (e.g., 1/28) now covers the student from 1/29 to the next due date (2/28)
  - All rent privilege checks, purchase blocking, dashboard status, and shop indicators use coverage-based lookups
  - Itemized rent item purchases (`per_period` duration) follow the same coverage period
  - **Migration**: `a1b2c3d4e5f6` adds columns with backfill from existing `period_month`/`period_year`

### Fixed
- **Privilege Badges Showing Non-Privilege Rent Items** - Fixed roster badge display to only show privilege-type rent items, not per-use or hall pass items
  - **Issue**: `_build_rent_privileges_by_block()` and `_get_rent_privileges_for_student()` filtered by `purchase_duration='per_period'` but not `rent_item_type='privilege'`, causing per-use and hall pass items to incorrectly appear as roster badges
  - **Solution**: Added `rent_item_type='privilege'` filter to both functions and the student shop "Included in your rent!" indicator
- **Insurance Class Selector Not Filtering Data** - Fixed multi-tenancy scoping issue where insurance management page showed all classes' data regardless of selected class
  - **Issue**: The "Viewing Insurance For" dropdown on the Insurance Management page did not filter policies, enrollments, or claims. Teachers with multiple class periods saw all insurance data aggregated together instead of scoped to the selected period.
  - **Root Cause**:
    - `InsurancePolicy` queries filtered only by `teacher_id`, not by `InsurancePolicyBlock.block`
    - `StudentInsurance` enrollments were not filtered by `join_code`
    - `InsuranceClaim` queries did not include `join_code` filtering
  - **Solution**:
    - Added `InsurancePolicyBlock` join to filter policies by selected block (or show policies available to all blocks)
    - Added `join_code` lookup from `TeacherBlock` for the selected period
    - Added `join_code` filter to all `StudentInsurance` and `InsuranceClaim` queries
  - **Impact**: Teachers now see only the insurance policies, enrollments, and claims for the currently selected class period
- **Store Purchase Blocked After Rent Paid Across Month Boundary** - Fixed rent-check logic using wrong month/year when verifying rent payments
  - **Issue**: `purchase_item()` used `now.month`/`now.year` instead of `current_due.month`/`current_due.year` when querying `RentPayment`. When a rent due date fell in January but the purchase check ran in February (past the grace period), the query looked for February payments and found none, incorrectly blocking the student.
  - **Solution**: All rent lookups now use `coverage_month`/`coverage_year` derived from the due date, not the wall-clock time
- **Issue Ticket Filing Fails With "An error occurred"** - Fixed Decimal serialization error in issue context snapshots
  - **Issue**: `create_context_snapshot()` stored raw `Decimal` objects (balances, transaction amounts) in a dict destined for a `db.JSON` column. Python's `json` module cannot serialize `Decimal`, causing a `TypeError` caught by the generic exception handler.
  - **Solution**: Convert all `Decimal` values to `float` before storing in the context snapshot
- **Duplicate Store Items When Applying Rent to All Periods** - Fixed `_sync_rent_items_to_store` creating duplicate store items
  - **Issue**: When a teacher applied rent settings to multiple blocks, each block created its own store item copy instead of sharing one item with block visibility
  - **Solution**: Look up existing store items by `teacher_id` + `name` before creating new ones; use `StoreItemBlock` to add block visibility without replacing existing associations

### Changed
- **Redundant Check Removal** - Simplified `_add_period` utility function in `app/routes/api.py` by removing a redundant `isinstance` check.
- **Documentation Update Plan Retired** - Removed `docs/development/DOCUMENTATION_UPDATE_PLAN.md` after v1.7 documentation updates were completed and tracked.

### Security
- **Hardened Grafana Proxy XSS Protection** - Improved content-type filtering to prevent XSS attacks (#897)
  - **Issue**: Original implementation had case-sensitivity issues, missed dangerous MIME types (SVG), and could be bypassed
  - **Solution**:
    - Made Content-Type check case-insensitive per RFC 2045
    - Added `image/svg+xml`, `text/xsl`, and `application/xslt+xml` to blocked MIME types
    - Properly handles Content-Type parameters (e.g., "text/html; charset=utf-8")
  - Prevents reflected XSS attacks via Grafana proxy endpoint
- **Fixed Function Redefinition in Student Routes** - Removed duplicate `_is_safe_url` function definition (#897)
  - **Issue**: Two identical function definitions in `add_class()` route, causing code clarity issues
  - **Solution**: Removed redundant first definition, kept wrapper around shared `is_safe_url` helper
  - Improves code maintainability and prevents potential bugs from function shadowing

## [1.7.1] - 2026-01-22

### Fixed
- **CRITICAL: Decimal.InvalidOperation in Student Dashboard Earnings/Spending Calculations** - Fixed crash when calculating weekly/monthly analytics with NULL transaction amounts
  - **Issue**: Dashboard earnings and spending calculations compared `tx.amount > Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]` when corrupted transactions exist
  - **Affected Code**: Lines 1261-1283 in `app/routes/student.py` (earnings_this_week, earnings_this_month, spending_this_week, spending_this_month)
  - **Additional Fix**: Line 1697 in savings interest calculation also needed NULL check
  - **Solution**: Added null check (`tx.amount is not None`) before all Decimal comparisons in dashboard calculations
  - Completes the NULL handling fix from PR #885 which fixed the Student model properties
- **Duplicate Student Claim Handling** - Added IntegrityError handling for duplicate student account claims
  - **Issue**: Edge cases in deduplication logic could cause IntegrityError when claiming student accounts with duplicate `first_half_hash` values
  - **Solution**: Wrapped `db.session.flush()` in try-except block to catch IntegrityError and link to existing student accounts gracefully
  - Prevents crashes and provides better user experience when duplicate claims occur
- **NameError in Payroll Function** - Fixed import error for `calculate_payroll_breakdown` in admin routes
  - **Issue**: Admin payroll routes referenced `calculate_payroll_breakdown` without proper import
  - **Solution**: Added explicit import of `calculate_payroll_breakdown` from `app.payroll` module
- **Decimal.InvalidOperation in recent_deposits** - Fixed crash when accessing student dashboard with NULL transaction amounts
  - **Issue**: `Student.recent_deposits` property compared `tx.amount <= Decimal('0')` without checking for NULL
  - **Impact**: Student dashboard returned 500 error with `decimal.InvalidOperation: [<class 'decimal.InvalidOperation'>]`
  - **Solution**: Added null check (`tx.amount is None`) before comparison in both `recent_deposits` and `total_earnings` properties
  - Prevents crashes when database has corrupted transaction data with NULL amounts
- **CRITICAL: Float/Decimal Type Error in Savings Interest Calculation** - Fixed `TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'` in `apply_savings_interest()` function
  - **Issue**: The `student.savings_balance` property returns a `float`, but interest calculations were using `Decimal` arithmetic. When the float balance was multiplied by a Decimal rate expression, Python raised a TypeError.
  - **Impact**: Student dashboard returned 500 errors when compound interest was enabled for the class
  - **Root Cause**: The Decimal refactoring (PR #882) updated the interest calculation logic to use Decimal, but the `savings_balance` property still returns float for backward compatibility with other parts of the codebase
  - **Solution**: Wrap `student.savings_balance` with `_quantize_currency()` to convert it to Decimal before performing Decimal arithmetic
  - **Location**: `app/routes/student.py` in `apply_savings_interest()` function, line 1621
- **Decimal JSON Serialization Error** - Fixed `TypeError: Object of type Decimal is not JSON serializable` in student dashboard and API endpoints
  - **Issue**: After Decimal refactoring, Decimal values in templates and JSON responses were not converted to serializable types
  - **Impact**: Student dashboard and `/api/student-status` endpoint returned 500 errors
  - **Solution**: Convert all Decimal values to float before passing to templates or JSON serialization:
    - `app/routes/student.py`: Dashboard variables (checking_balance, savings_balance, forecast_interest, earnings, spending, projected_pay_per_block)
    - `app/routes/student.py`: Student dashboard `period_states_json`
    - `app/routes/api.py`: `/student/start-work` and `/student/stop-work` endpoints (projected_pay)
    - `app/routes/api.py`: `/student/status` endpoint (period_states)
  - Maintains Decimal precision for calculations, converts only at template/serialization boundary
- **CRITICAL: Decimal Precision in All Financial Calculations** - Refactored all financial logic to use Python's `Decimal` type throughout, not just for database storage
  - **Issue**: PR #880 was a hotfix that converted `Decimal` to `float` to resolve TypeErrors, but introduced floating-point precision errors
  - **Impact**: Small residual balances accumulate over time, incorrect interest calculations, potential overdraft fee issues
  - **Solution**: Systematic refactoring of all financial calculations to use Decimal arithmetic
  - **Changes**:
    - Updated `Student.get_checking_balance()` and `Student.get_savings_balance()` to return Decimal instead of float
    - Updated `calculate_scoped_balances()` to return Decimal tuples
    - Refactored all interest calculations in `student.py` to use Decimal arithmetic with proper exponentiation
    - Updated `apply_savings_interest()` to use Decimal throughout for compound and simple interest
    - Refactored transfer route to convert form inputs to Decimal before validation
    - Updated rent payment processing to use Decimal for payment amounts
    - Updated `payroll.py` `get_pay_rate_for_block()` to return Decimal per-second rate
    - Refactored all `admin.py` financial form handling (rent, payroll, store items, rewards, fines) to use `_quantize_currency()`
    - Updated `api.py` demo session balance inputs to use Decimal
    - Updated `system_admin.py` reward amounts to use Decimal
    - Refactored `utils/economy_balance.py` CWI calculations and balance validators to use Decimal
    - Updated `_normalize_to_weekly()` helper to work with Decimal inputs/outputs
  - **Backward Compatibility**: Decimal objects convert to float only for JSON serialization and template rendering
  - **Testing**: All existing decimal precision tests pass; financial calculations now mathematically exact
- **Decimal.InvalidOperation in get_total_earnings** - Fixed crash when calculating student earnings with NULL transaction amounts
  - Added null check (`tx.amount is not None`) before comparison in `get_total_earnings()` method
  - Prevents `decimal.InvalidOperation` error on `/admin/students` page when database has corrupted transaction data
  - Handles edge case where historical data migrations or database inconsistencies result in NULL amounts
  - Fix applied to all three code paths (join_code, teacher_id, and no parameters)
- **CRITICAL: Floating-Point Rounding Errors in Financial Calculations** - Converted all financial amounts from Float to Decimal for exact precision
  - **Bug 1**: Transfers that zeroed out checking accounts incorrectly triggered $35 overdraft fees due to -0.00 balance representation
  - **Bug 2**: Partial rent payments left unpayable tiny balances (e.g., $0.0000001) due to float precision errors
  - **Fix**: Changed `Transaction.amount` from `Float` to `Numeric(12, 2)` in database for exact decimal representation
  - **Fix**: Updated all financial models (RentSettings, BankingSettings, PayrollSettings, StoreItem, InsurancePolicy, etc.) to use Numeric
  - **Fix**: Updated balance calculation methods to use Python's `Decimal` type instead of `float`
  - **Fix**: Added near-zero balance normalization (|balance| < $0.01 → $0.00) to prevent false overdraft fees
  - **Migration**: Created migration to convert all Float columns to Numeric(12, 2) without data loss
  - **Testing**: Added comprehensive test suite for edge cases (zero transfers, partial payments, near-zero balances)
- **Student Creation Without Deprecated teacher_id** - Removed deprecated `teacher_id` assignment when creating new students to prevent `TypeError: 'teacher_id' is an invalid keyword argument for Student`.
- **Scheduled Auto Tap-Out Transactions** - Avoided committing inside the scheduled auto tap-out loop to prevent closed-transaction errors during background checks.
- **Student Claim DOB Field** - Aligned the claim-account form field name with the templates to prevent 500 errors on /student/claim-account.
- **Student Transfer Banking Settings Import** - Removed a local import shadowing `BankingSettings` to prevent UnboundLocalError on /student/transfer.
- **Rent Calculation Accuracy** - Improved rent amount calculations for monthly display (#839)
  - Fixed daily rent calculation to use actual days in month (via `monthrange`) instead of approximating 30 days
  - Added support for 'custom' frequency type in rent calculation logic
  - Fixed timezone inconsistency by using timezone-aware `datetime.now(timezone.utc)` consistently
  - Added null checks for `grace_period_days` and `due_day_of_month` fields to prevent TypeError
  - Refactored duplicated late payment check logic into single code path
  - Optimized payments query using subquery instead of list comprehension for better performance
- **Rent Statistics Display** - Fixed incorrect student counts in rent overview cards (#839)
  - "Paid This Month" now correctly shows count of students who paid (not payment count)
  - "Unpaid This Month" now correctly shows count of students with outstanding balances
  - Both statistics use accurate `unpaid_students` calculation instead of payment count
- **Rent Period Display** - Fixed misleading "Period" column in unpaid students list (#839)
  - Now shows billing period (e.g., "January 2026") instead of class block/period
- **Hall Pass Queue Scoping** - Removed deprecated `students.teacher_id` filtering to prevent hall pass queue errors.

### Changed
- **Rent Calculation Helper** - Extracted rent amount calculation into reusable helper function (#839)
  - Created `_calculate_base_rent_amount()` helper to avoid code duplication
  - Used in both payroll warning calculation and unpaid students calculation
  - Follows DRY principle for better maintainability
- **CSP Headers for Public Hall Pass Pages** - Modified Content Security Policy to allow embedding for read-only hall pass display pages
  - `/hall-pass/verification` and `/hall-pass/queue` can now be embedded in external sites (e.g., Schoology, Canvas)
  - These pages are public, read-only displays with no state-changing actions
  - `/hall-pass/terminal` remains protected (not embeddable) as it performs state-changing check-in/check-out actions
  - Removed `X-Frame-Options` header for embeddable pages and added `frame-ancestors *` to CSP
  - All other pages remain protected with `X-Frame-Options: SAMEORIGIN` and `frame-ancestors 'self'`

## [1.7.0] - 2026-01-09

### Added
- **ToS Acknowledgment Modal** - Implemented a modal during admin sign-up that requires explicit acknowledgment of Terms of Service and Privacy Policy.
  - Modal blocks the sign-up process until the "I have read and agree" checkbox is checked.
  - `tos_accepted` status and timestamp are recorded in the `Admin` table.
  - Ensures compliance with legal requirements for teacher account creation.

### Fixed
- **Analytics Events Value Display** - Show zero-value economy changes in the analytics events timeline by checking for `None` instead of falsy values.
- **EasyMDE Form Submission** - Fixed issue where forms with EasyMDE markdown editors could not be submitted due to hidden required fields
  - EasyMDE markdown editor hides the underlying textarea, causing browser validation to fail on required fields
  - Removed HTML `required` attribute from hidden textareas after editor initialization
  - Server-side validation via `DataRequired()` still enforces required fields
  - Applied fix to insurance claim form (`student_file_claim.html`) and issue submission form (`student_submit_issue.html`)
  - Resolves console error: "An invalid form control with name='[field]' is not focusable"

### Added
- **Analytics Dashboard (Phase 1-3)** - System health observability dashboard per analytics specification
  - Three new database models: `AnalyticsSnapshot`, `AnalyticsEvent`, `AnalyticsAlert`
  - Analytics computation engine with CWI-relative metrics (no absolute balances/rankings)
  - System health metrics: participation rate, money velocity, CWI deviation bands, budget survival pass rate
  - Trend analysis: tracks improving/stable/worsening patterns across periods
  - Visual alerts with explanations (what changed, why it matters, suggested actions)
  - Event annotation system for rent changes, wage changes, inflation events
  - Metrics precomputed and cached by time window for 5-second readability
  - Weekly and monthly time window views
  - All metrics properly scoped by `join_code` for multi-tenancy compliance
  - Dashboard route at `/admin/analytics`
  - API endpoints for snapshot data and alerts
  - Comprehensive test coverage for analytics engine
  - Database migration: `a7b8c9d0e1f2_add_analytics_models`
  - Per spec: no student names in default views, no leaderboards, no comparative rankings
  - Design principle: "Something is drifting — and I know what lever to pull"
- **Mobile Navigation Enhancement** - Full navigation menu now accessible on mobile devices and PWA
  - Added floating hamburger menu button that appears on mobile (<768px)
  - Sidebar slides in from left with smooth animation and backdrop overlay
  - Help buttons now visible as icon-only on mobile screens
  - Contextual help links show icon on mobile, hiding text to save space
  - Same template works for desktop, mobile, and PWA - no separate mobile templates needed
  - Sidebar automatically closes when clicking navigation links or backdrop
  - Resolves PWA limitation where full navigation menu was previously inaccessible
- **Rent Itemization Feature** - Teachers can now specify what rent pays for and offer items as store alternatives (MVP)
  - New `RentItem` model to track itemized rent components (e.g., Desk, Chair, Locker)
  - Teachers can add/remove/reorder rent items in Rent Settings page
  - Optional store integration: mark items as "Available in Store" with custom pricing
  - Automated sync: items marked for store availability automatically create/update StoreItem records
  - StoreItem created with `limit_per_student=1` to enforce single-purchase behavior
  - Store items inherit block visibility from rent settings
  - Student rent view displays itemized breakdown showing what rent includes
  - Students see store price comparison for items available separately
  - Pro tip message encourages rent payment by showing total value comparison
  - Manual pricing (teacher sets store price manually - automatic pricing calculator coming in future release)
  - Database migration: `6feaa660d6c3_add_rent_item_table`
- **Enhanced Purchase Restrictions** - "Prevent Purchase When Late" toggle now has dynamic behavior based on itemization
  - When rent itemization is disabled: blocks ALL store purchases when student is late on rent (original behavior)
  - When rent itemization is enabled: students late on rent can ONLY purchase items covered by rent (at à la carte prices), all other store items blocked
  - Creates strong incentive structure: pay rent to get everything, or buy individual rent items at higher prices while missing out on other store items
  - UI dynamically updates toggle label and description based on itemization status
  - JavaScript updates label when items are added/removed dynamically
  - Implemented in `/api/purchase-item` endpoint with proper rent late detection and item validation
- **Purchase Duration Options for Rent Items** - Teachers can now choose how long individually-purchased rent items last
  - New `purchase_duration` field on RentItem model: 'per_use' or 'per_period'
  - **Per Use**: Student must buy each time they want to use it (unlimited purchases allowed)
  - **Per Rent Period**: Student buys once and can use until next rent is due (limit 1, expires when rent comes due)
  - Radio button selector in rent itemization UI with clear explanations
  - Store items automatically configured with appropriate purchase limits based on duration type
  - Purchase API calculates expiration dates for "per_period" items based on rent frequency settings
  - Automated expiration when next rent payment is due
  - Database migration: `h7i8j9k0l1m2_add_purchase_duration_to_rent_items`
- **Rent Privilege Badges** - Visual indicators on student detail page showing active rent privileges
  - Displays all "per_period" rent items that students currently have access to
  - **Green badges**: Privileges covered by paid rent (automatic for rent-paying students)
  - **Blue badges**: Privileges purchased individually (shows "(Purchased)" label)
  - Badges only show for non-expired privileges
  - Rent-paying students automatically receive all per-period privilege badges
  - Teachers can quickly see which students have which privileges at a glance
  - Hover over badges to see item descriptions

## [1.6.0] - 2026-01-01

### Added
- **Documentation Organization** - Improved repository structure and documentation consistency
  - Consolidated duplicate script files into scripts/ directory
  - Standardized file paths and references across documentation
  - Removed obsolete root-level duplicates
  - Improved navigation and file organization

### Fixed
- **Getting Started Widget** - Fixed onboarding widget state persistence issues
  - Widget state now persists to database instead of browser localStorage
  - Widget dismissal and task completion now sync across logins and devices
  - Skipped tasks are now properly marked as complete in the widget
  - Added `widget_tasks_completed`, `widget_dismissed`, and `widget_dismissed_at` fields to `TeacherOnboarding` model
  - Updated `/admin/onboarding/status` endpoint to check both actual setup AND manually skipped tasks
  - Added `/admin/onboarding/dismiss-widget` endpoint to persist widget dismissal
  - Widget state is per-teacher (not per-block) for consistent onboarding experience
- **Multi-Tenancy Violation** - Fixed critical bug where `HallPassSettings` records were created without `teacher_id`, violating NOT NULL constraint and breaking multi-tenancy isolation
  - Fixed `/api/hall-pass/settings` endpoint to scope settings by `teacher_id` from session
  - Fixed hall pass creation in `/tap` endpoint to retrieve `teacher_id` from `join_code` via `TeacherBlock` lookup
  - All `HallPassSettings` queries now properly scoped by `teacher_id` and `block`
- **Content Security Policy** - Restored `'unsafe-eval'` directive to `script-src` CSP policy as it is required by passwordless.dev library's minified build (uses `new Function()` internally)
- **Passkey Authentication** - Fixed environment variables not loading by specifying explicit path to `.env` file in `load_dotenv()` call - ensures environment is loaded regardless of gunicorn working directory
- **Passkey Authentication** - Fixed token destructuring in `signinWithDiscoverable()` to properly handle error responses from passwordless.dev SDK
- **Deployment** - Added verification steps to confirm environment variables are properly written to `.env` and loaded by systemd service
- **File Organization** - Fixed inconsistent paths for student upload template and script references

### Changed
- Consolidated duplicate scripts into scripts/ directory (seed_dummy_students.py, create_admin.py, etc.)
- Removed duplicate nginx configuration file from root
- Updated documentation to reference correct file paths

### Documentation
- Improved repository organization and file structure
- Updated path references throughout documentation
- Removed obsolete duplicate files

## [1.5.0] - 2025-12-29

### Added
- **Attendance Issue Reporting** - Students can now report issues with specific attendance/tap events (clock in/out records) directly from the Work & Pay page
  - New route `/help-support/tap-event/<id>/report` for reporting attendance record issues
  - Report buttons added to all tap event tables in Work & Pay > Attendance Record tab
  - Uses same issue resolution workflow as transaction reporting
  - Students can report up to 20 most recent tap events per block
- **Issue Resolution & Escalation System** - Structured, teacher-mediated issue handling system
  - **Student Features**:
    - New Help & Support interface with 3 tabs: Knowledge Base, Report an Issue, My Issues
    - Submit general issues (clock-in problems, features not working, balance incorrect, etc.)
    - Report transaction-specific issues directly from transaction history
    - Help icons next to each transaction in Recent Activity for quick issue reporting
    - Character-limited submissions (1000 chars) to encourage concise reporting
    - Automatic context capture: balances, transaction history, system metadata
    - Status badges (Submitted, Teacher Review, Resolved, Elevated, Developer Review) - no messaging
    - View all submitted issues with status tracking
  - **Teacher Features**:
    - Issue review queue with pending/resolved/escalated tabs
    - Detailed issue view showing student explanation, context, and transaction details
    - Resolution actions:
      - Reverse/void transactions directly from issue interface
      - Manual adjustment (teacher handles offline)
      - Deny issue with required explanation
    - Escalate to developer with:
      - Required escalation reason
      - Diagnostic notes for investigation
      - Optional class name sharing checkbox (default: opaque reference only)
      - **"Student may receive reward"** checkbox for legitimate bug reports
    - Complete status history and resolution action audit trail
  - **Technical Implementation**:
    - 4 new database models: `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
    - Default categories: 6 transaction types + 6 general issue types
    - Opaque student references for sysadmin privacy (non-reversible hashes)
    - Multi-tenancy scoping by `join_code` for proper class isolation
    - Context snapshots preserve ledger state at time of submission
    - Complete audit trail with timestamps and attribution
    - Immutable student submissions after creation
  - **Design Principles**:
    - No direct student-to-sysadmin communication
    - Teachers are first-line decision makers
    - Evidence-based issue tracking (tied to concrete transactions/records)
    - Data minimization for sysadmin review
    - Status badges only (non-communicative design)
  - Routes:
    - Student: `/student/help-support`, `/student/help-support/submit-issue`, `/student/help-support/transaction/<id>/report`
    - Teacher: `/admin/issues`, `/admin/issues/<id>`, `/admin/issues/<id>/resolve`, `/admin/issues/<id>/escalate`

### Changed
- Improved `flask create-sysadmin` command to display TOTP secret and QR code during account creation
  - Shows scannable QR code in terminal for easy authenticator app setup
  - Displays plaintext secret for manual entry backup
  - Auto-clears terminal after user confirmation for security
  - Secret remains encrypted in database after initial display
- Issue resolution UI refresh and workflow refinements
- Issue management and reporting refactor
- Standardized UTC timestamp formatting

### Fixed
- **Store Item Creation** - Fixed critical bug where tier, collective_goal_type, collective_goal_target, and redemption_prompt fields were not being saved when creating new store items
  - Added `tier` field assignment to store creation route (app/routes/admin.py:3047)
  - Added `collective_goal_type` and `collective_goal_target` field assignments for collective goal items (app/routes/admin.py:3063-3064)
  - Added `redemption_prompt` field assignment for delayed-use items (app/routes/admin.py:3066)
  - These fields were already present in the form (forms.py) and model (models.py), but were not being passed to the StoreItem constructor
  - Edit functionality uses `populate_obj` rather than manually assigning these fields, so this bug specifically affected the creation route
- **Transaction Issue Reporting** - Added report buttons to all transaction tables in Banking/Finances page (Checking and Savings tabs), allowing students to report issues on any visible transaction (up to 50 most recent), not just the 5 shown on dashboard
- **Issue Resolution Display** - Fixed `developer_resolved` status showing as "Escalated" instead of "Resolved by Developer" in teacher view
- **Issue Context Snapshot** - Fixed incorrect balance calculation in context_snapshot by using Student model's `get_checking_balance()` and `get_savings_balance()` methods instead of non-existent `get_balances()` function
- **Passkey Authentication** - Fixed missing username parameter in passkey authentication start request causing 500 error
- **Passkey Registration** - Fixed credential ID extraction from passwordless.dev SDK response by using correct destructuring pattern `{ token, error }`
- **Content Security Policy** - Added `https://static.cloudflareinsights.com` to `connect-src` directive to allow Cloudflare analytics
- **Content Security Policy** - Added `worker-src 'self' blob:` directive to allow Web Workers used by passwordless.dev library
- Fixed `time.tzset()` Windows compatibility issue in wsgi.py - now only calls tzset() on Unix-like systems
- Fixed admin signup crash when using SQLite - handles datetime fields stored as strings
- System Admin announcements form `ValueError` by adding a custom `coerce` for the `target_teacher` field

### Security
- Enhanced privacy protection in issue resolution system through opaque student references
- Teacher-controlled data disclosure to sysadmins (optional class name sharing)
- **Content Security Policy** - Removed unnecessary `'unsafe-eval'` directive from `script-src` to strengthen XSS protection (passwordless.dev library does not require dynamic code execution)

### Documentation
- Reorganized documentation structure for improved navigation
- **Developer Documentation Updates** - Updated development tracking documentation to reflect current status
  - Updated `DEVELOPMENT.md` to reflect v1.6.0 status (was showing 1.4.0)
  - Added v1.5.0 and v1.6.0 release summaries to Recent Releases section
  - Updated target version from 1.5.0 to 1.7.0
  - Updated `IMPLEMENTATION_PROGRESS.md` to mark sysadmin routes and templates as completed (were incorrectly marked as pending)
  - Added detailed test coverage priorities and recommendations
  - Updated Next Steps with current implementation status (85% complete)
  - Added specific guidance for remaining work (tests, user docs, technical docs)
- **Comprehensive Documentation Accuracy Fixes** - Corrected 10 inaccuracies found in user-facing documentation
  - **Store Items (docs/user-guides/features/store/creating-items.md)**:
    - Fixed tier system documentation to reflect actual implementation (Basic/Standard/Premium/Luxury based on % of CWI, not Tier 1/2/3 with dollar amounts)
    - Corrected default state - items are created as active by default, not inactive
    - Removed non-existent image upload feature documentation
    - Removed non-existent daily purchase limit documentation
    - Updated terminology to match code (Immediate Use/Delayed Use instead of Virtual/Physical)
    - Added missing "Collective Goal" item type to documentation with full explanation
    - Corrected purchase limits documentation to reflect actual behavior (concurrent ownership, not daily limits)
    - Updated scenario examples to use correct field names and remove daily limits
    - Removed confusing "if available" language for collective goals (feature is fully available)
    - Removed misleading "Use images" tip from Tips for Success section (feature doesn't exist)
    - Fixed contradictory troubleshooting text about daily limits (clarified to use inventory and per-student limits)
  - **Payroll (docs/user-guides/features/payroll/running-payroll.md)**:
    - Removed non-existent automatic payroll feature documentation (entire section)
    - Added guidance for manual payroll scheduling and consistency
    - Clarified that break time IS paid (system does not exclude breaks from hours worked)
    - Added Q&A explaining how to handle unpaid breaks if desired
    - Updated all automatic payroll references to reflect manual-only operation
  - **Banking (docs/user-guides/features/banking/transferring-money.md)**:
    - Removed non-existent transfer limits documentation (daily limits, min/max transfer amounts)
    - Simplified to only document actual rules (no negative balances)

### Dependencies
- Bump `requests` from 2.32.4 to 2.32.5
- Bump `markdown` from 3.7 to 3.10
- Bump `webfactory/ssh-agent` from 0.9.0 to 0.9.1

## [1.4.0] - 2025-12-27

### Added
- **Announcement System** - Teachers can create and manage announcements for their class periods
  - Display announcements on student dashboards with dismiss capability
  - Filter announcements by class period
  - Toggle announcement visibility (active/inactive)
  - Create, edit, and delete announcements with rich formatting
  - System admins can create global announcements visible across all classes
  - Announcements link added to admin navigation under Classroom section
- **UI/UX Improvements** - Comprehensive redesign of dashboard and navigation interfaces
  - **Personalized Greetings**:
    - Teacher dashboard displays centered "Hi, [Display Name]" greeting with info icon tooltip linking to settings
    - Student dashboard shows dynamic time-based greeting with first name
    - Mid-day greetings randomize between friendly options: "Howdy", "Good day to you", "Good to see you again", "Great timing", "Let us get started"
    - Morning (5am-12pm): "Good morning"
    - Afternoon (12pm-5pm): Random friendly greeting
    - Evening (5pm-5am): "Good evening"
  - **Enhanced Student Dashboard**:
    - Removed redundant left navigation sidebar for cleaner layout
    - Added side-by-side account balance cards for Checking and Savings accounts
    - Light gray card backgrounds for better visibility
    - Savings account displays projected monthly interest when balance > 0
    - Encouragement message when savings balance is $0 to promote saving habits
    - Fully responsive design (side-by-side on desktop, stacked on mobile)
  - **Accordion-Style Admin Navigation**:
    - Reorganized sidebar navigation into collapsible accordion categories
    - Categories: Classroom, Economy, Bills, Settings
    - Bootstrap accordion ensures only one section open at a time for cleaner interface
    - Consolidated Settings section: Personalization, Passkey, Features, Help & Support
    - Removed non-functional "Mobile Site" link from navigation
    - Custom CSS styling for dark sidebar theme with smooth transitions
  - **Improved Sign Out Button**: Enhanced contrast with red filled button and white text
  - **Streamlined Authentication Flow**:
    - Login forms present two authentication method buttons upfront
    - "Use my authenticator" button reveals TOTP field with Back button
    - "Use my passkey" button triggers WebAuthn flow with automatic fallback to TOTP on failure
    - Applied to both admin and system admin login pages
    - Cleaner, more intuitive authentication experience with proper error handling

### Changed
- **Dependency Updates** - Updated key dependencies for security and stability
  - Updated `click` from 8.1.8 to 8.3.1
  - Updated `beautifulsoup4` from 4.13.4 to 4.14.3
  - Updated `requests` from 2.32.3 to 2.32.4

### Security
- **CodeQL Security Alerts Remediation** - Addressed 62 security alerts identified by CodeQL scanning (#737)
  - **Clear-text Logging of Sensitive Information**:
    - Remove TOTP secret printing from `create_admin.py`, `wsgi.py`, and seed scripts
    - TOTP secrets now encrypted in database with secure access only
    - Prevents TOTP secrets from appearing in logs, console output, or command history
  - **DOM XSS Vulnerabilities**:
    - Fixed `innerHTML` usage in `templates/student_transfer.html`
    - Fixed `innerHTML` usage in `static/js/attendance.js`
    - Replaced with safe DOM manipulation using `createElement` and `textContent`
    - Prevents XSS attacks via user-controlled data
  - **GitHub Actions Workflow Permissions**:
    - Added explicit permissions to `toggle-maintenance.yml`, `check-migrations.yml`, and `deploy.yml`
    - Follows principle of least privilege for workflow security
    - Reduces workflow attack surface
  - **Documentation**: Added `docs/archive/SECURITY_FIXES_SUMMARY.md` with complete analysis of all 62 alerts
  - **Summary**: Fixed 23+ real security issues, suppressed 2 false positives, reviewed 37 false positives (already mitigated)
- **Enhanced Open Redirect Protection** - Improved URL validation in student class enrollment redirects
  - Upgraded `_is_safe_url()` function to use same-origin validation
  - Now uses `urljoin()` to resolve relative URLs against application's base URL
  - Validates that redirect targets match the application's scheme and domain
  - Prevents protocol-relative URLs and external redirects
  - Added explicit security annotations (`# nosec`) with justification at all redirect points
  - Addresses all 9 CodeQL security scanner findings for URL redirection vulnerabilities
  - Affects student add-class flow redirect handling (`app/routes/student.py:710-877`)

### Fixed
- **Teacher Invite Code Validation** - Fixed critical bugs preventing teacher signup with invite codes (#738)
  - **Whitespace Handling**: Strip whitespace from invite codes during creation and validation
  - **Timezone Comparison Error**: Fixed TypeError when comparing invite code expiration dates (timezone-aware vs timezone-naive datetimes)
  - **TOTP Form Validation**: Properly handle TOTP confirmation form submission separate from initial signup form
  - **Form Field Population**: Use AdminTOTPConfirmForm for TOTP submissions instead of AdminSignupForm
  - **Date String Handling**: Pass date string instead of integer for dob_sum field in TOTP confirmation
  - Added comprehensive debug logging for invite code creation and validation
  - Added cleanup script (`cleanup_invite_codes.py`) for existing codes with whitespace
  - Ensures consistency between invite code creation and validation across system admin and CLI tools
- **TOTP Setup UI** - Updated TOTP setup page to match new brand theme
  - Replaced hardcoded colors with CSS variables (--primary, --secondary, etc.)
  - Updated gradient and logo to match refreshed brand
  - Added pattern background to match signup page design
  - Improved button hover states for consistency
- **Onboarding Templates** - Updated color scheme and text for better consistency with new brand theme
- **Admin Dashboard**: Removed duplicate greeting that was appearing in both page header and content section
- **Student Dashboard**: Improved account balance cards with clearer styling using light backgrounds instead of semi-transparent overlays for better readability
- **Mobile Responsiveness**: Enhanced responsive behavior with proper Bootstrap column classes (col-12 col-md-6)
- **Grafana Access Issue** - Fixed "connection refused" error when accessing Grafana from system admin dashboard
  - **Root Cause**: Nginx `proxy_pass` had trailing slash that stripped URL path, causing infinite redirects
  - **Dual-Layer Solution** for maximum reliability:
    - **Flask Proxy (Fallback)**: Added `/sysadmin/grafana` route that proxies to Grafana service
      - Works immediately without Nginx configuration changes
      - Maintains system admin authentication via `@system_admin_required`
      - Configurable via `GRAFANA_URL` environment variable (defaults to `http://localhost:3000`)
      - Rate-limit exempt for smooth dashboard operation
      - Graceful error handling with user-friendly messages
      - Added `requests==2.32.3` dependency
    - **Nginx Fix (Production)**: Corrected configuration provided in `nginx-grafana-fix.conf`
      - Remove trailing slash from `proxy_pass http://127.0.0.1:3000/` → `proxy_pass http://127.0.0.1:3000`
      - Nginx intercepts requests before Flask (faster performance)
      - Auto-fallback to Flask proxy if Nginx not configured
  - See `GRAFANA_FIX_GUIDE.md` for detailed implementation guide

## [1.3.0] - 2025-12-25

### Added
- **Passwordless Authentication for Teachers** - Implemented WebAuthn/FIDO2 passkey authentication for teacher admins
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/admin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Database model `AdminCredential` for storing passkey metadata
  - TOTP authentication remains available as backup option
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Passkey settings link added to teacher navigation sidebar
- **Passwordless Authentication for System Admins** - Implemented WebAuthn/FIDO2 passkey authentication using passwordless.dev
  - Supports hardware security keys (YubiKey, Google Titan Key, etc.)
  - Supports platform authenticators (Touch ID, Face ID, Windows Hello)
  - Supports synced passkeys across devices
  - Phishing-resistant authentication (domain-bound credentials)
  - New `/sysadmin/passkey/settings` page for passkey management
  - Backend routes for passkey registration and authentication
  - Frontend integration with passwordless.dev JavaScript SDK
  - Database model `SystemAdminCredential` for storing passkey metadata
  - TOTP authentication remains available alongside passkeys
  - Self-hosted ready: Infrastructure supports future migration to py-webauthn library
  - Requires environment variables: `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`
  - Full CSRF protection and rate limiting on all passkey endpoints
  - Tracks credential usage timestamps for security auditing
  - Uses official Bitwarden Passwordless SDK (`passwordless==2.0.0`) for type-safe API interactions
- **Security Remediation Tools and Documentation** - Complete implementation guides and fixed workflow files
  - Step-by-step remediation guide: `docs/security/SECURITY_REMEDIATION_GUIDE.md`
  - Fixed workflow files with SSH host key verification: `.github/workflows/*.FIXED`
  - Automated SSH security setup script: `scripts/setup-ssh-security.sh`
  - Includes fixes for: SSH MITM vulnerability, secrets management hardening, dependency updates
  - Ready-to-use workflow files with improved security posture

### Security
- **Encrypted TOTP Secrets at Rest** - TOTP 2FA secrets now encrypted in database using Fernet (AES-128-CBC)
  - Added `encrypt_totp()` and `decrypt_totp()` helper functions in `app/utils/encryption.py`
  - All new admin/system admin accounts store encrypted TOTP secrets (base64-encoded)
  - Backward compatible: `decrypt_totp()` handles both encrypted and legacy plaintext secrets transparently
  - **MIGRATION REQUIRED**: Column length expanded from VARCHAR(32) to VARCHAR(200) - See `docs/archive/MIGRATION_TOTP_ENCRYPTION.md`
  - Defense in depth: Database compromise alone no longer sufficient to generate valid 2FA codes
  - **Note:** Still requires `ENCRYPTION_KEY` security - future migration to AWS Secrets Manager/Vault recommended
  - Files changed: `app/utils/encryption.py`, `app/models.py`, `app/routes/admin.py`, `app/routes/system_admin.py`, `wsgi.py`, `create_admin.py`
- **Removed Sensitive Information from Application Logs** - Eliminated logging of usernames, hashes, and PII
  - Removed username logging from student login, admin login, admin signup, and admin recovery flows
  - Removed partial hash logging from student authentication
  - Removed student name and DOB sum logging from bulk upload process
  - Impact: Prevents accidental exposure of PII in development logs, log files, or screenshots
  - Note: Production deployments should configure `LOG_LEVEL=WARNING` or higher to minimize log output
- **CRITICAL: Fixed PromptPwnd AI Prompt Injection Vulnerability** - Disabled vulnerable `summary.yml` GitHub Actions workflow
  - Workflow used AI inference (`actions/ai-inference@v1`) with untrusted user input from issue titles/bodies
  - Attack vector: Any user could create an issue with malicious prompt injection to leak `GITHUB_TOKEN` or manipulate workflows
  - Remediation: Disabled workflow by renaming to `summary.yml.DISABLED`
  - Impact: No exploitation detected - vulnerability fixed proactively
  - Documentation: See `docs/security/PROMPTPWND_REMEDIATION.md` for full details
  - Reference: [Aikido Security PromptPwnd Disclosure](https://www.aikido.dev/blog/promptpwnd-ai-prompt-injection-in-github-actions) (December 2025)
- **Comprehensive Attack Surface Security Audit Completed** - Full security review of codebase, CI/CD, and infrastructure
  - Audited: GitHub Actions workflows, authentication, authorization, encryption, multi-tenancy, dependencies, and API security
  - Findings: 16 total findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
  - Critical issues: AI prompt injection (fixed), SSH host key verification disabled (open)
  - Strengths: Excellent CSRF protection, SQL injection prevention, XSS mitigation, PII encryption, multi-tenancy isolation
  - Recommendations: Enable SSH host key verification, update cryptography package, improve secrets management
  - Documentation: See `docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md` for complete report

## [1.2.1] - 2025-12-21

### Added
- **Comprehensive Legacy Account Migration Script** - Complete migration tool for transitioning all legacy accounts to new multi-tenancy system
  - Migrates students with `teacher_id` to claim-based enrollment system
  - Creates missing `StudentTeacher` associations and `TeacherBlock` entries
  - Backfills `join_code` for all TeacherBlock entries
  - Backfills `join_code` for transactions, tap events, and related tables with proper multi-tenancy isolation
  - **FIXED:** Transaction backfill now matches on BOTH `student_id` AND `teacher_id` to ensure correct period assignment for students in multiple periods with same teacher
  - **FIXED:** Block names normalized to uppercase for consistency across database
  - **OPTIMIZED:** Phase 5 backfill uses CTE with `DISTINCT ON` instead of correlated subqueries for significantly better performance on large datasets
  - Includes dry-run mode for safe preview before applying changes
  - Provides comprehensive verification and error reporting
  - Located at: `scripts/comprehensive_legacy_migration.py`
- **Comprehensive Test Suite for Legacy Migration** - Full test coverage for migration script
  - Tests all 5 migration phases including Phase 5 (related tables backfill)
  - Tests critical multi-period student scenarios
  - Tests idempotency and error handling
  - Tests block casing normalization
  - Tests rollback on errors
  - Tests CTE performance optimization for Phase 5
  - Tests tables with and without period columns
  - Located at: `tests/test_comprehensive_legacy_migration.py`
- **Legacy Account Migration Documentation** - Complete guide for migration process
  - Historical context and migration strategy
  - Step-by-step deployment instructions
  - Troubleshooting common issues
  - Post-migration verification procedures
  - Roadmap for deprecating `teacher_id` column
  - Located at: `docs/operations/LEGACY_ACCOUNT_MIGRATION.md`
- **Join Code Schema Audit Tool** - `scripts/inspect_join_code_columns.py` lists which tables have or are missing `join_code` to support multi-tenancy audits
- **StudentBlock Join Code Migration** - Added idempotent migration (`a1b2c3d4e5f8`) to create `join_code` column and index on `student_blocks`, with safeguards for partially applied schemas

### Changed
- Preparing for final deprecation of `teacher_id`-based linkage system
- All legacy data now ready for migration to `join_code`-based multi-tenancy
- Hardened migration best practices documentation for avoiding duplicate-column errors in `student_blocks` hotfix scenarios
- Refreshed maintenance page copy and styling for clearer outage messaging

### Fixed
- Closed multi-tenancy gaps by adding `join_code` propagation to overdraft fees, bonus/bulk payroll postings, insurance reimbursements, manual payments, and bug-report rewards
- Improved bonus join_code lookup performance to reduce N+1 queries during mass payouts

## [1.2.0] - 2025-12-18

### Added
- **Progressive Web App (PWA) Support** - Full PWA implementation for improved mobile experience
  - Web app manifest with app metadata and icon configuration
  - Service worker with intelligent caching strategies (cache-first for static assets, network-first for CDN resources)
  - Offline fallback page with user-friendly offline experience
  - PWA installation capability on mobile devices (Add to Home Screen)
  - Multi-tenancy-safe caching that excludes authenticated routes
  - Automatic cache cleanup and version management
- **Mobile Experience Enhancements** - Dedicated mobile templates for student portal with responsive navigation and improved touch targets
- **Accessibility Improvements** - Enhancements following WCAG 2.1 AA guidelines
  - Added ARIA labels to mobile navigation and interactive elements
  - Improved keyboard navigation support
  - Enhanced screen reader compatibility
  - Better color contrast ratios
- **UI Documentation** - Added `docs/PWA_ICON_REQUIREMENTS.md` and `TEMPLATE_REDESIGN_RECOMMENDATIONS.md`
  - PWA icon asset generation instructions
  - UI redesign patterns and guidelines
  - Best practices for accordion/collapsible patterns
  - Color scheme guidelines for consistent visual hierarchy

### Changed
- **Attendance Terminology** - Renamed "Tap In/Out" to "Start Work/Break Done" for clarity
  - Updated user-facing text throughout student portal
  - Updated frontend API actions and documentation
  - Maintained backward compatibility in database actions
- **Admin UI Redesigns** - Modernized admin templates with collapsible accordion sections
  - **Insurance Policy Edit Page** - Eliminated overflow issues with progressive disclosure layout
  - **Store Item Edit Page** - Reduced scrolling with accordion sections for Bundle, Bulk Discount, and Advanced settings
  - **Rent Settings Page** - Better organization with collapsible sections
  - **Feature Settings** - Simplified to single-column, collapsible cards
  - Added visual "Active" badges to accordion headers indicating when sections have configured settings
- **Mobile Dashboard** - Simplified single-column layout with attendance card and tap buttons
- **Mobile Store** - Improved item list layout with larger purchase buttons
- **Theme Consistency** - Aligned mobile templates with main application theme colors

### Fixed
- **Critical: Multi-Tenancy Payroll Bug** - Fixed payroll calculations leaking data across class periods (#664)
  - Ensured all payroll queries properly scoped by join_code
  - Added multi-tenancy tests for payroll system
- **Payroll JSON Error** - Fixed "Run Payroll Now" button returning HTML instead of JSON (#668)
  - Resolved "Unexpected token '<!DOCTYPE'" error
  - Properly returns JSON response for AJAX requests
- **Timezone Handling** - Fixed timezone comparison error in payroll calculation (#666)
  - Corrected UTC normalization for payroll scheduling
  - Fixed edge cases with daylight saving time transitions
- **PWA Icon Rendering** - Fixed Material Symbols icons not loading in PWA mode (#672, #676)
  - Root cause: Service Worker intercepting Google Fonts with incorrect caching strategy
  - Solution: Service Worker now bypasses Google Fonts, letting browser handle natively
  - Added font preload and fallback CSS for Material Symbols
- **Mobile PWA Navigation** - Restored icons and removed horizontal scrolling (#674)
  - Tightened bottom navigation layout for small screens
  - Added overflow-x protection and responsive media queries
- **Desktop PWA Rendering** - Added PWA support to desktop templates for mobile viewing (#675)
  - Added PWA meta tags (theme-color, apple-mobile-web-app-capable)
  - Added mobile bottom navigation when sidebar is hidden
- **Auto Tap-Out Regression** - Fixed test failures due to missing teacher_id context in auto tap-out logic (#670)

### Technical
- Service worker cache bumped to v5 to force updates
- Added comprehensive multi-tenancy tests for payroll
- Improved mobile responsiveness across all admin templates
- Enhanced documentation organization and clarity

## [1.1.1] - 2025-12-15

### Fixed
- Secured teacher recovery verification by hashing date-of-birth sums and migrating existing records to the new salted hash format (#637)
- Hardened student login redirects and UTC-normalized dashboard earnings/spending calculations to prevent redirect abuse and negative totals (#638)
- Applied the green theme to standalone admin/auth pages and corrected admin heading hierarchy to resolve styling regressions (#635, #639)
- Added cache-busting static asset helper defaults and fallback coverage to stop `static_url` undefined errors across templates (#628-633)
- Stopped insurance management and edit screens from crashing when legacy forms lack the tier grouping field (#640)
- Added one-time prompt for legacy insurance policies and supporting script to encourage migration to tiered plans (#641)

## [1.1.0] - 2024-12-13

### Added
- **Student Analytics Dashboard** - Weekly statistics showing days tapped in, minutes attended, earnings, and spending
- **Savings Projection Graph** - Interactive 12-month visualization of savings growth on bank page using Chart.js
- **Long-Term Goal Items** - Option to mark store items that should be exempt from CWI balance checks (for expensive class rewards)
- **Enhanced Economy Health Warnings** - Specific recommended ranges and actionable guidance for all economy settings
- **Weekly Analytics Calculations** - Backend logic to calculate unique days tapped, total minutes, and transaction summaries
- **Savings Projection Algorithm** - Respects simple/compound interest and compounding frequency settings

### Changed
- **Complete UI Redesign** - Modern interface with softer colors, improved navigation, and better layout
- **Color Scheme** - Reduced brightness and contrast for better eye comfort (primary: #1a4d47, secondary: #d4a574)
- **Student Dashboard Layout** - Added sticky left sidebar navigation for quick access to all features
- **Economy Health Messages** - Improved warnings with absolute values and specific dollar recommendations
- **Tab Navigation** - Fixed CSS scoping to restore visibility across 15+ multi-tab pages

### Fixed
- **Critical: Restored Pending Actions section** on admin dashboard (store approvals, hall passes, insurance claims were missing)
- **Critical: Fixed invisible tabs** on Student Management, Store Management, and other multi-tab pages
- **Fixed missing navigation links** on login screens (account setup, recovery, privacy/terms)
- **Fixed CSS scoping issue** where `.nav-link` styles were applied globally instead of scoped to sidebar
- **Added missing Bootstrap Icons CSS** imports to admin and student layouts
- **Added missing utility classes** (`.btn-white`, `.icon-circle`) for redesigned UI

### Technical
- Database migration `a7b8c9d0e1f2` adds `is_long_term_goal` column to `store_items` table
- Updated `economy_balance.py` to skip long-term goal items in CWI validation
- Added Chart.js (v4.4.0) for savings projection visualization
- Improved query performance for weekly analytics calculations
- Updated forms.py with `is_long_term_goal` BooleanField

## [1.0.0] - 2024-11-29

### Milestone
First stable release of Classroom Token Hub! All critical security issues resolved and production-ready.

## [Unreleased] - Version 0.9.0 (Pre-1.0 Candidate)

### Project Status
The project is ready for version 1.0 release. All critical blockers have been resolved:
- ✅ **P0 Critical Data Leak:** Fixed and deployed (2025-11-29) - See [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/security/CRITICAL_SAME_TEACHER_LEAK.md)
- ✅ **P1 Deprecated Patterns:** All updated to Python 3.12+ and SQLAlchemy 2.0+ (2025-12-06)
- 🔄 **Backfill:** Legacy transaction data being backfilled with interactive verification

### Added (2025-12-11)
- **DEVELOPMENT.md** — Unified development priorities document consolidating all TODO files and roadmap
- **docs/technical-reference/economy-specification.md** — Financial system specification (moved from root)
- **docs/development/ECONOMY_BALANCE_CHECKER.md** — CWI implementation guide (moved from root)

### Changed (2025-12-11)
- **Major documentation consolidation:**
  - Merged `docs/development/TODO.md`, `docs/development/MULTI_TENANCY_TODO.md`, and `ROADMAP_TO_1.0.md` into single `DEVELOPMENT.md`
  - Updated all references to point to new unified documentation structure
  - Updated README.md to reflect v1.0 readiness (all critical blockers resolved)
  - Moved implementation reports to `docs/archive/` for historical reference
- **Security documentation updates:**
  - Updated `CRITICAL_SAME_TEACHER_LEAK.md` status to RESOLVED (deployed with backfill in progress)
  - Updated `docs/README.md` to remove "P0 BLOCKER" label

### Removed (2025-12-11)
- `docs/development/TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/MULTI_TENANCY_TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/TECHNICAL_DEBT_ISSUES.md` — Superseded by DEPRECATED_CODE_PATTERNS.md
- `ROADMAP_TO_1.0.md` — Consolidated into DEVELOPMENT.md

### Added (2025-12-04)
- **PROJECT_HISTORY.md** — Comprehensive document capturing project philosophy, evolution, and key milestones
- **docs/development/DEPRECATED_CODE_PATTERNS.md** — Technical debt tracking for Python 3.12+ and SQLAlchemy 2.0+ compatibility
- Documentation index updated with new security and archive sections

### Changed (2025-12-04)
- **Major documentation reorganization:**
  - Moved security audits to `docs/security/` (CRITICAL_SAME_TEACHER_LEAK.md, MULTI_TENANCY_AUDIT.md)
  - Moved development guides to `docs/development/` (JULES_SETUP.md, SEEDING_INSTRUCTIONS.md, TESTING_SUMMARY.md, MIGRATION_STATUS_REPORT.md)
  - Moved operations docs to `docs/operations/` (MULTI_TENANCY_FIX_DEPLOYMENT.md)
  - Archived historical fix summaries to `docs/archive/` (FIXES_SUMMARY.md, JOIN_CODE_FIX_SUMMARY.md, MIGRATION_FIX_SUMMARY.md, STAGING_MIGRATION_FIX.md)
- Updated `docs/README.md` with comprehensive documentation map including security and archive sections
- Updated main README with version 0.9.0 status and platform-agnostic deployment language
- Removed hardcoded IP addresses from GitHub Actions workflows (now use `secrets.PRODUCTION_SERVER_IP`)

### Removed (2025-12-04)
- **scripts/cleanup_duplicates.py** — Obsolete duplicate cleanup script (superseded by cleanup_duplicates_flask.py)
- Debug print statement in `app/routes/api.py:1198` (replaced with proper logging)

### Fixed (2025-12-04)
- Security: Removed hardcoded production server IP from CI/CD workflows

### Fixed (2025-12-05)
- Student portal: Removed the non-functional class switch button from the class banner and eliminated hover animations to reduce UI confusion.
- Student portal: Scoped payroll attendance and projection data to the currently selected class so multi-class students only see the active class statistics.

### Previous Changes
- Continued repository organization and documentation cleanup
- Moved `PULSETIC_SETUP.md` to `docs/operations/` for better organization
- Moved additional PR-specific reports to `docs/archive/pr-reports/`
- Updated `docs/operations/README.md` with comprehensive guide listings
- Added migration to align `rent_settings` schema with application model by including the `block` column
- Added migration to bring the `banking_settings` table in sync with the model by introducing the missing `block` column

---

## [2025-11-25] - Maintenance & Bypass Enhancements

### Added
- Persistent maintenance mode across deploys (`deploy_updates.sh`) with `--end-maintenance` explicit exit flag
- System admin and token-based maintenance bypass with session persistence (`maintenance_global_bypass`)
- System admin login access during maintenance (`/sysadmin/login`) and login link on `maintenance.html`
- Badge icon/text server-side mapping and status description rendering fallback when JS disabled
- Documentation for maintenance variables and operational workflow (see `docs/DEPLOYMENT.md`)

### Changed
- `deploy_updates.sh` now detects existing maintenance state instead of resetting it
- Bypass logic promotes valid sysadmin/token to global session for teacher/student role testing
- Tests expanded for bypass persistence and login accessibility

### Security
- Bypass token now stored only in environment and session flag; recommends rotation post-window

## [2025-11-24] - Repository Housekeeping

### Added
- Archive directory for historical PR reports (`docs/archive/pr-reports/`)
- README documentation for scripts directory
- README documentation for archived PR reports
- CLI command `normalize-claim-credentials` to backfill student and roster claim hashes to the canonical format

### Changed
- Moved utility scripts to `scripts/` directory for better organization:
  - `check_migration.py`
  - `check_orphaned_insurance.py`
  - `cleanup_duplicates.py`
  - `cleanup_duplicates_flask.py`
- Updated script references in documentation to reflect new paths
- Removed hardcoded paths from `check_orphaned_insurance.py`
- Repository housekeeping: organized files, removed obsolete files, and updated documentation
- Improved repository structure for better maintainability and navigation

### Removed
- Duplicate file: `SECURITY_AUDIT_INSURANCE_OVERHAUL (1).md`
- Moved PR-specific reports to archive (no longer in root):
  - `PR_DESCRIPTION.md`
  - `PR_DESCRIPTION_SECURITY_FIXES.md`
  - `CODE_REVIEW_SECURITY_FIXES.md`
  - `CODE_REVIEW_TECHNICAL_ANALYSIS.md`
  - `FINAL_CODE_REVIEW_SUMMARY.md`
  - `MIGRATION_REPORT_STAGING.md`
  - `REGRESSION_TEST_REPORT_STAGING.md`
  - `SECURITY_FIXES_CONSOLIDATED.md`
  - `SECURITY_FIX_VERIFICATION.md`
  - `SECURITY_FIX_VERIFICATION_UPDATED.md`
  - `SECURITY_AUDIT_INSURANCE_OVERHAUL.md`
  - `PRODUCTION_DEPLOYMENT_INSTRUCTIONS.md`

## [2025-11-20] - Feature Updates

### Added
- Align tap projected pay with payroll settings (#235)
- Simple vs compound interest options with configurable frequency (#233)

### Fixed
- Savings rate input validation error for hidden fields (#231)
- Normalize tap event actions for payroll counts (#230)
- Hall pass network errors and missing status updates (#229)
- Student template redesign to match admin layout (#225, #227)

## [2025-11-19] - Architecture Refactor

### Added
- Comprehensive system architecture documentation
- System admin portal with error logging
- Custom error pages for all major HTTP errors
- GitHub Actions CI/CD to DigitalOcean

### Changed
- Refactored monolithic app.py to modular blueprint architecture

---

## Documentation Maintenance

This changelog tracks significant changes to the codebase. For:
- **Current development tasks**: See [docs/development/TODO.md](docs/development/TODO.md)
- **Planned features**: See [docs/development/TODO.md](docs/development/TODO.md) Roadmap section
- **Technical details**: See [docs/technical-reference/architecture.md](docs/technical-reference/architecture.md)

## Changelog Guidelines

When adding entries:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Reference PR/issue numbers where applicable
- Use present tense for entries
- Keep entries concise but informative
- Update the date when moving Unreleased to a version

**Last Updated:** 2026-01-09
