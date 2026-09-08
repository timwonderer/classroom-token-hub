---
title: Hall Pass Troubleshooting
description: Why hall pass configuration, approvals, or pass balances behave unexpectedly.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/store
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Hall Pass Troubleshooting

Diagnostic guide for resolving issues with hall pass approvals, tracking, and terminal usage.

## Configure tab says it cannot load the class scope

### Symptoms
- The **Configure** tab shows **Class scope not found** or **Hall pass is disabled for this class**.
- Pass destinations and their controls do not load, so the configuration instructions are unavailable.

### Causes & Solutions
**Cause 1: The active class context is unavailable**
- **Check:** Confirm a class is selected in the teacher sidebar, then reload Hall Pass Management and open **Configure**.
- **Fix:** If a class is selected and the message persists, do not attempt to configure passes. Report the class name and the exact message to support; this is an application configuration failure.

**Cause 2: Hall Pass is disabled for the class**
- **Check:** Open **Class Tools → Economy Features** and verify Hall Pass is enabled for the active class.
- **Fix:** Enable Hall Pass from **Class Tools → Economy Features**, then reload the Hall Pass Management page and open **Configure**. Until it is enabled, destination controls cannot be viewed.

## Passes cannot be approved

### Symptoms
- You cannot approve a student's hall pass request.
- The approve button is disabled or missing.

### Causes & Solutions
**Cause 1: Hall pass feature disabled**
- **Check:** Verify Hall Pass is enabled in **Class Tools → Economy Features** for the class.
- **Fix:** Enable the feature to allow approvals.

**Cause 2: Pass is no longer pending**
- **Check:** Look at the pass status in the queue.
- **Fix:** Approved, rejected, or cancelled passes cannot be re-approved. The student must submit a new request.

**Cause 3: Insufficient passes available**
- **Check:** Check the student's remaining hall pass balance.
- **Fix:** If you require passes for approval, the student cannot be approved if their balance is zero. Grant more passes or waive the requirement in settings.

## Hall pass tracking looks wrong

### Symptoms
- Passes are stuck in the queue.
- Pass deductions are incorrect.

### Causes & Solutions
**Cause 1: Pass stuck as "Approved"**
- **Check:** Verify if the student scanned the pass at the terminal.
- **Fix:** The queue shows approved passes that haven't left yet. Terminal scans move passes from approved to left, then returned. If a student forgets to scan, manually mark them returned.

**Cause 2: Passes not deducted from balance**
- **Check:** Check the reason selected for the pass.
- **Fix:** Office, Summons, or "Done for the day" passes do not deduct from the standard pass balance. Only standard bathroom/water/errand passes do.

## When to Contact Support
Report this issue if:
- The hall pass terminal tablet fails to load or connect to the system.
- Passing scanning results in a systemic server error.
