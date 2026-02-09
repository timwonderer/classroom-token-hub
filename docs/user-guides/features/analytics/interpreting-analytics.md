---
title: Interpreting the Analytics Dashboard
category: features
subcategory: analytics
audience: teachers
---

# Interpreting the Analytics Dashboard

**Audience:** Teachers
**Version:** 1.7.0+
**Route:** `/admin/analytics`

---

## Overview

The Analytics Dashboard provides a comprehensive view of your classroom economy's health through privacy-preserving metrics. Instead of comparing students to each other, all metrics are relative to your Class Wealth Index (CWI), helping you identify trends and take action without creating competition.

**Core Principle:** *"Something is drifting — and I know what lever to pull"*

---

## Accessing the Dashboard

1. Log in to your teacher account
2. Navigate to **Economy** section in sidebar
3. Click **Analytics Dashboard**
4. Select time window: **Weekly** or **Monthly**

---

## Understanding CWI-Relative Metrics

All analytics use the **Class Wealth Index (CWI)** as the baseline. This is the target balance you've designed for your economy.

**Why CWI-Relative?**
- Prevents student comparison and competition
- Focuses on economy health, not individual rankings
- Makes metrics meaningful across different class sizes and economies
- Privacy-preserving (no absolute balances shown)

**Example:**
- If your CWI is $100 and a student has $150, they're at +50% of CWI
- If they have $50, they're at -50% of CWI

---

## Key Metrics Explained

### 1. Participation Rate

**What It Measures:** Percentage of students actively engaging with the economy

**How It's Calculated:**
- Students who tapped in/out at least once in the time window
- Students who made at least one transaction
- Divided by total enrolled students

**What the Numbers Mean:**
- **80-100%:** Excellent engagement
- **60-79%:** Good engagement, room for improvement
- **40-59%:** Moderate engagement, investigate barriers
- **Below 40%:** Low engagement, intervention needed

**Trend Indicators:**
- ⬆️ **Improving:** More students participating over time
- ➡️ **Stable:** Participation steady
- ⬇️ **Worsening:** Declining participation

**What to Do:**

**If Participation is Low:**
- Check if students understand how to tap in/out
- Verify payroll is running regularly
- Review store items - are they appealing?
- Consider adding bonus incentives
- Ask students what would increase engagement

**If Participation is High:**
- Keep doing what you're doing!
- Consider adding new features to maintain interest
- Share success strategies with other teachers

---

### 2. Money Velocity

**What It Measures:** How quickly money circulates through your economy

**How It's Calculated:**
- Total transaction count per student in the time window
- Average frequency of economic activity

**What the Numbers Mean:**
- **High Velocity (5+ transactions/student):** Money flowing freely, active economy
- **Medium Velocity (2-4 transactions/student):** Healthy economy, students engaging regularly
- **Low Velocity (0-1 transactions/student):** Stagnant economy, money not circulating

**Trend Indicators:**
- ⬆️ **Improving:** More transactions happening
- ➡️ **Stable:** Consistent activity
- ⬇️ **Worsening:** Decreasing transactions

**What to Do:**

**If Velocity is Too Low:**
- Add more store items to encourage spending
- Create limited-time offers or sales
- Introduce collective goal items
- Check if rent/insurance are too high (students saving to survive)
- Lower prices or increase pay rates

**If Velocity is Too High:**
- May indicate prices are too low
- Students might be accumulating too much money
- Consider inflation adjustments
- Raise CWI to match new economy baseline

---

### 3. CWI Deviation Bands

**What It Measures:** How many students are drifting significantly from your target CWI

**How It's Calculated:**
- Count of students more than 50% above CWI (wealthy students)
- Count of students more than 50% below CWI (struggling students)
- Percentage of class in deviation zones

**What the Numbers Mean:**
- **0-10% Deviation:** Excellent economy balance
- **10-20% Deviation:** Good balance, minor adjustments may help
- **20-35% Deviation:** Moderate imbalance, action recommended
- **35%+ Deviation:** Significant imbalance, intervention needed

**Trend Indicators:**
- ⬆️ **Improving:** More students near CWI target
- ➡️ **Stable:** Balance maintained
- ⬇️ **Worsening:** More students drifting from target

**What to Do:**

**If Too Many Students Are Wealthy (+50% CWI):**
- Wages may be too high relative to expenses
- Store prices may be too low
- Consider raising rent/insurance premiums
- Add premium store items
- Implement progressive rent (higher earners pay more)

**If Too Many Students Are Struggling (-50% CWI):**
- Expenses may be too high relative to income
- Wages may be too low
- Store prices may be too high
- Check attendance - are students able to work consistently?
- Offer rent waivers or payment plans
- Consider bonus payroll for participation

