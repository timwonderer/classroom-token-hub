---
title: Hall Pass Configuration
category: features
subcategory: teacher-classroom
roles: [teacher]
description: How to configure hall-pass destinations and their limits.
keywords: [hall pass setup, pass types, queue limit, destinations, bathroom, configuration]
related:
  - user-guides/features/teacher/classroom/hall-pass
  - user-guides/diagnostics/teacher/hall-pass
  - user-guides/features/student/work/hall-passes
---

# Hall Pass Configuration

## Overview

**Classroom → Hall Pass → Configure** opens the **Hall Pass Configuration** tab, where you set your destinations and their limits.

Use this page to configure the destinations and limits students can request in your class.

## What your class actually uses

The saved destinations and their queue limits are the options students see and the destinations the approval queue on the [Hall Pass](hall-pass.md) page works against. New classes start with the built-in destinations; edit the list here when your class uses different destinations or limits.

## Step-by-step instructions

### Reading the page

**How It Works** explains the destination limit and its read-only total:

| Control | What it is meant to do |
| --- | --- |
| **Students Out At Once** | Maximum number of students who may be out for that destination. A value of `0` blocks the destination. |
| **Total Students Out At Once** | Read-only sum of the destination limits; it is a planning summary, not a separate setting. |

Enable or disable the Hall Pass feature from **Class Tools → Economy Features**. The **Configure** tab only controls destinations and their limits.

### The Pass Types card

The card lists your destinations, each with a name, a red delete button, and its **Students Out At Once** limit.

The list opens with the saved destinations for the active class. If none have been configured, it starts with the built-in defaults.

**Add New Pass Type** opens a modal asking for a **Pass Type Name** and a **Students Out At Once** limit. If the limit is left blank, it defaults to `10`. The modal rejects a blank name, a duplicate name, and any negative number.

Adding or removing a destination changes only what is on screen; the page reminds you with *Pass type added. Don't forget to save!*

### Total Limits

The **Total Limits** box below the list is greyed out and calculated for you. It reads *Calculated from individual destination limits* and adds the per-destination limits.

### Saving

**Save Configuration** submits; **Reset to Saved** discards your on-screen changes and reloads.

Saving with an empty list is refused with *Please add at least one pass type.* Saving with destinations listed reports *Configuration saved successfully!* — but see below.

## Important notes

> [!CAUTION]
> **Save applies to the active class.** After saving, reload the page to confirm the destinations and limits shown are the ones you intended.

> [!WARNING]
> Students see the enabled destinations in their **Choose Break Type** menu. A destination with no available capacity is unavailable until a place opens.

> [!NOTE]
> Approval checks count students currently out. A destination blocks further approvals when its **Students Out At Once** limit is reached. Across the class, approvals are blocked when the count reaches the smaller of **Out Limit** (above the tabs) and the sum of destination limits. For example, an Out Limit of 10 and destination limits totaling 6 block further approvals when 6 students are out. Approved students who have not left are not included in that count.

> [!TIP]
> Approvals are the control that actually works. Configure the destinations your class uses here, then use your judgement at the [Hall Pass](hall-pass.md) queue — nothing is silently letting students out.

## Related guides

- [Hall Pass](hall-pass.md)
- [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md)
- [Hall Passes (Student)](../../student/work/hall-passes.md)
