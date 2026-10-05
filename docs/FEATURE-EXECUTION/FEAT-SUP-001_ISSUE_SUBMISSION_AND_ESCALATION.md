# FEAT-SUP-001 — Issue Submission and Escalation

Authority: INV-CORE-000, INV-ARC-005, INV-ARC-018, INV-ARC-019,
DOM-SUP-001 §X–XI. Version 1.1, supersedes 1.0. Effective 2026-10-04.

Student submissions capture immutable teacher-review context and the existing
correlation pack. A selected transaction must belong to the submitting seat and
class. Student input cannot grant system-support access to class data.

Escalation resolves the authenticated teacher's canonical class and verifies the
ticket belongs to it before writing anything. Each checkbox writes exactly its
own permission under `support_permissions`; unchecked or missing means false.
The separate class-name flag follows the same rule. Persist the permission set,
teacher public actor reference, escalation time, and status history atomically.
No checkbox authorizes live classroom reads or mutations by system support.

Operator payloads project the frozen snapshot through these permissions on every
read. Preserve technical context and the correlation pack; omit unapproved or
unknown class-data fields. Do not rely on template visibility as the access gate.
Direct teacher submission authorizes its written report, but does not implicitly
include class names or economic records.

Capture occurs once at submission. Escalation and operator views use saved values
without re-reading teacher/student seat data. Permission and workflow metadata
may change; captured context and correlation packs may not. Issue actor references
are canonical seat public IDs, including teacher-submitted tickets, with no foreign
key to `seats` (DOM-SUP-001 §X). Seat/account deletion deletes the corresponding
issues by public ID, and Support's own cascades remove the pack, history, and
resolution rows, rather than retaining a detached snapshot.

For direct teacher filing and teacher escalation of a student issue, freeze the
DOM-SUP-001 §XI allow-listed notification values in transaction-local memory
after the ticket command succeeds. Send one outbound POST only after the outer
FEAT transaction commits; discard values on rollback and defer through savepoint
release. Lock the class-scoped issue row before evaluating its escalation status
and hold that lock through commit, so concurrent requests cannot each accept the
same transition. Do not query classroom records during delivery or serialize an Issue
model. Use IFTTT's `Receive a web request` trigger with `value1` = fixed event
label, `value2` = encrypted opaque issue reference, `value3` = UTC event timestamp.
Delivery failures log only a bounded outcome and never escape into ticket success
handling. Student filing, refused actions, operator reads, and other transitions
do not schedule this notification. No schema change or delivery-state record is
authorized by this feature.
