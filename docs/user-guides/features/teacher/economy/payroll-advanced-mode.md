---
title: Payroll Advanced Mode
category: features
subcategory: teacher-economy
roles: [teacher]
description: What the Advanced Mode toggle adds to payroll settings — time increments, overtime and the pay simulator — and which of those actually change what students are paid.
keywords: [payroll, advanced mode, overtime, time increment, pay simulator, pay schedule, daily limit, auto run, automatic payroll]
related:
  - user-guides/features/teacher/economy/payroll-settings
  - user-guides/features/teacher/economy/payroll-run
  - user-guides/diagnostics/teacher/attendance-payroll
---

# Payroll Advanced Mode

## Overview

The **Payroll Settings** card on **Economy > Payroll** has an **Advanced Mode** switch in its header. Simple mode asks four questions; advanced mode asks nine. The extra fields are not all live, so it is worth knowing which ones reach the ledger before you build a pay policy on them.

Underneath, payroll is one calculation: seconds worked since the last run, multiplied by a rate, rounded to the cent. Advanced mode changes how you *express* the rate and the schedule. It does not currently change that formula.

## Step-by-step instructions

### Switching modes

Flip **Advanced Mode** in the card header. The form swaps between two sets of fields, and the mode you were in when you pressed **Save Settings** is the one that is stored.

Saving clears the other mode's fields. Save in simple mode and overtime and the advanced daily limit are reset; save in advanced mode and the simple daily limit is cleared. Nothing carries across, so treat a mode switch as a rewrite of the policy rather than an edit.

### Pay Amount and Time Increment

Advanced mode splits the rate in two: **Pay Amount** and a **Time Increment** of **Per Second**, **Per Minute**, **Per Hour**, or **Per Day**.

This is a data-entry convenience. Whatever you enter is converted to a single internal rate on save, so $0.25 per minute and $15.00 per hour are the same policy stored two ways. Pick whichever wording your students think in.

### Overtime

Ticking **Enable Overtime** opens a **Threshold** and its **Unit**.

The threshold saves and reappears when you come back. It does not affect pay. Every second is paid at the base rate no matter how many hours a student accumulates. See *Important notes*.

### Daily Time Limit

This is the advanced form of the limit simple mode expresses as hours and minutes: a value plus a unit of seconds, minutes, or hours.

It works, and it is the one advanced setting that changes student behaviour. When a student reaches the limit they are automatically tapped out and cannot tap back in until the next day. The counter resets at midnight PST. Leave it blank for no limit.

### Pay Schedule

Payroll runs **Weekly**, **Bi-weekly**, or **Monthly** — the same three choices as simple mode.

**First Pay Date** is required and anchors the calendar. Every later payday is counted from it: weekly and bi-weekly paydays fall on the same weekday, and monthly paydays fall on the same date each month. When that date does not exist in a month, payday moves to the first day of the next month and then returns to the original date: a schedule starting January 31 pays on January 31, March 1, March 31, May 1, May 31, and so on. A month is never counted as 30 days.

The **Next Payroll** figure at the top of the page comes from that calendar, so a manual run does not shift it.

### Pay Simulator

The panel to the right of the form estimates earnings from your unsaved form values. Enter **Minutes per Class** and **Classes per Week**, then choose **Calculate** for a **Per Week**, **Per Month (4 weeks)**, and **Per Semester (18 weeks)** figure.

It reads the rate straight off the form, so it is accurate for the rate and honest about the parts of advanced mode that do not work — it ignores overtime, exactly as payroll does. It also ignores your **Daily Time Limit**, which payroll does *not*. If you have set a limit that your simulated day exceeds, the estimate will be too high.

Below the simulator, **Current Settings** narrates your form in plain English.

### Validation

The form checks your entries when you save and lists any failures in a red box above the button:

| Message | What it means |
| --- | --- |
| *Maximum time per day overrides overtime. Consider disabling one of them.* | A student tapped out at the limit can never cross an overtime threshold above it |

Saving without a **First Pay Date** is refused with *Choose the first payday. Payroll settings need a first pay date.*

## Important notes

> [!CAUTION]
> **Overtime does not pay overtime.** The threshold saves and redisplays, and it does not enter the pay calculation. A student who works twelve hours is paid twelve hours at the base rate. Do not promise students an overtime rate — set a base rate you are happy to pay for every hour worked.

> [!NOTE]
> **Pay is exact.** Time is measured to the second and money is rounded once, to the cent. Choosing **Per Hour** or **Per Day** as your increment only changes how you type the rate: a student who works nine minutes of an hour is paid for nine minutes.

> [!NOTE]
> **Due payroll cycles run through the scheduler.** The scheduled job checks each class's **Next Payroll** date and invokes the same completion workflow as **Run Payroll**. The page does not provide a separate auto-run toggle; saving the schedule is what makes a class eligible for automatic execution.

> [!IMPORTANT]
> **Settings are per class.** One policy is stored for the class you currently have selected. If you teach several periods and want different rates, switch class context and save again for each one. Rate and schedule changes apply only to future runs; money already paid is never recalculated.

> [!TIP]
> Advanced mode earns its place when you want a **Daily** or **Custom** schedule, a per-second or per-day way of describing the rate, or a daily limit finer than whole minutes. If you only want a different hourly rate, simple mode does the same job with fewer ways to be misled.

## Related guides

- [Payroll Settings](payroll-settings.md)
- [Run Payroll](payroll-run.md)
- [Attendance and Payroll Troubleshooting](../../../diagnostics/teacher/attendance-payroll.md)
