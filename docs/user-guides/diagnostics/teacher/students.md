---
title: Students and Join Codes Troubleshooting
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/onboarding
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Students and Join Codes Troubleshooting

Diagnostic guide for resolving roster syncing, account claiming, and CSV upload errors.

## Student cannot claim an account

### Symptoms
- A student attempts to use a join code but receives an error.
- The system says "Student Not Found" during claim account setup.

### Causes & Solutions
**Cause 1: Wrong join code**
- **Check:** Verify which class period the student is trying to join.
- **Fix:** Join codes are specific to each class period. Provide the code for their exact block.

**Cause 2: Roster data mismatch**
- **Check:** Look at the student's exact first name, last name, and DOB in the roster.
- **Fix:** The student must type their first initial, full last name, and date of birth exactly as it appears in the roster to verify their identity.

**Cause 3: Seat already claimed**
- **Check:** Check the student list to see if the row already has a linked username.
- **Fix:** If the seat is claimed by the wrong student, you must unlink the account or delete the row and recreate it.

## CSV uploads fail

### Symptoms
- Uploading a class roster CSV results in validation errors or a silent failure.

### Causes & Solutions
**Cause 1: Missing required columns**
- **Check:** Open the CSV in Excel or Notepad.
- **Fix:** Ensure the header contains exactly `first_name`, `last_name`, `date_of_birth`, and `block`.

**Cause 2: Date format errors**
- **Check:** Look at the `date_of_birth` column format.
- **Fix:** Date of birth must match the expected `MM/DD/YYYY` or `YYYY-MM-DD` format described in the template.

**Cause 3: Duplicate rows**
- **Check:** Look for exact duplicate students in the file.
- **Fix:** Remove duplicate rows, as they create claim conflicts.

## When to Contact Support
Report this issue if:
- Legacy students lose connection to their accounts and the "Claim Students" emergency workflow fails.
- The overall student roster fails to load with a 500 server error.
