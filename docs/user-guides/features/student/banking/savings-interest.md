---
title: Savings Interest
category: features
subcategory: student-banking
roles: [student]
description: Find your interest rate, read the 12-month savings projection, and understand what the chart is and is not promising you.
keywords: [savings, interest, interest rate, projection, chart, compound, simple, APY, payout, next payout, monthly interest]
related:
  - user-guides/features/student/banking/accounts-transfers
  - user-guides/diagnostics/student/money
---

# Savings Interest

## Overview

Savings can earn interest. Whether it does, and at what rate, is a setting your teacher controls — the app will not invent a rate to make the page look better.

Everything about interest lives on the **Accounts** page, on its first tab, also called **Accounts**.

## Step-by-step instructions

### Finding your rate

The **Statistics** card, to the right of your balances, carries four numbers. Two of them are about interest:

| Statistic | What it means |
| --- | --- |
| **Total Earnings** | Everything you have earned in this class |
| **Monthly Interest Rate** | Your class's annual rate divided by twelve, shown as a percentage |
| **Estimated interest next payout** | What your next payout will be if your savings stay as they are until the payout period ends: a week's worth if your class pays weekly, a month's worth if it pays monthly |
| **Total Transactions** | How many entries are in your history |

**Monthly Interest Rate** is a *monthly* slice of an *annual* rate. If your class is set to 6% a year, this reads 0.50%. It is not a separate rate — it is the same rate expressed per month.

The **Transfer** tab states the same thing the other way round, in a blue **Tip** under the form: the annual rate, whether it is simple or compound, and *approximately $X per weekly payout* or *per monthly payout*.

### Reading the projection

Below Statistics, **Savings Balance Projection (12 Months)** draws a line from today out twelve months. Hovering a point shows *Balance: $NN.NN*. The horizontal labels are **Now**, then **Month 1** through **Month 12**.

The caption under the chart tells you exactly what it assumed:

> Projection based on current balance of **$X** with N.NN% annual compound interest (compounded monthly)

If your class has no rate set, it says so plainly instead:

> Savings interest is not currently configured for this class, so your balance of **$X** is projected flat.

A flat line is not a broken chart. It is the app declining to show you growth that is not configured.

### Simple and compound

The caption names which one your class uses.

- **Simple** — interest is worked out on your savings balance. Interest that is still building up does not earn anything until it is paid.
- **Compound** — interest that is still building up also earns, so the line curves upward faster. The caption also names how often it compounds.

In both cases, once interest is paid into your savings it is part of your balance and earns like the rest of it. For **Simple** that is a known issue: true simple interest would never earn on interest already paid. A fix is being tracked.

Over one term the difference is usually small. Over the whole chart it is visible.

### When interest arrives

Interest is paid on the schedule your teacher chose, once each payout period has ended:

- **Weekly** — a week runs Monday to Sunday in your class's time zone. The payout arrives shortly after midnight going into Monday.
- **Monthly** — a month is the calendar month in your class's time zone. The payout arrives shortly after midnight on the 1st.

Interest is earned day by day. At the end of each day (midnight in your class's time zone) the app notes your savings balance, and that day earns a small slice of the yearly rate on it. When the period ends, the days' interest is added up and paid as one amount.

So money earns only for the days it was actually in savings. Money moved in on Sunday night earns one day, not a whole week, and money moved out on Sunday still keeps what it earned Monday to Saturday.

A credited payout appears in your history like anything else: **Accounts → Transactions → Savings**, with the type **Interest** and the description *Weekly Savings Interest* or *Monthly Savings Interest*.

Payouts happen automatically — nobody has to press a button, and you cannot trigger one early. If a period has ended, your class shows a rate, and you had savings at the time, but no payout has appeared, tell your teacher.

## Important notes

> [!IMPORTANT]
> **The projection assumes you never touch the money.** It takes today's savings balance and grows it forward, day by day and payout by payout, with nothing added and nothing removed. It is a picture of the rate, not a prediction of your behaviour. Every transfer out resets the line lower.

> [!NOTE]
> **Only savings earns.** Checking does not. That is the trade — savings grows but cannot be spent, checking can be spent but sits still. See [Accounts and Transfers](accounts-transfers.md).

> [!NOTE]
> **The chart has a text version.** The same month-by-month figures are published in a table beside the chart for screen readers, captioned *Projected savings balance by month*. Nothing in the chart is picture-only.

> [!TIP]
> Compare **Estimated interest next payout** against the price of something in the store. If a payout of interest does not buy a pencil, the way to grow savings faster is a bigger balance, not a longer wait — the rate is fixed, the balance is the part you control.

## Related guides

- [Accounts and Transfers](accounts-transfers.md)
- [Troubleshooting Balances, Transfers, and Interest](../../../diagnostics/student/money.md)
