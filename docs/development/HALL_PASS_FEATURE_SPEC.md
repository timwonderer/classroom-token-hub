# Hall Pass Feature Specification

Status: Active (Normative)
Last Updated: 2026-02-24
Owner: Platform / Identity & Classroom Flows

## 1. Purpose

Define the full hall pass feature contract across student, teacher, and public verification flows.
This spec is the source of truth for lifecycle states, API behavior, data invariants, and deprecation policy.

## 2. Scope

In scope:
- Student hall pass request, cancel, checkout, and checkin flows.
- Teacher approval/rejection and active pass management.
- Public office verification URL flow.
- Hall pass settings (enabled state, pass types, queue/simultaneous limits).
- Attendance side effects (tap-out/tap-in).

Out of scope:
- Broader attendance policy semantics unrelated to hall pass events.
- Store/rent economics except where hall pass balance is consumed.

## 3. Canonical Data Model

Primary table: `hall_pass_logs`
- `student_id` (required)
- `reason` (destination/pass type)
- `status` in: `pending`, `approved`, `rejected`, `left`, `returned`
- `pass_number` legacy nullable field (deprecated, no longer generated or displayed)
- `period` optional class period snapshot
- `join_code` class isolation key (authoritative scope)
- `request_time`, `decision_time`, `left_time`, `return_time`

Settings table: `hall_pass_settings`
- Teacher-scoped by `teacher_id`, with `block=None` as global default.
- `queue_enabled` boolean.
- `queue_limit` global numeric limit.
- `pass_types` JSON per destination:
  - `name`
  - `enabled`
  - `queue_limit` (nullable)
  - `simultaneous_limit` (nullable)

Teacher public verification token:
- `admins.hall_pass_verify_token` (rotatable, random capability token).
- Exposed as `/verify/hallpass/<token>`.

## 4. Lifecycle State Machine

Allowed transitions:
1. `pending` -> `approved`
2. `pending` -> `rejected` (teacher reject or student cancel)
3. `approved` -> `left` (student checkout or teacher/manual action)
4. `left` -> `returned` (student checkin or auto-return on start-work)
5. `left` -> `done for the day` (student forgot to checkin and time elapsed since initial start work is larger than set limit if there is one)

Forbidden transitions:
- Any transition from `rejected` to active states.
- `pending` -> `left` without teacher approval.
- `approved` -> `returned` without `left`.

## 5. Primary User Flow (Required)

Primary flow:
1. Student initiates request (creates `pending` record).
2. Teacher approves or rejects.
3. Student checks out (`approved` -> `left`).
4. Student checks in (`left` -> `returned`).

Deprecated compatibility flow:
- Terminal and queue endpoints are removed from active use and must return `410 Gone`.

## 6. Behavior Rules

Request-time gating:
- Request must be scoped to current class context (`join_code`).
- Pass type must be enabled (or request denied).
- Queue limits and destination limits must be enforced when configured.
- For reasons other than `office`, `summons`, `done for the day`, student must have pass balance.

Approval-time behavior:
- On approve, hall pass balance is decremented when deduction applies.
- `rent_hall_passes` consumption is prioritized before purchased passes.

Checkout/checkin side effects:
- Checkout creates `TapEvent(status='inactive')`.
- Checkin creates `TapEvent(status='active')`.
- Start-work flow auto-returns any active (`left`) pass in the same class context.

## 7. Public Verification Contract

Endpoint: `GET/POST /verify/hallpass/<teacher_public_token>`

Requirements:
- Token must be non-enumerable and rotatable.
- No roster listing.
- No multi-day history exposure.
- Query scope must be limited to selected teacher class (`join_code`) and current school day window.
- Match result must support:
  - no match
  - ambiguous match
  - single match with minimal details (student display, class label, destination, status, timestamps)

Rate limiting:
- Public verification route must be rate-limited.

## 8. Public Verification Portal — Claim-Based Model

Design principle:
- Does not display lists.
- Does not display historical multi-day data.
- Does not expose roster.
- Only reveals information in response to a specific student claim.

Endpoint:
- `/verify/hallpass/<teacher_public_token>`

Input:
- Class (teacher-defined label mapped internally to `join_code`)
- Student first name
- Student last initial

Scope constraints:
- `teacher_public_token` must match.
- `join_code` must belong to teacher.
- Date scope must be current school date (school timezone).
- Match detection must stop after 2 matches to distinguish unique vs ambiguous.

Output rules:
- `0` matches: `No hall pass record found for today.`
- `1` match: display minimal operational details only.
- `>1` matches: `Unable to uniquely verify. Please contact the teacher.`

Non-goals:
- No public list view.
- No multi-day history.
- No audit display.
- No roster enumeration.

## 9. API Surface (Current Contract)

Teacher actions:
- `POST /api/hall-pass/<pass_id>/approve`
- `POST /api/hall-pass/<pass_id>/reject`
- `POST /api/hall-pass/<pass_id>/leave` (legacy/manual path)
- `POST /api/hall-pass/<pass_id>/return` (legacy/manual path)

Student actions:
- `POST /api/hall-pass/cancel/<pass_id>`
- `POST /api/hall-pass/checkout`
- `POST /api/hall-pass/checkin`

Settings:
- `GET/POST /api/hall-pass/settings`
- `GET/POST /api/hall-pass/setup`
- `POST /api/hall-pass/verify-token/rotate`
- `GET /api/hall-pass/available-types`

Read endpoints:
- `GET /api/hall-pass/history`

Deprecated endpoints (must return `410 Gone`):
- `GET /hall-pass/terminal`
- `GET /hall-pass/queue`
- `GET /api/hall-pass/queue`
- `GET /api/hall-pass/lookup/<pass_number>`
- `POST /api/hall-pass/terminal/use`
- `POST /api/hall-pass/terminal/return`

## 10. Security and Privacy Requirements

- All hall pass operations must remain tenant-scoped by class context (`join_code`) and role auth.
- Public verify endpoint must use capability token, never teacher username or internal numeric IDs.
- Verification outputs must avoid exposing non-essential PII or roster-level data.

## 11. Observability and Audit

Minimum events to log:
- Request create, approve, reject, checkout, checkin, cancel.
- Verify-token rotation.
- Rate-limit or policy denials (queue/simultaneous/type disabled).

All timestamps are UTC at rest and converted at read time for user display.

## 12. Acceptance Criteria

Functional:
- Student can complete request -> approve -> checkout -> checkin without terminal dependencies.
- Terminal and queue routes are disabled (`410 Gone`) in all environments.
- Teacher approval is mandatory before checkout.
- Queue/simultaneous limits enforce correctly per destination and day.
- Public verification resolves valid current-day pass state correctly.

Security:
- Invalid or rotated verification token cannot access teacher verification view.
- Cross-teacher/cross-class requests are denied.
- Non-owner student cannot checkout/checkin another student's pass.

Data integrity:
- Status transitions follow the allowed state machine only.
- Tap events are generated exactly once per checkout/checkin.
