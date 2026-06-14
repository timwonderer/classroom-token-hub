# Accessibility Conformance Report (WCAG 2.1 Level AA)

**Product Name:** Classroom Token Hub
**Report Date:** June 13, 2026
**Evaluation Method:** Automated assessment using Deque Systems' `axe-core` v4.9.1 engine and Playwright headless Chromium auditing, supplemented by static AST structural analysis.
**Conformance Target:** Web Content Accessibility Guidelines (WCAG) 2.1, Level AA

---

## Executive Summary

Classroom Token Hub is committed to providing an inclusive educational platform for all students and teachers. Following a comprehensive accessibility audit and remediation phase, the platform has achieved **100% automated compliance** with WCAG 2.1 Level AA standards across all primary user-facing interfaces. 

Zero "Critical" or "Serious" WCAG violations were detected during the most recent automated audit of the fully-rendered application DOM.

---

## Evaluation Scope

The following core views and application states were explicitly audited under authenticated session contexts:

**Student Experience:**
- Student Dashboard & Activity Feed
- Bank Transfer interface
- Property Rent interface
- Economy Store / Purchasing system
- Insurance Marketplace & Claims
- Help & Support portal

**Teacher/Administrator Experience:**
- Class Dashboard & Analytics
- Roster & Student Management
- Rent Settings configuration
- Store Catalog management
- Insurance Policy generation
- Payroll & Tax configuration
- Hall Pass issuance & auditing

---

## Conformance Results by Principle

### 1. Perceivable
*Information and user interface components must be presentable to users in ways they can perceive.*

**Status: Supports**
- **Non-text Content:** All informative images and interactive icons contain equivalent `alt` attributes or `aria-label` descriptors. Material icons used strictly for decoration are hidden from screen readers.
- **Adaptable Structure:** The platform employs strict HTML5 semantic landmarks (`<main>`, `<nav>`, `<aside>`). All pages maintain a logical heading outline containing exactly one `<h1>` per view, with contiguous descending sub-headings (`<h2>`, `<h3>`).
- **Contrast (Minimum):** All text elements, including contextual alert boxes, badges, and outline buttons, achieve a minimum contrast ratio of **4.5:1** against their respective backgrounds, meeting the WCAG 1.4.3 standard. Dynamic CSS calculations are used to guarantee compliance across custom school themes.

### 2. Operable
*User interface components and navigation must be operable.*

**Status: Supports**
- **Keyboard Accessible:** All interactive elements (forms, tabs, dropdowns, modals) are natively accessible via keyboard navigation.
- **Navigable Names:** All links and buttons contain discernible, meaningful text. Where visual text is absent (e.g., icon-only action buttons), programmatic `aria-label` attributes provide full context to assistive technologies.
- **Bypass Blocks:** Semantic structural markup allows assistive technologies to reliably bypass repetitive navigation blocks.

### 3. Understandable
*Information and the operation of the user interface must be understandable.*

**Status: Supports**
- **Predictable:** The platform utilizes standard, predictable Bootstrap-based layout paradigms.
- **Input Assistance:** Every form control (including hidden or system-generated inputs) is explicitly associated with a text `<label>` using matching `id` and `for` attributes, or contains a valid `aria-label`. Placeholder text is strictly treated as supplementary and is never utilized as a primary label.
- **Error Identification:** Form validation failures provide clear, visually distinct error messages with associated context.

### 4. Robust
*Content must be robust enough that it can be interpreted reliably by a wide variety of user agents, including assistive technologies.*

**Status: Supports**
- **Parsing Compatibility:** The platform strictly enforces unique DOM `id` attributes to prevent identifier collisions and ensure assistive technology reliably maps interactive controls.
- **Name, Role, Value:** Custom components (such as toggle switches and complex data tables) utilize standard HTML5 input types or appropriate ARIA roles to correctly broadcast their states to user agents.

---

## Ongoing Commitment

Accessibility is treated as a continuous integration requirement, not a one-time audit. Classroom Token Hub employs a dual-layer automated PR gate:
1. **Structural Linter:** Blocks any code contributions that introduce heading outline breaks, duplicate DOM IDs, or missing form labels.
2. **Axe-Core Validation Engine:** Blocks any code contributions that introduce color contrast failures or ARIA state violations.

For inquiries regarding specific VPAT (Voluntary Product Accessibility Template) line items or to report an accessibility barrier, please consult the support channels provided in your school district's service agreement.
