---
title: Running Payroll
category: payroll
roles: [teacher]
related:
  - features/payroll/settings
  - features/payroll/rewards-and-fines
  - diagnostics/teacher-attendance-payroll
---

# Running Payroll

Process student paychecks and distribute earnings based on attendance.

## What You'll Learn

- When and how to run payroll
- What payroll calculates
- Reviewing payroll results
- Troubleshooting payroll issues

## Quick Start

1. Navigate to **Payroll** from the sidebar
2. Click **Run Payroll** button
3. Review the preview
4. Confirm to process payments

That's it! Tokens are automatically distributed to student checking accounts.

## Before You Run Payroll

### Prerequisites

✅ **Payroll Settings configured**:
- Pay rate set (e.g., $10/hour)
- Pay frequency planned (e.g., weekly, bi-weekly)

✅ **Students have attendance data**:
- Students have clocked in/out during the period
- Attendance log shows work sessions

✅ **Banking feature enabled**:
- Students must have checking accounts to receive pay

### Check Your Settings

Visit **Payroll** → **Settings** to verify:
- **Pay Rate**: How much students earn per hour
- **Block-Specific Rates** (Advanced): Different pay for different periods

> **Note:** Payroll is always run manually. There is no automatic payroll feature. Set a reminder to run payroll on your chosen schedule.

## How Payroll Works

### What Gets Calculated

When you run payroll, the system:

1. **Calculates work time** since last payroll:
   - Looks at all "Start Work" (active tap) and "Done" (inactive tap) events
   - Calculates total minutes between active and inactive taps
   - Includes all time logged, regardless of reason

2. **Applies pay rate**:
   - Converts minutes to hours
   - Multiplies by hourly rate
   - Rounds to nearest cent

3. **Adds rewards and deducts fines**:
   - Includes any pending bonuses
   - Subtracts any pending fines
   - Shows net payment

4. **Creates transactions**:
   - Deposits into checking accounts
   - Records in transaction history
   - Updates student balances

### Example Calculation

Student worked 180 minutes (3 hours) at $10/hour:
- Base pay: 3 hours × $10 = $30.00
- Bonus reward: +$5.00 (good behavior)
- Fine: -$2.00 (late to class)
- **Net payment**: $33.00

## Step-by-Step Guide

### 1. Navigate to Payroll

From admin dashboard:
1. Click **Payroll** in the sidebar
2. You'll see the payroll dashboard with:
   - Last payroll run date
   - Preview of what students will earn
   - Run Payroll button

### 2. Review Payroll Preview

Before running, check the preview table:
- **Student names**: Who will be paid
- **Hours worked**: Time since last payroll
- **Base pay**: Hours × pay rate
- **Adjustments**: Rewards and fines
- **Net pay**: Total deposit amount

**Red flags to watch for**:
- 🚨 Student with 0 hours (didn't clock in)
- 🚨 Unusually high hours (forgot to clock out?)
- 🚨 Negative pay (too many fines)

### 3. Run Payroll

1. Click **Run Payroll**
2. Confirm the action in the modal
3. Wait for processing (usually < 5 seconds)
4. See success confirmation

### 4. Verify Results

After running:
- Check **Payroll History** to see the run
- Spot-check a few students:
  - Go to **Students** → Click a student
  - View their transaction history
  - Verify payroll deposit appears

## Payroll Schedule Planning

**Payroll is always manual** - you must click "Run Payroll" to process payments.

### Best Practices for Consistency

**Set a recurring reminder**:
- Weekly: Every Friday at the same time
- Bi-weekly: Every other Friday
- Use your calendar app to create a recurring event

**Communicate your schedule**:
- Post your payroll day on the classroom board
- Announce before running: "Paychecks processing!"
- Be consistent so students know when to expect pay

**Tips**:
- Run payroll same day/time each week
- Run before students want to shop in the store
- Friday afternoons work well (students see earnings before weekend)

## Handling Special Cases

### Student Forgot to Clock Out

**Problem**: Student shows 24+ hours worked (left session open overnight)

**Solution**:
1. Go to **Attendance Log**
2. Find the student's unclosed session
3. Manually close it with correct time
4. Run payroll again (or note for next run)

### Negative Paycheck

**Problem**: Student's fines exceed their earnings

**Options**:
1. **Allow negative**: Checking balance goes negative (becomes debt)
2. **Waive fines**: Remove some fines before running payroll
3. **Adjust pay**: Give manual bonus to offset

### Missed Payroll Run

**Problem**: You forgot to run payroll last week

**Solution**:
- Just run payroll now
- System calculates all time since last run
- Students get full back pay automatically
- Set a recurring reminder to avoid missing future runs

### Student Not Receiving Pay

**Checklist**:
- ✅ Student has checking account?
- ✅ Student actually worked (clocked in/out)?
- ✅ Student in the correct class period?
- ✅ Payroll feature enabled?
- ✅ Student's account not frozen?

## Payroll History

View past payroll runs:
1. Go to **Payroll** → **Payroll History**
2. See list of all runs with:
   - Date/time of run
   - Total amount paid
   - Number of students paid
   - Filter by date or block

Click on a specific run to see:
- Which students were paid
- How much each received
- Breakdown of hours/rate/adjustments

## Best Practices

### Timing

- **Be consistent**: Run payroll same day/time each week
- **Before store opens**: Give students time to shop
- **Friday afternoons**: Students see their earnings before weekend

### Communication

- **Announce payroll**: "Paychecks processed! Check your balance."
- **Post schedule**: Tell students when to expect pay
- **Explain adjustments**: If someone gets a fine, explain why

### Monitoring

- **Check economy health**: Use Economy Health page to ensure pay rates are balanced
- **Review history**: Look for patterns (who works most? who never clocks in?)
- **Student feedback**: Ask if pay seems fair

### Troubleshooting

- **Run test payroll**: At start of semester, run payroll early to catch issues
- **Keep settings simple**: Start with basic settings, add complexity later
- **Document changes**: Note why you changed pay rates or added fines

## Common Questions

**Q: Can I undo a payroll run?**
A: No, but you can void individual transactions if needed. Go to **Transactions**, find the payroll entry, and click **Void**.

**Q: Do students on break get paid?**
A: Yes, all time between "Start Work" and "Done" taps is paid at the configured rate. The system does not differentiate between work time and break time.

**Q: How can I handle breaks if I don't want to pay for them?**
A: If you want unpaid breaks, ask students to tap "Done" before breaks and "Start Work" after breaks. This creates separate paid work sessions.

**Q: Can different students have different pay rates?**
A: Not per-student, but you can set different rates per block/period if students are in multiple periods.

**Q: What if I change the pay rate mid-semester?**
A: Future payroll runs use the new rate. Past payments are not affected.

**Q: Can students see their hours before payroll runs?**
A: Yes! Students can view their attendance history and projected earnings on the **Work & Pay** page.

## Related Articles

- [Payroll Settings](/docs/features/payroll/settings)
- [Rewards and Fines](/docs/features/payroll/rewards-and-fines)
- [Economy Health](/docs/features/payroll/economy-health)
- [Attendance Tracking](/docs/features/students/attendance)

## Need Help?

- Full [Teacher Diagnostics Index](/docs/diagnostics/teacher)
- Check [Economy Health](/docs/features/payroll/economy-health) for balance guidance
- Contact support for technical issues
