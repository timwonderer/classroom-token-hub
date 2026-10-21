---
title: Interpretation Troubleshooting
description: Why the Interpretation page is empty, shows "not applicable," or doesn't match what you expected.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/features/teacher/economy/interpretation
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Interpretation Troubleshooting

Diagnostic guide for the teacher **Interpretation** page (`/admin/interpretation`). This page reads what a completed payroll cycle recorded; it does not recompute live and has no alerts, thresholds, or per-student drill-down.

## The page says "No completed interpretation yet"

### Symptoms
- The page shows an empty state instead of any sections or cards.

### Causes & Solutions
**Cause 1: No payroll cycle has completed yet**
- **Check:** Has this class run and completed at least one payroll cycle?
- **Fix:** This is expected for a new class. Interpretation appears automatically the first time a payroll cycle completes — there is nothing to configure or trigger manually.

**Cause 2: Wrong class selected**
- **Check:** Confirm which class is active in the class selector.
- **Fix:** Interpretation is scoped to one class at a time. Switch to the class whose payroll has actually run.

## An observation says "not applicable" instead of a number

### Symptoms
- A section renders, but one or more observations read "not applicable" rather than showing a value.

### Causes & Solutions
**Cause 1: The required feature is disabled for this class**
- **Check:** Open **Class Tools → Economy Features** and check whether the feature that observation depends on (savings, insurance, a given obligation type, etc.) is enabled.
- **Fix:** Nothing to fix if that's intentional. "Not applicable" means the feature itself was off for the class during that cycle — it is not a zero, and not an error. Enabling the feature only affects cycles that complete afterward; a closed cycle is never recomputed.
- **Note:** If the feature was enabled but there was simply no activity of that kind during the cycle, the observation is a computed value of zero, not "not applicable" — if you see "not applicable" on a feature you're sure was enabled, that is a real discrepancy worth reporting.

## Numbers look different from a cycle you remember

### Symptoms
- A past cycle's figures don't match what you expected, or seem to have "changed."

### Causes & Solutions
**Cause 1: You're looking at a different cycle**
- **Check:** Use the cycle selector to confirm which completed cycle you're viewing.
- **Fix:** Each cycle is interpreted exactly as it stood when that cycle closed. Switching cycles in the selector shows a different frozen snapshot, not a live recalculation.

**Cause 2: Expecting a live recomputation**
- **Check:** Did something change in the class (a setting, a correction) after the cycle closed?
- **Fix:** A closed cycle's interpretation is a historical record and is never recomputed after the fact, even if later activity would change the picture. The next completed cycle will reflect the new state.

## Guiding questions look like a verdict or a recommendation

### Symptoms
- A guiding question under a section reads like advice ("you should…") rather than a question.

### Causes & Solutions
- Guiding questions are written to invite reflection, never to recommend a change or label a number good or bad. If one reads as an instruction or a judgment rather than a genuine question, that is a defect in the question itself — report it with the exact section and wording so it can be corrected.

## When to Contact Support
Report this issue if:
- The page errors instead of showing the empty state or a completed cycle.
- An observation's number is clearly wrong given the transactions you can see in that cycle.
- A guiding question reads as a recommendation or a value judgment rather than a question.

Include the class, the cycle you were viewing (or that none had completed yet), and a screenshot if possible.
