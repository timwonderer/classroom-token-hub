# Classroom Token Hub - Teacher Manual

Welcome to the Classroom Token Hub! This guide covers all teacher features, from onboarding to daily classroom operations.

## Table of Contents

- [Getting Started](#getting-started)
- [Dashboard Overview](#dashboard-overview)
- [Student Management](#student-management)
- [Attendance and Workflows](#attendance-and-workflows)
- [Payroll and Financials](#payroll-and-financials)
- [Store and Rewards](#store-and-rewards)
- [Hall Pass Management](#hall-pass-management)
- [Rent and Insurance](#rent-and-insurance)
- [Announcements](#announcements)
- [Help and Issue Management](#help-and-issue-management)
- [Settings and Security](#settings-and-security)

---

## Getting Started

### Logging In
Create your admin account using an invite code and log in at `/admin/login`. TOTP-based two-factor authentication is required.

### Onboarding
The onboarding flow walks you through enabling features and configuring initial settings such as payroll, banking, rent, and store options.

## Dashboard Overview
The admin dashboard provides quick access to:

- Student roster and class summaries
- Recent transactions and payroll activity
- Attendance snapshots
- Pending store redemptions
- Recent announcements and alerts

## Student Management

### Adding Students
Upload a CSV roster from the **Students** page.

1. Download the CSV template.
2. Fill in `first_name`, `last_name`, `date_of_birth`, and `block`.
3. Upload the file to create student accounts and join codes.

### Viewing Student Details
Student detail pages include:

- Balances (checking/savings)
- Attendance and payroll history
- Store purchases and item usage
- Rent status and insurance policies
- Hall pass balance and activity

### Claiming and Linking Students
Use the **Claim Students** workflow to link legacy or unclaimed students to your account and ensure join codes are correct.

### Deletion Requests
Manage and approve student deletion requests from the **Deletion Requests** page.

## Attendance and Workflows

### Attendance Log
The **Attendance Log** page provides a complete, uneditable history of all Start Work / Break / Done events. This log is the source of payroll calculations.

### Student-Reported Issues
Students can report attendance or transaction issues. Review them in the **Issues Queue** and resolve or escalate as needed.

## Payroll and Financials

### Payroll Settings
Configure payroll schedules and rates in **Payroll**:

- Simple or Advanced settings
- Block-specific rates
- Expected weekly hours (used for economy balance checks)

### Run Payroll
Trigger a payroll run manually from the dashboard or payroll page.

### Payroll History
Use **Payroll History** for detailed records of payroll transactions and filters by block/date.

### Rewards, Fines, and Manual Payments
Issue bonuses, fines, and manual payments directly from the payroll interface.

### Transactions
The **Transactions** page is the master ledger. Filter by student, block, type, or date range and void incorrect entries when needed.

### Banking Settings
Manage interest rates, savings behavior, and transfer rules from **Banking Settings**.

### Economy Health
The **Economy Health** page reviews CWI (Classroom Wage Index) and recommends balanced settings for rent, insurance, and store pricing.

## Store and Rewards
The **Store** page lets you:

- Add, edit, and deactivate store items
- Set inventory, limits, and pricing tiers
- Manage redemption approvals and item usage
- Offer hall pass items as a store purchase type

## Hall Pass Management
Use the **Hall Pass** page to:

- Approve or reject pass requests
- Track who is currently out
- Adjust student hall pass balances

## Rent and Insurance

### Rent Settings
Configure rent amounts, schedules, due dates, and late fees in **Rent Settings**.

### Insurance
Create policies, set premiums and coverage rules, and process student claims in **Insurance**. View student policy details as needed.

## Announcements
Create announcements for students from the **Announcements** page. Announcements can include priority styling and expiration dates.

## Help and Issue Management
The **Help and Support** page includes guidance for teachers. Student-submitted issues appear in the **Issues Queue**, where you can:

- Review reports
- Mark issues resolved
- Escalate bugs to system admins or developers

## Settings and Security

### Feature Settings
Enable or disable features per class period (banking, payroll, store, rent, insurance, hall pass, and issue reporting).

### Account Security
Manage passkeys, recovery options, and credential resets from **Settings** and **Passkey Settings**.

### Backfill and Maintenance
Use **Backfill Join Codes** to fix legacy data when prompted during upgrades or audits.
