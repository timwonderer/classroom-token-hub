#!/usr/bin/env python3
"""Validate cross-domain reference and coordination direction (INV-ARC-021).

Two static questions, both answerable without running the application:

1. **Coordination direction** (§V.2, §V.6). The FEAT layer is the sole
   coordination layer. A domain service that imports a FEAT has moved the
   composition root inside a domain, which §V.6 forbids by name ("no ... domain
   service may perform multi-domain capability composition"). A service or FEAT
   that imports a route has inverted the execution layering outright.

2. **Cross-domain foreign keys** (§V.7). "The only legal cross-domain foreign
   key targets are shared anchor columns: `class_id`, `seat_id`, and `user_id`."
   Table ownership is read from the canonical schema definition, DOM-CORE-002
   §V, under its §IV.2 rule that each table has exactly one owning domain.

Both checks carry an enumerated baseline of violations that predate the gate.
A new violation fails the build; so does a baseline entry that no longer
reproduces, because a stale exemption is indistinguishable from a gate that
never asked the question.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "app" / "models.py"

# Authority: DOM-CORE-002 §V (Canonical Domain Tables), under §IV.2 "each table
# has exactly one owning domain". Companion specs collapse into their parent
# domain as listed in DOM-CORE-001 §IV: the DOM-IDEN-00x identity specs are one
# domain, and DOM-CLASS-003 Economic Policy is Class Configuration's versioning
# surface rather than an eleventh domain.
TABLE_DOMAIN = {
    # DOM-IDEN-001 / -003 — identity, class binding, recovery, authentication
    "users": "DOM-IDEN",
    "seats": "DOM-IDEN",
    "classes": "DOM-IDEN",
    "identity_profiles": "DOM-IDEN",
    "recovery_requests": "DOM-IDEN",
    "student_recovery_codes": "DOM-IDEN",
    "passkey_credentials": "DOM-IDEN",
    # DOM-CLASS-001 / -003 — class directives and their version lifecycle
    "class_features": "DOM-CLASS",
    "economic_engine": "DOM-CLASS",
    "policy_versions": "DOM-CLASS",
    "policy_transitions": "DOM-CLASS",
    # DOM-PROD-001 — productivity and payroll facts
    "attendance_sessions": "DOM-PROD",
    "hall_pass_logs": "DOM-PROD",
    "payroll_event": "DOM-PROD",
    # DOM-OBL-001 — seat-scoped debt lifecycle
    "bill_cycles": "DOM-OBL",
    "assessment_events": "DOM-OBL",
    "obligation_satisfaction": "DOM-OBL",
    # DOM-LED-001 — monetary truth
    "ledger_transaction": "DOM-LED",
    "ledger_balance_snapshot": "DOM-LED",
    # DOM-STORE-001 — entitlement grant and exercise lineage
    "entitlement_events": "DOM-STORE",
    "pending_actions": "DOM-STORE",
    # DOM-OPS-001 — operational truth and audit trace
    "operational_events": "DOM-OPS",
    "audit_events": "DOM-OPS",
    "chain_heads": "DOM-OPS",
    "incident_events": "DOM-OPS",
    "incident_summary": "DOM-OPS",
    "alert_events": "DOM-OPS",
    "invariant_run_events": "DOM-OPS",
    "job_events": "DOM-OPS",
    "health_check_events": "DOM-OPS",
    # DOM-ITR-001 — cycle interpretation
    "interpretation_cycle_record": "DOM-ITR",
    # DOM-SUP-001 — issue lifecycle and communication
    "issues": "DOM-SUP",
    "issue_status_history": "DOM-SUP",
    "issue_resolution_actions": "DOM-SUP",
    "ticket_correlation_pack": "DOM-SUP",
    "announcements": "DOM-SUP",
    "issue_categories": "DOM-SUP",
    # DOM-POL-001 — append-only policy definition repository
    "rent_settings": "DOM-POL",
    "payroll_settings": "DOM-POL",
    "payroll_rewards": "DOM-POL",
    "payroll_fines": "DOM-POL",
    "hall_pass_settings": "DOM-POL",
    "store_items": "DOM-POL",
    "store_item_visibility": "DOM-POL",
}

# INV-ARC-021 §V.7 enumerates these and only these as legal cross-domain
# foreign key targets.
SHARED_ANCHORS = {"classes.class_id", "seats.id", "users.id"}

# `app.feats.base` is the execution harness — FEATContext, correlation ids,
# audit protection — not a coordination unit. A service importing it is
# participating in the caller's FEAT transaction, which is how §V.2 expects
# domain work to be enlisted. Any other `app.feats.*` module is a coordination
# unit and a service must not reach into one.
FEAT_HARNESS_MODULES = {"app.feats.base"}

# Violations that predate this gate. Each is real and unremediated; the entries
# exist so the gate can fail on *new* coupling instead of staying permanently
# red on inherited debt. Removing a violation requires deleting its line here.
BASELINE_COORDINATION = {
    "app/services/ledger_fee_service.py imports app.feats.ledger_resolution_feat",
    "app/services/payroll/settlement.py imports app.feats.prod",
}
BASELINE_FOREIGN_KEYS = {
    "assessment_events.ledger_transaction_id -> ledger_transaction.id (DOM-OBL -> DOM-LED)",
    "assessment_events.policy_version_id -> policy_versions.id (DOM-OBL -> DOM-CLASS)",
    "issues.related_transaction_id -> ledger_transaction.id (DOM-SUP -> DOM-LED)",
    "issue_resolution_actions.related_transaction_id -> ledger_transaction.id (DOM-SUP -> DOM-LED)",
    "ledger_transaction.lineage_event_id -> audit_events.id (DOM-LED -> DOM-OPS)",
    "payroll_event.policy_version_id -> policy_versions.id (DOM-PROD -> DOM-CLASS)",
    # Tables with no attribution in DOM-CORE-002 §V. Ownership cannot be judged
    # until the schema definition is amended to name their owning domain.
    "insurance_claim_productivity_dates.claim_id -> insurance_claims.claim_id: "
    "insurance_claim_productivity_dates has no domain attribution in DOM-CORE-002 §V",
    "insurance_claim_productivity_dates.claim_id -> insurance_claims.claim_id: "
    "insurance_claims has no domain attribution in DOM-CORE-002 §V",
    "ledger_transaction.command_reservation_id -> ledger_command_reservation.id: "
    "ledger_command_reservation has no domain attribution in DOM-CORE-002 §V",
}


def _resolve_import(node: ast.ImportFrom | ast.Import, module_parts: list[str]) -> list[str]:
    """Absolute dotted names a single import statement binds to."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level:
        # `from ..feats.base import x` inside app/services/payroll/settlement.py
        # resolves against the *package*, so one level is already consumed.
        package = module_parts[: len(module_parts) - node.level]
        prefix = package + (node.module.split(".") if node.module else [])
    else:
        prefix = node.module.split(".") if node.module else []
    return [".".join(prefix)] if prefix else []


