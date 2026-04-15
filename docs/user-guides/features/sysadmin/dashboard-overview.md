---
title: Dashboard and Logs
category: features
subcategory: sysadmin
roles: [sysadmin]
description: Guide to monitoring platform health and reviewing global logs.
keywords: [sysadmin, dashboard, grafana, logs, errors, health, monitoring, network]
---

# Dashboard and Logs

## Overview
As a System Administrator, your primary tool for monitoring platform health is the global Dashboard. The main dashboard gives you a high-level overview of important metrics across the platform. Use it with the **Logs** area to check for spikes in user activity or errors.

## Step-by-Step Instructions

### Reading the Dashboard Stats
The dashboard shows four key stats at a glance: **Total Teachers**, **Total Students**, **Active Invites**, and **Open Tickets** (sum of new user reports plus pending or in-review escalated issues). Six quick-action buttons provide fast access to common management tasks.

### Reviewing Support Tickets
1. Navigate to **Support** in the sysadmin sidebar (or use the consolidated `/sysadmin/support` page).
2. The **User Reports** tab shows feedback and bug reports from teachers and students.
3. The **Escalated Issues** tab shows issues teachers have escalated for sysadmin review. Use the **In Review** status to signal active investigation, and **Resolved** when the issue is closed.

### Examining Logs
1. Navigate to **Logs** in your Sysadmin sidebar (combined view at `/sysadmin/combined-logs`).
2. Use the **Error Logs** tab for application-level errors and the **Network Activity** tab for access patterns.
3. Drill into recent entries to identify broken features, recurring issues, or unusual traffic patterns.

### Using the Grafana Integration
The system includes an integrated Grafana dashboard for advanced visualizations:
1. Select **Grafana Dashboard** from the navigation.
2. Ensure you are authenticated through the system proxy.
3. Review economy health metrics, access log patterns, and database performance indicators.

## Important Notes
> [!TIP]
> **Stay proactive:** Check logs daily to catch potential issues before users report them.

> [!NOTE]
> **Use the Logs area broadly:** Error details and network-related views are grouped under the overall **Logs** section instead of separate sidebar items.
