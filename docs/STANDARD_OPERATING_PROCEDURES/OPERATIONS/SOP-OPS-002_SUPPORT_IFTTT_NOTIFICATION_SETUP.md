# SOP-OPS-002: Support IFTTT Notification Setup

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-OPS-002 | 1.0 | 2026-10-04 | Unnumbered Support IFTTT setup guide | Normative |

## I. Purpose

Define the operator procedure for configuring and validating lightweight IFTTT email notifications for qualifying Classroom Token Hub support filings.

## II. Scope

This procedure governs IFTTT applet setup, application environment configuration, delivery validation, and notification troubleshooting. It applies to direct teacher tickets and teacher escalation of student tickets.

## III. Authority Level

Normative (Tier 2). Subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-000`, `INV-ARC-005`, `DOM-SUP-001` §XI, and `FEAT-SUP-001` v1.1.

The OPERATIONS placement assigns the setup procedure to operators. Support retains authority over ticket state, qualifying actions, and the external payload allow-list. This procedure creates no additional runtime authority or notification-state records.

## IV. Dependencies

- [INV-CORE-000 — Core Invariants](../../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)
- [INV-CORE-001 — Capability-Based Architecture and Authority Model](../../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)
- [INV-ARC-000 — Execution Model](../../INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md)
- [INV-ARC-005 — No PII Leakage in Execution Layer](../../INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md)
- [DOM-SUP-001 — Support Domain](../../DOMAIN/DOM-SUP-001_SUPPORT_DOMAIN.md), §XI
- [FEAT-SUP-001 — Issue Submission and Escalation](../../FEATURE-EXECUTION/FEAT-SUP-001_ISSUE_SUBMISSION_AND_ESCALATION.md), v1.1
- [SOP-DOC-000 — Documentation Standard](../SOP-DOC-000_DOCUMENTATION_STANDARD.md)
- [SOP-DEP-002 — Production Transition Runbook](../DEPLOYMENT/SOP-DEP-002_Production_Transition_Runbook.md)

## V. IFTTT Applet and Application Configuration

1. Create an IFTTT applet with Webhooks **Receive a web request** (the trigger
   with three values). Set the event name to `cth_support_issue`.
2. Choose your email action and configure its recipient in IFTTT.
3. Suggested subject: `CTH support: {{Value1}}`.
4. Suggested body:

   ```text
   {{Value1}}
   UTC time: {{Value3}}
   Ticket reference: {{Value2}}
   Open: https://YOUR_APP_ORIGIN/sysadmin/issues/{{Value2}}
   ```

   Replace `YOUR_APP_ORIGIN` with the application hostname. The link still
   requires Cloudflare Access and normal operator authentication/visibility.
5. Obtain the Webhooks key from IFTTT's Webhooks documentation page. Configure
   `SUPPORT_IFTTT_EVENT=cth_support_issue` and `SUPPORT_IFTTT_KEY` in the app server's
   secret environment, then restart through the approved deployment process.
   Keep the key out of source control and command/log output.

Both variables unset disables notifications. Partial configuration records a
configuration failure when a ticket action commits. The destination is fixed
to `https://maker.ifttt.com/trigger/{event}/with/key/{key}`; the implementation
does not accept an arbitrary destination URL.

## VI. Qualifying Actions and Payload Values

| IFTTT ingredient | Meaning |
|------------------|---------|
| `Value1` | Fixed label identifying a teacher filing or teacher escalation of a student issue. |
| `Value2` | Encrypted opaque issue reference, used in the authenticated ticket link. |
| `Value3` | UTC notification event timestamp in ISO format. |

Teacher filing sends **New teacher support ticket**. Teacher escalation of an
existing student issue sends **Student support ticket escalated by teacher**.
Student filing alone sends nothing. Escalating an existing teacher ticket does
not send another filing notification. Refused actions, rolled-back transactions,
operator reads, and other transitions send nothing.

Only the three allow-listed values leave CTH. Do not add names, participant or
class identifiers, report titles, free text, page URLs, IP or browser details,
diagnostics, permissions, correlation packs, or economic records. In-app
disclosure permissions do not expand the external payload.

## VII. Delivery Outcomes and Troubleshooting

The app makes one post-commit HTTPS attempt with a three-second socket timeout.
It logs `support_notification_delivered` for IFTTT acceptance, or
`support_notification_delivery_failed` with a fixed reason and optional HTTP
status. Acceptance is not proof of email delivery. There is no retry or durable
queue; the committed ticket remains available in the support dashboard.

If an email is missing, check that both environment settings are present and the
application restarted with them, then check the bounded delivery outcome. For a
configuration failure, correct the event/key configuration. For transport or HTTP
failure, check outbound HTTPS connectivity and the IFTTT applet configuration.
If IFTTT accepted the request, inspect the applet's email action and recipient.
Never print the key, full webhook URL, request payload, response body, or exception
text during diagnosis. Notification logs must not attach participant, class, or
request context. To disable notifications, unset both environment settings and
restart through the approved deployment process.

## VIII. Validation Procedure

Validate in an authorized environment by filing a synthetic teacher ticket,
then filing a synthetic student ticket and escalating it as its owning teacher.
Confirm no email for student filing, one email for each qualifying action, and
that links open the corresponding tickets after authentication. Local tests mock
IFTTT; they do not send email or verify production configuration.

Record the validation environment, tested revision, qualifying action outcomes,
and observed email/link results in a separate operational record. Keep this SOP
as the reusable procedure; do not fill it with one deployment's results.

Protocol reference: [IFTTT Webhooks service FAQ](https://help.ifttt.com/hc/en-us/articles/115010230347-Webhooks-service-FAQ).

## IX. Amendment

Revisions must increment the version, update the Effective Date and Supersedes
fields, and register the revision in `SOP-DOC-001`. Changes must preserve the
governing invariants and `DOM-SUP-001` / `FEAT-SUP-001` boundaries. A change to
qualifying actions, payload contents, or delivery semantics requires amendment
of the governing Support contracts before this procedure is revised to use it.