**If Balance is Good:**
- You've found the sweet spot!
- Monitor for seasonal changes (testing weeks, holidays)
- Document your settings for future reference

---

### 4. Budget Survival Pass Rate

**What It Measures:** Percentage of students who can afford basic expenses (rent + insurance)

**How It's Calculated:**
- Students whose balance ≥ (monthly rent + insurance premium)
- Indicates financial sustainability of your economy

**What the Numbers Mean:**
- **90-100%:** Nearly all students financially stable
- **70-89%:** Most students surviving, some struggling
- **50-69%:** Many students in financial stress
- **Below 50%:** Economy is unsustainable for majority

**Trend Indicators:**
- ⬆️ **Improving:** More students can afford basics
- ➡️ **Stable:** Survival rate maintained
- ⬇️ **Worsening:** More students unable to afford basics

**What to Do:**

**If Survival Rate is Low:**
- **CRITICAL:** This suggests fundamental economy imbalance
- Reduce rent and/or insurance costs
- Increase base pay rate
- Offer more frequent payroll
- Provide temporary waivers or assistance
- Check if there are unexpected fees accumulating

**If Survival Rate is Too High (100%):**
- Expenses may be too low
- Students should feel some financial pressure (teaches budgeting)
- Consider raising rent slightly
- Add optional premium services (insurance upgrades)

---

## Visual Alerts

The dashboard shows color-coded alerts when metrics need attention:

### Alert Types

**🔴 Critical (Red):**
- Participation below 40%
- Survival rate below 50%
- Urgent action required

**🟡 Warning (Yellow):**
- Moderate issues detected
- Review and consider adjustments
- Not urgent but should be addressed

**🟢 Healthy (Green):**
- Metrics in good range
- Economy functioning well
- Maintain current settings

### Alert Components

Each alert includes:

1. **What Changed:** Specific metric that triggered alert
2. **Why It Matters:** Impact on classroom economy
3. **Suggested Actions:** Concrete steps you can take

**Example Alert:**
```
🟡 Low Money Velocity Detected

What changed: Average transactions per student dropped from 4.2 to 1.8 this week

Why it matters: Students are not spending money, which may indicate:
- Prices too high for current earnings
- Store items not appealing
- Students hoarding for large purchases

Suggested actions:
- Review store inventory and add new items
- Run a limited-time sale (20% off)
- Check if upcoming rent payment causing saving behavior
- Consider bonus payroll to inject liquidity
```

---

## Event Annotations

The timeline shows important economy events that may explain metric changes:

### Event Types

**💰 Wage Changes:**
- Pay rate increased/decreased
- Affects income levels

**🏠 Rent Changes:**
- Rent amount modified
- Affects baseline expenses

**📈 Inflation Events:**
- Price adjustments across store
- Affects purchasing power

**💸 Bonus Payroll:**
- One-time payouts
- Creates temporary spike in activity

**🎯 Store Events:**
- New items added
- Sales or promotions
- May boost velocity

**Why Events Matter:**
Correlating events with metric changes helps you understand cause and effect.

**Example:**
- Rent increased on Monday → Survival rate dropped from 85% to 60%
- **Insight:** Rent increase was too steep, consider rollback or gradual increase

---

## Time Windows

### Weekly View

**Best For:**
- Detecting short-term trends
- Immediate feedback on recent changes
- Week-to-week comparison

**Use Cases:**
- Just changed pay rate or rent - see immediate impact
- Testing new store items
- Monitoring after break/holiday

### Monthly View

**Best For:**
- Long-term trend analysis
- Seasonal patterns
- Sustained economy health

**Use Cases:**
- Evaluating overall economy balance
- Planning semester adjustments
- Reporting to administration

---

## Action Playbook

### Scenario 1: Low Participation + Low Velocity
**Problem:** Students aren't engaging with the economy

**Diagnosis:** Lack of interest or understanding

**Actions:**
1. Hold class discussion about the economy
2. Explain how to earn and spend money
3. Add exciting new store items
4. Create a limited-time promotion
5. Offer bonus for first transaction this week

---

### Scenario 2: High CWI Deviation (Many Wealthy)
**Problem:** Too much money in the economy

**Diagnosis:** Income > Expenses

**Actions:**
1. Raise rent by 10-20%
2. Add premium store items
3. Increase insurance premiums
4. Consider one-time "taxes" on high earners
5. Reduce pay rate slightly (5-10%)

---

### Scenario 3: High CWI Deviation (Many Struggling)
**Problem:** Students can't afford basics

**Diagnosis:** Expenses > Income

