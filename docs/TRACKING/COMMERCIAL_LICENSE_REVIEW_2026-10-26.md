# Commercial-services licensing review — 2026-10-26

**Status: proposed structure for qualified legal review; not a license or adopted terms.**

## Settled project intent

The owner requests automatic conditional permission for reasonable, profitable services around
CTH, without software monetization or individual approval. Contribution of commercial providers'
CTH fixes and general improvements upstream remains required in the intended policy. Independent
implementations and commercial competition are welcome. The philosophy is recorded in
[PRN-PHL-002](../PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-002_Classroom_Token_Hub_Open_Source_Philosophy.md).

## Recommended structure for review

Keep the standard repository `LICENSE` and its reproduced text unchanged. Propose a separate,
versioned **CTH Commercial Services License** from the rights holders, available automatically
on compliance with stated conditions. This would be an additional route for covered commercial
activities, not an assertion that PolyForm itself permits those activities. A public exception
could also implement the objective, but counsel must determine whether an exception or a separate
grant most clearly handles rights, conditions, and remedies.

The candidate instrument would explicitly identify covered releases and material, grant the
necessary rights to operate, copy, modify, and distribute for qualifying services, and attach
the no-software-monetization, attribution, and contribution-back conditions to that grant.
Customer rights and distribution notices need independent treatment; a provider must not be
assumed to sublicense rights it does not hold. Warranty, patent rights, acceptance, applicable
law, cure, and termination must be drafted expressly rather than inherited ambiguously.

PolyForm's “No Other Rights” provision does not prevent licensors from granting other licenses,
but does not prove that the maintainer controls every contribution's rights. Receiving a contribution under PolyForm permits use on those terms; that alone should not be
assumed to authorize relicensing for commercial services.
[PolyForm text](https://polyformproject.org/licenses/noncommercial/1.0.0).

Do not edit PolyForm into a custom license while retaining its name. The PolyForm project's
license-text reuse instructions require removing its name and site references when modifying
the license text. A separate CTH instrument avoids presenting custom clauses as standard PolyForm;
counsel should verify the final packaging and references.
[PolyForm reuse instructions](https://github.com/polyformproject/polyform-licenses/blob/1.0.0/README.md).

## Decisions and legal questions before activation

| Area | Proposed treatment for review | What remains unresolved |
|---|---|---|
| Authority | Grant only rights controlled by participating rights holders | Audit contributions, employment ownership, and third-party code; obtain needed consents. Do not assume sole ownership from the copyright notice. |
| Eligibility | Automatic permission for qualifying service providers | Define provider, affiliates, subcontractors, eligible customers and covered purposes; whether service to noneducational organizations is included. |
| Service economics | Reasonable profit for actual services; no software entitlements | Define objective evidence of a service fee and reasonableness without discretionary approval; address pooled infrastructure, usage meters and account-based proxies. |
| Continuity | Permit legitimate service billing without software lock-in | Specify nonpayment suspension, termination, export, handover, and self-hosting rights; distinguish infrastructure availability from software licensing. |
| Covered functionality | No charge for standard features in the corresponding free release | Define corresponding release, resource limits, legitimate configuration choices, and treatment of provider-developed extensions. |
| Contribution scope | Cover CTH bug fixes, security fixes and general improvements made in covered commercial activity | Define modifications and general improvements, treatment of affiliates, forks, extensions, integrations, and pre-existing changes; exclude independent software and confidential operational data. |
| Submission | Offer usable source, relevant tests/docs and adequate upstream licensing rights | Define the submission channel, acceptable materials, and fallback if upstream is unavailable. Upstream rejection must not put compliance outside the provider's control. |
| Timing | Tie submission to first commercial deployment or distribution | Choose an explicit deadline; none is adopted here. Address internal testing, abandoned changes, and updates already deployed. |
| Security | Private reporting first, with coordinated disclosure | Define private-submission deadline, embargo and public-release trigger, plus a fallback if maintainers do not respond. Never require student data or credentials. |
| Contribution rights | Allow incorporation and redistribution in CTH, including its intended services model | Verify incoming rights support both licenses; choose contribution terms. Avoid accidental copyright assignment or relicense of incompatible third-party code. |
| Breach | Objective obligations, notice, proportionate cure and defined consequences | Decide condition versus covenant, enforcement standing, termination/reinstatement and customer continuity. Do not transplant PolyForm's cure provisions without deciding their application. |
| Versioning | Publish a stable version, covered releases, and effective date | Decide prospective scope and treatment of existing grants; do not imply retroactive amendment or unilateral revocation. |
| Prior policy | Preserve historical evidence while reconciling future documentation | Determine whether earlier wording granted rights or generated reliance; a new draft disclaimer cannot decide or erase that effect. |

## Contradictions and proposed companion corrections

These corrections are proposed, not applied, because the final grant is unresolved.

| Source | Existing problem | Proposed correction at legal finalization |
|---|---|---|
| `docs/user-guides/legal/commercial.md` before this draft | Services permission and contribution-back attributed to PolyForm; all policy violations described as PolyForm violations | Separate actual license terms from additional commercial grant and conditions; use the correct instrument's remedies. The working revision is explicitly a proposal. |
| `docs/user-guides/legal/license.md`, Quick Summary | Blanket bans on paid hosting and for-profit internal use conflict with services intent and oversimplify purpose-based licensing | Preserve reproduced license text; summarize its permitted-purpose clauses accurately and link separately to any effective commercial-services grant. |
| `docs/user-guides/legal/attribution.md`, Commercial Services and License Rationale | Says services are already permitted and PolyForm supplies that permission; asserts legal clarity/international recognition without substantiation | Attribute service rights to the adopted instrument, distinguish mission from legal effects, remove unsupported legal assurances. |
| `README.md`, License | Blanket prohibition on SaaS, paid services and other for-profit use conflicts with intended services permission | Describe the baseline and adopted additional permission separately, with links to each. |
| `docs/PRINCIPLES/PROJECT_PHILOSOPHY/PRN-PHL-001_Design_Principles_And_Project_History.md`, Educational Use Only | Heading may imply a narrower license scope than PolyForm's permitted purposes | Describe educational mission separately from legal scope and cross-reference PRN-PHL-002. |
| `.github/CONTRIBUTING.md`, License | States PolyForm only; does not establish authority for an additional commercial grant | Resolve contribution licensing and historical permissions before representing that all contributions support the new grant. |
| `github-pages/terms.html` and third-party notices | Baseline license references are not grants of the proposed services rights | Review publication references on activation; preserve third-party licenses and assess compatibility individually. |

No runtime implementation, DOM amendment, or FEAT contract is involved. Documentation placement
and informative status follow SOP-DOC-000 and INV-CORE-001. The PRN does not govern license rights.

## Completion gate

Qualified counsel should resolve the questions above and prepare the effective instrument.
The owner must then settle outstanding policy choices and authorize finalization. Reconcile
all public summaries in the same release, record the effective version, and verify links and
published rendering. These working drafts neither authorize deployment of new legal terms nor
claim an enforceable commercial permission is already established.
