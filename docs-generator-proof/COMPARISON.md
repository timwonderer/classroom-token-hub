# Hugo + Hextra versus the Zensical prototype

**Hugo + Hextra is a viable next migration candidate.** It reproduces the current
developer-doc corpus with native search and less custom browser
behavior than the existing Zensical prototype. Both artifacts pass the shared local contract gate on the ab56 migration corpus.
This remains a local proof, not deployment approval.

This proof was rebuilt October 23, 2026, in the `ab56` docs worktree on
`codex/docs-hugo-proof`, based at `9cbbb0a7f56318125beee8aae24d1c1578ade2ce`
**including its existing uncommitted migration changes**. Source file hashes in
`evidence/corpus.json` identify the evaluated corpus; the commit alone does not. It uses Hugo **0.168.0**, Hextra **0.13.0**,
FlexSearch **0.8.143**, and the existing prototype's Zensical **0.0.69**.
Zensical was rerun against today's corpus; it was not upgraded. No canonical
documents, user guides, application code or deployment workflows were edited.

## Measured comparison

| Check | Hugo + Hextra | Zensical prototype |
|---|---|---|
| Same canonical developer corpus | 146 documents | 146 documents |
| Generated HTML pages | 188, including native section navigation | 163 |
| Canonical routes, links and local assets | Pass shared artifact checks | Pass shared artifact checks |
| Canonical heading fragments | All 3,019 Zensical fragments retained | Reference set for this comparison |
| Canonical GitHub edit links | All 146 verified | All 146 verified |
| Publication boundary | No unexpected HTML pages or out-of-artifact search targets | Same |
| Content-search targets checked | 3,216 page/section entries | 3,052 entries |
| Search by `INV-CORE-000` | Correct document first, after configuration adjustment | Correct document first |
| Sampled WCAG 2.1 A/AA axe checks | 0 violations in 11 states | 0 violations in 11 states |
| Keyboard search, Escape, focus return; mobile menu | Pass | Pass |
| Horizontal overflow at 390px | None in sampled states | None in sampled states |
| Source heading structure | Pass — zero failures | Pass — zero failures |
| Runtime external requests during sampled navigation | None | Two GitHub API endpoints for repository metadata |

The 19 focused proof/prototype tests passed, including rejection of missing pages,
missing anchors/fonts, unexpected user-guide output, new working-state inputs,
and search targets outside the artifact. They run without application/database
fixtures. Raw results and source hashes are in [evidence/](evidence/).

Route/fragment evidence compares these two local artifacts. It is not a fresh
Docusaurus/live-site compatibility certification. The old prototype's Docusaurus
comparison remains historical. Extensionless URLs rely on directory-index
resolution; deployed GitHub Pages behavior was not tested.

## Branding and maintenance findings

The initial proof overstated brand preservation: token colors alone did not retain
the site's visual identity. Following user review, the **main public site**
(`github-pages/`) is the visual reference. Hugo now uses its stacked wordmark,
green-and-gold hero, warm content background, heading typography, blue content
links and dark footer. The homepage and catalog have full-width hero layouts;
contract pages retain their document sidebar and table of contents. A green
utility header adapts the brand to developer-document navigation.

The Hugo homepage groups existing destinations by reader task: understand the
system, make a change, and run/integrate. A separate ordered contract-reading
section preserves the authority hierarchy, with a prominent full-catalog link
and a small handoff to the in-app user guides. Canonical documents are unchanged.

The proof consumes `github-pages/style.css` byte-for-byte and generates its footer
from the existing public reference, `github-pages/learnmore.html`. Only relative
public links and the build-time year are adapted. Duplicate hero sizing and the
invented footer were removed. The earlier primary-checkout brand run passed 49 tests; this corrected-worktree
run passed the 19 proof/prototype tests and 22 browser states. The developer utility
header and document content layouts remain adaptations, not exact marketing-page
copies.

Hugo reuses the required `templates/macros/docs_hero.html` macro and self-hosts Inter, Atkinson
Hyperlegible Next and IBM Plex Mono. Desktop and mobile screenshots were inspected,
and computed background, heading weight, hero color and footer color checks pass
for the sampled pages. Zensical remains the existing prototype baseline; this pass
does not restyle it. These checks are not exhaustive visual parity or accessibility
certification.

Hextra was not completely compliant out of the box. The proof adds **17 lines of
custom UI JavaScript** for hidden-navigation focus and scrollable tables, plus
token mappings for search-match contrast. Its default 20-page search candidate
limit omitted the heavily cited core contract; raising that limit to 200 and
limiting sections to two put the intended document first in the tested query.
Broader search-quality testing and a corpus-growth decision remain necessary.

The existing Zensical prototype carries **119 lines** across custom search and
navigation JavaScript, plus its heading-ID extension. Hugo needs document/Markdown
template overrides and shared Python staging, so it is not a zero-customization
solution. Native Hextra search is the main maintenance advantage demonstrated here.

Hugo's inputs are a checksum-verified binary, a pinned theme archive, and a pinned
FlexSearch bundle. Normal builds avoid npm and runtime CDN fetches. Zensical uses
its existing hash-locked Python dependency graph. Both retain third-party code and
supply-chain obligations; this proof does **not** establish fewer vulnerabilities.
The shared evaluation environment includes Python validation packages and is not
a minimal production Hugo dependency manifest.

## Corrected worktree and remaining migration gates

The initial proof was mistakenly created in the primary checkout. It used that
checkout's newer corpus with ab56's generator implementation, omitting ab56's
uncommitted heading fixes and SOP amendment. Its seven source-heading failures
were valid for that input, but did not describe the migration worktree.

The proof and screenshots now live in ab56. Both generators use its same 146
documents, and all 3,019 compared canonical heading fragments are retained.
No source-heading, link, asset, publication-boundary or edit-link failures remain.
The corpus differs from the original 150-document snapshot because ab56 is based
on an older commit; this result does not establish parity with current main.

All 1,887 pre-existing tracked/untracked non-ignored file states were hashed before
the move and verified unchanged afterward, including existing deletions. The
migration changes remain uncommitted. No reset, stash, merge, or deployment occurred.

Before deployment, reconcile the worktree's generator-independent SOP amendment
and source changes with current main, add the Hugo Linux/CI build path and
dependency-maintenance policy, compare with a fresh Docusaurus artifact, and
complete broader rendered/assistive-technology review.

**Recommendation:** prefer Hugo + Hextra for the next migration proposal, subject
to those gates. Retain the Zensical prototype as the comparison baseline until
the migration decision is reviewed. Nothing was deployed, committed or pushed.
