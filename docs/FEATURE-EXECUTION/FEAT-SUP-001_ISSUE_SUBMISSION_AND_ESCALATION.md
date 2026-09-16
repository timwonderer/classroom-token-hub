# FEAT-SUP-001 — Issue Submission and Escalation

Authority: INV-CORE-000, INV-ARC-005, INV-ARC-018, INV-ARC-019,
DOM-SUP-001 §X. Effective 2026-09-15.

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
are canonical seat public IDs with database deletion cascades, including teacher-submitted tickets. Seat/account deletion removes the corresponding issue,
pack, history, and resolution rows rather than retaining a detached snapshot.