def _layer(relative: Path) -> str | None:
    parts = relative.parts
    if len(parts) < 2 or parts[0] != "app":
        return None
    return {"routes": "route", "feats": "feat", "services": "service"}.get(parts[1])


def _imported_layer(module: str) -> str | None:
    return {"app.routes": "route", "app.feats": "feat", "app.services": "service"}.get(
        ".".join(module.split(".")[:2])
    )


def coordination_findings(root: Path = ROOT) -> list[str]:
    """Imports that move coordination out of the FEAT layer (§V.2, §V.6)."""
    findings: list[str] = []
    for path in sorted((root / "app").rglob("*.py")):
        relative = path.relative_to(root)
        layer = _layer(relative)
        if layer is None:
            continue
        module_parts = list(relative.with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for module in _resolve_import(node, module_parts):
                target = _imported_layer(module)
                if target == "route" and layer in {"service", "feat"}:
                    findings.append(f"{relative.as_posix()} imports {module}")
                elif target == "feat" and layer == "service" and module not in FEAT_HARNESS_MODULES:
                    findings.append(f"{relative.as_posix()} imports {module}")
    return sorted(set(findings))


def _string_arg(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def foreign_key_edges(path: Path = MODEL_PATH) -> list[tuple[str, str, str]]:
    """Every declared foreign key as ``(table, column, target)``.

    Covers both the inline ``db.ForeignKey('classes.class_id')`` form and the
    composite ``db.ForeignKeyConstraint([...], [...])`` form used in
    ``__table_args__``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    edges: list[tuple[str, str, str]] = []
    for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        table = None
        for statement in cls.body:
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "__tablename__"
            ):
                table = _string_arg(statement.value)
        if table is None:
            continue
        for statement in cls.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target_node = statement.targets[0]
            column = target_node.id if isinstance(target_node, ast.Name) else None
            for call in (n for n in ast.walk(statement) if isinstance(n, ast.Call)):
                name = _call_name(call)
                if name == "ForeignKey" and call.args:
                    reference = _string_arg(call.args[0])
                    if reference:
                        edges.append((table, column or reference.split(".")[-1], reference))
                elif name == "ForeignKeyConstraint" and len(call.args) >= 2:
                    locals_ = call.args[0]
                    remotes = call.args[1]
                    if isinstance(locals_, (ast.List, ast.Tuple)) and isinstance(remotes, (ast.List, ast.Tuple)):
                        for local, remote in zip(locals_.elts, remotes.elts):
                            local_name = _string_arg(local)
                            reference = _string_arg(remote)
                            if local_name and reference:
                                edges.append((table, local_name, reference))
    return sorted(set(edges))


def foreign_key_findings(path: Path = MODEL_PATH) -> list[str]:
    """Foreign keys that cross a domain boundary outside the shared anchors (§V.7)."""
    findings: list[str] = []
    for table, column, reference in foreign_key_edges(path):
        if reference in SHARED_ANCHORS:
            continue
        referenced_table = reference.split(".")[0]
        if referenced_table == table:
            continue
        edge = f"{table}.{column} -> {reference}"
        unattributed = [
            name for name in (table, referenced_table) if name not in TABLE_DOMAIN
        ]
        if unattributed:
            findings.extend(
                f"{edge}: {name} has no domain attribution in DOM-CORE-002 §V"
                for name in unattributed
            )
            continue
        source, destination = TABLE_DOMAIN[table], TABLE_DOMAIN[referenced_table]
        if source != destination:
            findings.append(f"{edge} ({source} -> {destination})")
    return sorted(set(findings))


def evaluate(root: Path = ROOT, models: Path | None = None) -> dict[str, list[str]]:
    """Compare observed violations against the enumerated baseline."""
    observed = {
        "coordination": coordination_findings(root),
        "foreign_key": foreign_key_findings(models or (root / "app" / "models.py")),
    }
    baselines = {"coordination": BASELINE_COORDINATION, "foreign_key": BASELINE_FOREIGN_KEYS}
    introduced: list[str] = []
    resolved: list[str] = []
    for kind, findings in observed.items():
        baseline = baselines[kind]
        introduced.extend(finding for finding in findings if finding not in baseline)
        resolved.extend(entry for entry in sorted(baseline) if entry not in findings)
    return {"introduced": sorted(introduced), "resolved": resolved}


def main() -> int:
    result = evaluate()
    if result["introduced"]:
        print("INV-ARC-021 cross-domain violations introduced:")
        print("\n".join(f"  - {finding}" for finding in result["introduced"]))
    if result["resolved"]:
        print("Baseline entries no longer reproduce and must be deleted from")
        print("scripts/validate-cross-domain.py so the gate keeps asking the question:")
        print("\n".join(f"  - {finding}" for finding in result["resolved"]))
    if result["introduced"] or result["resolved"]:
        return 1
    print(
        "Cross-domain coordination and foreign key direction match the declared baseline "
        f"({len(BASELINE_COORDINATION)} coordination, {len(BASELINE_FOREIGN_KEYS)} foreign key)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
