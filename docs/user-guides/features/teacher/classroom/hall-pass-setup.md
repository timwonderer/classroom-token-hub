---
title: Hall Pass Configuration
category: features
subcategory: teacher-classroom
roles: [teacher]
description: How to configure hall-pass destinations and their limits.
keywords: [hall pass setup, pass types, queue limit, destinations, bathroom, master toggle, configuration]
related:
  - user-guides/features/teacher/classroom/hall-pass
  - user-guides/diagnostics/teacher/hall-pass
  - user-guides/features/student/work/hall-passes
---

# Hall Pass Configuration

## Overview

**Hall Passes → Configure** opens **Hall Pass Configuration**, where you would set your destinations and their limits.

Use this page to configure the destinations and limits students can request in your class.

## What your class actually uses

The saved destinations and their queue limits are the options students see and the destinations the approval queue on the [Hall Pass](hall-pass.md) page works against. New classes start with the built-in destinations; edit the list here when your class uses different destinations or limits.

## Step-by-step instructions

### Reading the page

**How It Works** at the top defines the four controls:

| Control | What it is meant to do |
| --- | --- |
| **Master Toggle** | Turn the whole hall pass system on or off |
| **Pass Type Toggle** | Turn one destination on or off |
| **Students Out At Once** | Most students out at once for that destination. `0` closes the destination |
| **Total Students Out At Once** | The sum of the per-destination limits, calculated for you |

Below that, the **Hall Pass System** switch reads *Currently enabled* or *Currently disabled*. Switching it off greys out every destination row and locks its toggle; hovering a locked toggle explains *You must enable hall pass first*.

### The Pass Types card

The card lists your destinations, each with a name, an on/off switch, a red delete button, and its limit field.

The list opens with the saved destinations for the active class. If none have been configured, it starts with the built-in defaults.

**Add New Pass Type** opens a modal asking for a **Pass Type Name** and a **Students Out At Once** limit. Leaving the limit blank uses the built-in default of 10; there is no "unlimited" setting, and `0` closes the destination rather than opening it. The modal rejects a blank name, a duplicate name, and any negative number.

Adding or removing a destination changes only what is on screen; the page reminds you with *Pass type added. Don't forget to save!*

### Total Limits

The **Total Students Out At Once** box below the list is always read-only and calculated for you, reading *Calculated from individual pass type limits*. It adds up the limits of your enabled destinations, which is exactly the class-wide cap the app enforces.

### Saving

**Save Configuration** submits; **Reset to Saved** discards your on-screen changes and reloads.

Saving with an empty list is refused with *Please add at least one pass type.* Saving with destinations listed reports *Configuration saved successfully!* — but see below.

## Important notes

> [!CAUTION]
> **Save applies to the active class.** After saving, reload the page to confirm the destinations and limits shown are the ones you intended.

> [!WARNING]
> Students see the enabled destinations in their **Choose Break Type** menu. A destination with no available capacity is unavailable until a place opens.

> [!NOTE]
> **One number does both jobs.** A destination's limit caps how many students may be out to *that* destination at once, and the sum of the enabled destinations' limits caps how many may be out class-wide. The page used to offer a separate **Simultaneous Limit** box, which the runtime had no field for; it has been removed rather than left accepting values that changed nothing.

> [!TIP]
> Approvals are the control that actually works. Configure the destinations your class uses here, then use your judgement at the [Hall Pass](hall-pass.md) queue — nothing is silently letting students out.

## Related guides

- [Hall Pass](hall-pass.md)
- [Hall Pass Troubleshooting](../../../diagnostics/teacher/hall-pass.md)
- [Hall Passes (Student)](../../student/work/hall-passes.md)
