"""FEAT-CLASS-005: compose the class-owned economic evolution command."""
from app.feats.base import requires_feat_context
from app.services.context_resolver import CanonicalContext
from app.services.economic_configuration_commands import (
    EconomicEngineEvolutionResult, EconomicEngineEvolutionError, evolve_economic_engine,
)

def execute_evolve_economic_engine(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    updates: dict,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """
    Execute lawful teacher-directed EconomicEngine field evolution.

    Creates a new immutable EconomicEngine version with the requested field updates
    applied on top of the current engine's values, and links the specified features
    to the new version via class_features rows.

    Args:
        canonical_context: CanonicalContext with user_id, class_id, seat_id, actor_role="teacher"
        class_id: Class to modify
        updates: Dict of EconomicEngine field name → new value. Fields not present
                 are carried forward from the current engine. Whitelist enforced.
                 Supported keys:
                     economy_policy_mode, expected_weekly_hours, interest_rate,
                     interest_calculation_type, compound_frequency,
                     interest_accrual_frequency, interest_payout_frequency,
                     flat_overdraft_fee, progressive_overdraft_fee,
                     overdraft_protection_enabled
        feature_list: List of features affected by this transition (e.g., ['payroll', 'rent'])
        effective_at: When this transition takes effect (default: canonical_now, ISO 8601 string)
        correlation_id: Optional; generated if not provided
        idempotency_key: Optional replay guard

    Returns:
        EconomicEngineEvolutionResult with success status and engine details.
    """
    return _execute_evolve_economic_engine_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        updates=updates,
        feature_list=feature_list,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


def execute_transition_economic_policy(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    new_policy_mode: str,
    feature_list: list[str],
    effective_at: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> EconomicEngineEvolutionResult:
    """Backward-compat wrapper: policy-mode-only transition.

    Prefer `execute_evolve_economic_engine(updates={...})` for new callers.
    """
    return _execute_evolve_economic_engine_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        updates={'economy_policy_mode': new_policy_mode},
        feature_list=feature_list,
        effective_at=effective_at,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-CLASS-005")
def _execute_evolve_economic_engine_impl(**kwargs):
    return evolve_economic_engine(**kwargs)
