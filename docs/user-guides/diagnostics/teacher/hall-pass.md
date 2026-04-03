---
title: Hall Pass Troubleshooting
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/store
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Hall Pass Troubleshooting

Diagnostic guide for resolving issues with hall pass approvals, tracking, and student self-checkout.

> [!IMPORTANT]
> **We have changed the way student check-out/in for hall passes.** Instead of using a separate terminal, students will perform all actions within their dashboard. As a result, the hall pass terminal and queue systems have been retired. If you have saved your links to the terminal, queue, or verification page, please be advised that they are no longer valid.

> [!NOTE]
> **The Hall Pass Verification page has been upgraded to protect student privacy.** A new link has been created for your verification page. Instead of displaying the last 10 hall pass record, the verification page now requires school personnel to provide student name and class sections to look up a hall pass record. The verfication page will only display the record if:
>
> 1. The entered name and class section matches a record in your hall pass history
> 2. The record was created on the same day
>
> For example, if a hall monitor typed in "Monica C." and "Period 5" on 9/13/2025 using the link provided by Ms. Cortez, the verification page will show hall pass record if:
>
> 1. Ms. Cortez's Period 5 has a student named Monica C.
> 2. Monica C. have used a hall pass during Period 5
> 3. That hall pass record was dated 9/13/2025
>
> Otherwise, the verification page will return no result.

## Passes cannot be approved

### Symptoms
- You cannot approve a student's hall pass request.
- The approve button is disabled or missing.

### Causes & Solutions
**Cause 1: Hall pass feature disabled**
- **Check:** Verify Hall Pass is enabled in Feature Settings for the class.
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
- **Check:** Verify whether the student checked out from their dashboard.
- **Fix:** Approved passes stay in the **Approved** tab until the student uses their dashboard to check out. After checkout, the pass moves to **Out**. When they return, use **Returned** so the pass moves to **History**.

**Cause 2: Passes not deducted from balance**
- **Check:** Check the reason selected for the pass.
- **Fix:** Office, Summons, or "Done for the day" passes do not deduct from the standard pass balance. Only standard bathroom/water/errand passes do.

## When to Contact Support
Report this issue if:
- Approved passes never move out of **Approved** after the student checks out from their dashboard.
- Returning a pass or loading Hall Pass Management results in a recurring server error.
