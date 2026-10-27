---
title: Copy Configuration
category: features
subcategory: teacher-settings
roles: [teacher]
description: Export one class's settings to a file and import them into another class you own.
keywords: [copy configuration, export, import, settings, configuration file, cthconfig]
related:
  - user-guides/features/teacher/settings/economy-features
  - user-guides/features/teacher/settings/customizations
---

# Copy Configuration

## Overview

**Copy Configuration** lets you set up one class and reuse its settings in another class you teach. You export a file from the class that is already set up, then import that file in the other class.

What can be copied depends on which features are on in the exporting class: economy, banking, payroll, rent, store items, insurance policies, and hall passes. Students, balances, and activity are never copied.

## Step-by-step instructions

### Opening the page

1. In the teacher sidebar, open **Class Tools**.
2. Select **Copy Configuration**.

### Exporting from a class

1. Switch to the class whose settings you want to copy.
2. Under **Export this class**, tick the settings you want. For store items, insurance policies, and hall passes you can untick individual entries.
3. Select **Download configuration**. Your browser saves a file named `class-configuration.cthconfig`.

The file works for **five days**, and only in classes you own. Each new export replaces your previous one, so an older file stops working as soon as you make a new export.

### Importing into another class

1. Switch to the class that should receive the settings, and open **Copy Configuration**.
2. Under **Import into this class**, choose the file and select **Upload and choose configuration**.
3. Tick what you want to bring in. Where a setting has a schedule (payroll, rent, banking, store dates), choose whether to keep the exported schedule or enter your own.
4. Select **Preview import** and check the summary. Dates are shown in this class's time zone.
5. Select **Confirm import into this class**. The confirmation step expires, so confirm soon after previewing.

## What changes when you import

- **Hall passes** replace this class's existing destinations.
- **Store items** and **insurance policies** are added as new offerings. Existing ones are not changed.
- Settings for a feature that is off in this class are skipped, and the page tells you which.
- Store items linked to rent do not carry the rent link. Link them again in this class's Store.
- Purchases, bills, coverage, and other activity that already happened keep their original terms.

You can change anything you imported afterwards through the usual settings pages.

## Common issues

| What you see | What to do |
| --- | --- |
| The file is rejected as expired | Export a new file. Files work for five days. |
| The file is rejected after you exported again | Only your newest export works. Use the latest file. |
| A setting you exported is listed as skipped | Turn that feature on in [Economy Features](economy-features.md), then import again. |
| The confirmation has expired | Upload the file again and preview it before confirming. |
