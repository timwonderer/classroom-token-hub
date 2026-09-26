# FEAT-SUP-002 — Class Announcement Management

Authority: INV-CORE-000, INV-ARC-005, INV-ARC-019, INV-ARC-021,
DOM-SUP-001 §V `announcements`. Effective 2026-09-17.

This FEAT is the only path that creates, edits, activates, deactivates or deletes
a teacher class announcement. Each request runs one FEAT transaction that commits
on success and rolls back as a whole on failure.

The class is the canonical class from the teacher's session, verified as owned by
that teacher before the FEAT begins. A class ID submitted in a form is not
authority. The acting teacher seat is resolved for that class. Every write
requires that seat to be a teacher seat in the announcement's own class:

- Create stores that seat as `created_by_seat_id` and the canonical class as
  `class_id`.
- Edit, toggle and delete load the announcement by ID and class together. An
  announcement in another class is not found, even for the same teacher.
  The write is refused if the acting seat does not teach the row's class.

Authentication principal IDs are never used to find, author or filter an
announcement. Toggling changes only `is_active` and `updated_at`. Expiry is a
display hint, so no write happens when an announcement expires. Announcements
change no other domain's state.
