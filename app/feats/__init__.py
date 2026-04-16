"""
app/feats – Feature Transaction Objects (FEATs).

Each FEAT encapsulates exactly one full mutation flow:

  route → FEAT → services (ledger_service, attendance_service, …)

Rules for FEATs
───────────────
• A FEAT owns its db.session.commit() call (exactly one, at the end).
• All financial writes (Transaction rows) go through ledger_service.
• The FEAT accepts pre-validated domain inputs; it does NOT re-read
  form data or make HTTP-layer decisions.
• The FEAT returns a dataclass result object so the calling route can
  build a response without re-querying the database.
"""
