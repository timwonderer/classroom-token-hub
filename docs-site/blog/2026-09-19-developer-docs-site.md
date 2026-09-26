---
title: The developer docs site now publishes the real documentation tree
date: 2026-09-19
---

The docs site stopped being a placeholder. It now builds straight out of
`docs/` and publishes the documentation that actually governs the system:
`INV-CORE` and `INV-ARC` invariants, `DOM-*` domain authority specs, `FEAT-*`
execution contracts, `SPEC-*`, `SOP-*`, the interface maps, vocabulary
references, principles, operational notes, and tracking.

{/* truncate */}

## One document, one renderer

Content is read from `../docs` rather than copied into this workspace. A
normative document has one home in the repository and one rendered version on
the web, so the two cannot drift apart.

The split with the application is now explicit on both sides:

- `classroomtokenhub.com/docs/` — developer documentation, published from this
  workspace to GitHub Pages alongside the marketing pages.
- `app.classroomtokenhub.com/docs/` — the teacher and student help centre,
  rendered by Flask so readers keep their session and the context of the page
  they came from.

Nothing appears in both places.

## Deep links survive the hand-off

`route-map.json` used to be the list of paths that had been migrated; anything
unmapped landed on the site root. Now that the site publishes the tree at its
repository-relative paths, an unmapped developer-facing request forwards
unchanged, and the map carries only the handful of documents whose path changed
on the way over — the retired `ARC-*` namespace, mostly.

## Broken links fail the build

The build runs with `onBrokenLinks`, `onBrokenAnchors`, and
`onBrokenMarkdownLinks` all set to throw. Renaming or deleting a document under
`docs/` without fixing what points at it now fails the Pages build instead of
shipping a dead link.