**Actions:**
1. Increase pay rate by 10-20%
2. Lower rent temporarily
3. Offer rent waivers to struggling students
4. Add more frequent payroll
5. Reduce or eliminate late fees

---

### Scenario 4: Low Survival Rate
**Problem:** Students can't afford rent + insurance

**Diagnosis:** Fundamental imbalance

**Actions (URGENT):**
1. Immediately reduce rent by 25-50%
2. Make insurance optional temporarily
3. Run emergency bonus payroll
4. Provide universal rent waiver for 1 week
5. Recalculate CWI with current settings
6. Gradually reintroduce expenses after stabilizing

---

### Scenario 5: All Metrics Healthy
**Problem:** No problem! Economy is balanced

**Actions:**
1. Document current settings for future reference
2. Monitor for seasonal changes
3. Consider gradual growth (small increases)
4. Focus on adding variety (new items, features)
5. Share your success with other teachers

---

## Best Practices

### Regular Monitoring

**Weekly:**
- Quick check of key metrics
- Review any new alerts
- Respond to critical issues

**Monthly:**
- Deep dive into trends
- Plan adjustments for next month
- Document changes and results

**Quarterly:**
- Evaluate overall economy design
- Consider major redesigns if needed
- Update CWI if economy shifted

### Making Changes

**Golden Rules:**
1. **Change One Thing at a Time** - Can't tell what worked if you change everything
2. **Small Increments** - 10-20% adjustments, not 100% changes
3. **Wait and Observe** - Give changes 1-2 weeks to show impact
4. **Document Everything** - Note what you changed and why
5. **Communicate** - Tell students about major changes

### Common Mistakes

❌ **Overreacting to Short-Term Blips**
- One bad week doesn't mean broken economy
- Look for sustained trends (2-3 weeks)

❌ **Changing Too Much Too Fast**
- Makes it impossible to diagnose issues
- Can destabilize a working economy

❌ **Ignoring Student Feedback**
- Analytics show "what," students explain "why"
- Ask students about their experience

❌ **Comparing to Other Teachers**
- Every classroom is unique
- Your CWI is designed for YOUR students

❌ **Expecting Perfection**
- Some variation is normal and healthy
- 80-90% in target range is excellent

---

## Privacy and Ethics

### What Analytics Show

✅ **Do Show:**
- Aggregate class metrics
- Trend patterns
- System health indicators

❌ **Don't Show:**
- Individual student names
- Specific balances
- Comparative rankings
- Leaderboards

### Using Analytics Ethically

**DO:**
- Use data to improve economy balance
- Intervene when students struggling
- Adjust settings for fairness

**DON'T:**
- Share individual data publicly
- Create competition between students
- Use data punitively
- Pressure students based on metrics

**Remember:** Analytics are a tool for systemic improvement, not individual judgment.

---

## Troubleshooting

### "Metrics Seem Wrong"

**Possible Causes:**
- Recent data hasn't processed yet (check timestamp)
- Major economy event skewed calculations
- Need to recalculate CWI

**Solutions:**
- Wait 24 hours for data to stabilize
- Check event timeline for anomalies
- Verify CWI matches your current design

### "No Data Showing"

**Possible Causes:**
- No transactions in time window
- Analytics not yet computed
- Technical issue

**Solutions:**
- Select longer time window (monthly)
- Run a test transaction
- Report issue to system admin

### "Conflicting Signals"

**Example:** High participation but low velocity

**Meaning:** Students logging in but not transacting

**Diagnosis:** Possibly saving for something, or store not appealing

**Action:** Check store inventory, ask students directly

---

## Advanced Usage

### Seasonal Adjustments

**Start of Year:**
- Lower expenses initially
- Higher participation focus
- Gradual introduction of features

**Mid-Year:**
- Full economy operational
- Optimize for balance
- Add variety to maintain interest

**End of Year:**
- Consider clearance sales
- Zero out balances if desired
- Plan for next year's CWI

### Economy Experiments

Use analytics to test:
- Different pay structures
- Progressive rent systems
- Store promotion effectiveness
- Insurance uptake rates

**Method:**
1. Record baseline metrics
2. Implement change
3. Monitor for 2-4 weeks
4. Compare to baseline
5. Keep or revert based on results

---

## Related Documentation

- [Economy Design Guide](../economy_guide.md) - Designing balanced economies
- [CWI Calculator](../technical-reference/economy-specification.md) - How CWI is calculated
- [Teacher Manual](../teacher_manual.md) - Complete teacher guide

---

**Last Updated:** 2026-01-09
**Version:** 1.7.0
**Feedback:** Report issues or suggestions via Help & Support
