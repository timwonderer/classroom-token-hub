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

**How It Works** at the top defines the five setup controls:

| Control | What it is meant to do |
| --- | --- |
| **Pass Type Toggle** | Turn one destination on or off |
| **Queue Limit** | Most students approved and waiting for that destination. Blank means unlimited |
| **Simultaneous Limit** | Displayed in the form, but not persisted or enforced by the current runtime. Do not rely on it. |
| **Total Queue Limit** | Cap on approved-and-waiting across all destinations |
| **Total Simultaneous Limit** | Cap on students out across all destinations |

Enable or disable the Hall Pass feature from **Class Tools → Economy Features**. The **Configure** tab only controls destinations and their limits.

### The Pass Types card

The card lists your destinations, each with a name, an on/off switch, a red delete button, and its two limit fields.

The list opens with the saved destinations for the active class. If none have been configured, it starts with the built-in defaults.

**Add New Pass Type** opens a modal asking for a **Pass Type Name** and, optionally, a **Queue Limit** and a **Simultaneous Limit**. Both limit boxes show *Unlimited* as their placeholder — leaving them blank means no cap. The modal rejects a blank name, a duplicate name, and any negative number.

Adding or removing a destination changes only what is on screen; the page reminds you with *Pass type added. Don't forget to save!*

### Total Limits

The two **Total Limits** boxes below the list are usually greyed out and calculated for you, reading *Calculated from individual pass type limits* — they simply add up the per-destination limits.

They unlock only when at least one enabled destination has an unlimited limit, since there is then nothing to add up. When unlocked, they enforce a floor: *Must be at least N (sum of non-unlimited pass types)*.

### Saving

**Save Configuration** submits; **Reset to Saved** discards your on-screen changes and reloads.

Saving with an empty list is refused with *Please add at least one pass type.* Saving with destinations listed reports *Configuration saved successfully!* — but see below.

## Important notes

> [!CAUTION]
> **Save applies to the active class.** After saving, reload the page to confirm the destinations and limits shown are the ones you intended.

> [!WARNING]
> Students see the enabled destinations in their **Choose Break Type** menu. A destination with no available capacity is unavailable until a place opens.

> [!NOTE]
> The saved **Queue Limit** is enforced per destination, and the class-wide **Out Limit** is enforced across destinations. There is no separate simultaneous-limit field in the current runtime payload.

> [!NOTE]
> **Simultaneous and Total Limits are not enforcement controls in the current runtime.** The per-destination **Queue Limit** and class-wide **Out Limit** are the limits that affect approvals. The simultaneous and total-limit fields may be displayed, but their values are not persisted or enforced.

> [!TIP]
> Approvals are the control that actually works. Configure the destinations your class uses here, then use your judgement at the [Hall Pass](hall-pass.md) queue — nothing is silently letting students out.

## Related guides

- [Hall Pass](hall-pass.md)
- [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md)
- [Hall Passes (Student)](../../student/work/hall-passes.md)
