"""
Economy Balance Checker - Centralized CWI Calculator and Balance Validator

This module implements the economic-calculation authority SPEC-ECON-003 for
the Classroom Economy App. It provides tools to:
- Calculate CWI (Classroom Wage Index) dynamically
- Validate economy settings against standard ratios
- Generate teacher recommendations for balanced configurations
- Warn when settings deviate from CWI guidelines

Reference: SPEC-ECON-003 (Economic Engine Calculation & Reference Specification).
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

from app.utils.economy_policy import (
    AVERAGE_WEEKS_PER_MONTH as _AVERAGE_WEEKS_PER_MONTH,
    frequency_label,
    get_active_policy_mode,
    get_active_policy_mode_for_class,
    get_policy_profile,
    get_price_recommendation_context,
    normalize_policy_mode,
    scale_band,
    STORE_ROLE_RATIOS,
    weeks_per_period,
)


class WarningLevel(Enum):
    """Severity levels for economy balance warnings"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EconomicRole(Enum):
    """Store economic roles per SPEC-ECON-003 §4.7.

    The teacher declares the role; the price is then reported against that
    role's reference band. The old pricing tiers ran the other way — they were
    inferred from the price — which meant a product had no stable role to be
    judged against across a price change.
    """
    NECESSITY = "necessity"        # 0.01-0.10 * CWI
    CONVENIENCE = "convenience"    # 0.11-0.20 * CWI
    ADD_ON = "add_on"              # 0.21-0.30 * CWI


@dataclass
class CWICalculation:
    """Result of CWI calculation with breakdown"""
    cwi: float                          # Weekly expected income
    pay_rate: float                     # Pay rate per unit
    time_unit: str                      # Unit type (seconds, minutes, hours, days)
    pay_rate_per_minute: float         # Normalized to per-minute
    expected_weekly_minutes: float     # Expected attendance per week
    payroll_frequency_days: int        # How often payroll runs
    notes: List[str]                   # Calculation notes


@dataclass
class BalanceWarning:
    """A warning about economy imbalance"""
    feature: str                # Feature name (e.g., "Rent", "Insurance Premium")
    level: WarningLevel         # Severity level
    message: str               # Human-readable warning
    current_value: Optional[float]     # Current setting
    recommended_min: Optional[float]   # Recommended minimum
    recommended_max: Optional[float]   # Recommended maximum
    cwi_ratio: Optional[float]         # Ratio relative to CWI


@dataclass
class EconomyBalance:
    """Complete economy balance analysis"""
    cwi: CWICalculation
    is_balanced: bool
    warnings: List[BalanceWarning]
    recommendations: Dict[str, Any]
    budget_survival_test_passed: bool
    weekly_savings: Optional[float]


class EconomyBalanceChecker:
    """
    Centralized tool for calculating CWI and validating economy balance.

    All monetary values in the Classroom Economy must scale from CWI per SPEC-ECON-003 §4.1 (CWI derivation) and §6.2 (Class-Relative Comparison).
    This class provides the single source of truth for:
    - CWI calculation
    - Ratio-based validation
    - Teacher recommendations
    - Balance warnings
    """

    # Rent, fine, collective-goal and savings ratios are NOT restated here. They
    # are read per-mode from POLICY_MODES, which transcribes the SPEC-ECON-003 §4
    # tables; a local fallback copy is a second spelling of the band and drifts
    # silently from the one the teacher is shown (INV-ARC-022).
    #
    # NOTE (SPEC-ECON-003 migration): insurance CWI-band and coverage/period-cap
    # multiplier constants were removed. Insurance economics are owned by the
    # Economic Engine (app/services/economic_engine.resolve_insurance).

    STORE_ROLE_BANDS = {
        role: (STORE_ROLE_RATIOS[role.value]["min"], STORE_ROLE_RATIOS[role.value]["max"])
        for role in EconomicRole
    }

    # Conversion helpers. The month length is the policy module's constant, not a
    # local restatement of it — two spellings produced two rent bands.
    AVERAGE_WEEKS_PER_MONTH = _AVERAGE_WEEKS_PER_MONTH

    # Conservative weekly store spending estimate
    ESTIMATED_WEEKLY_STORE_SPENDING_RATIO = 0.15

    # Thresholds for warnings
    MINOR_DEVIATION_THRESHOLD = 0.15  # 15% deviation = warning
    MAJOR_DEVIATION_THRESHOLD = 0.30  # 30% deviation = critical

    def __init__(
        self,
        user_id: int,
        policy_mode: Optional[str] = None,
        class_id: Optional[str] = None,
    ):
        """Initialize checker for a specific class owner.

        Args:
            user_id: The owning user ID
            policy_mode: Optional explicit policy mode (else resolved from class_id)
            class_id: The class scope for policy-mode resolution
        """
        self.user_id = user_id
        self.class_id = class_id
        resolved_mode_source = policy_mode
        if resolved_mode_source is None and class_id:
            resolved_mode_source = get_active_policy_mode_for_class(class_id)
        if resolved_mode_source is None:
            resolved_mode_source = get_active_policy_mode(user_id, class_id=class_id)
        resolved_mode = normalize_policy_mode(resolved_mode_source)
        self.policy_mode = resolved_mode
        self.policy_profile = get_policy_profile(resolved_mode)

    def _ratio_band(self, key: str) -> Tuple[float, float, float]:
        ratios = self.policy_profile["ratios"][key]
        return (
            float(ratios["min"]),
            float(ratios["max"]),
            float(ratios["recommended"]),
        )

    def _minimum_ratio(self, key: str) -> float:
        return float(self.policy_profile["ratios"][key]["min"])

    def rent_band(
        self,
        cwi: float,
        frequency_type: str,
        custom_frequency_value: Optional[float] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> Dict[str, Decimal]:
        """The rent band for a class, in the cadence the teacher sets rent on.

        This is the only place a rent recommendation is derived. The settings page
        and the balance warning both read it, so the number a teacher is shown is
        the number they are judged against (INV-ARC-022).
        """
        min_ratio, max_ratio, recommended_ratio = self._ratio_band("rent_weekly")
        return scale_band(
            cwi,
            {"min": min_ratio, "max": max_ratio, "recommended": recommended_ratio},
            weeks_per_period(
                frequency_type,
                custom_frequency_value=custom_frequency_value,
                custom_frequency_unit=custom_frequency_unit,
            ),
        )

    def fine_band(self, cwi: float) -> Dict[str, Decimal]:
        """The fine band for a class's policy mode, on the cent grid."""
        min_ratio, max_ratio, recommended_ratio = self._ratio_band("fine_weekly")
        return scale_band(
            cwi,
            {"min": min_ratio, "max": max_ratio, "recommended": recommended_ratio},
        )

    def store_role_bands(self, cwi: float) -> Dict[EconomicRole, Dict[str, Decimal]]:
        """Each economic role's reference price band, on the cent grid."""
        return {
            role: scale_band(cwi, {"min": bounds[0], "max": bounds[1]})
            for role, bounds in self.STORE_ROLE_BANDS.items()
        }

    def _weekly_insurance_premium(self, policy_version) -> Optional[float]:
        """Weekly premium of one offered insurance policy version, or None.

        A policy version carries its terms in its payload, not in columns. An
        inactive version is not offered, and a version with no usable premium is
        skipped rather than priced by guesswork.
        """
        import json

        if not getattr(policy_version, "is_active", False):
            return None
        try:
            payload = json.loads(getattr(policy_version, "policy_payload_json", None) or "{}")
            premium = Decimal(str(payload["premium"]))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            return None
        frequency = str(payload.get("charge_frequency") or "weekly").lower()
        return float(self._normalize_to_weekly(premium, frequency))

    def _normalize_to_weekly(
        self,
        value: Decimal,
        frequency: str,
        custom_frequency_value: Optional[Decimal] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> Decimal:
        """Normalize a value to its weekly equivalent based on frequency."""
        from app.models import _quantize_currency

        # Ensure value is Decimal for consistent arithmetic
        if not isinstance(value, Decimal):
            value = Decimal(str(value))

        if frequency == 'monthly':
            return _quantize_currency(value / Decimal(str(self.AVERAGE_WEEKS_PER_MONTH)))
        if frequency == 'weekly':
            return value
        if frequency == 'biweekly':
            return _quantize_currency(value / Decimal('2'))
        if frequency == 'daily':
            return _quantize_currency(value * Decimal('7'))
        if frequency == 'custom':
            # Default to days when unit is unspecified
            unit = (custom_frequency_unit or 'days').lower()
            freq_value = custom_frequency_value or Decimal('1')
            if unit == 'weeks':
                # Value is "per N weeks", so weekly equivalent is value / N
                return _quantize_currency(value / freq_value)
            if unit == 'months':
                return _quantize_currency(value / (Decimal(str(self.AVERAGE_WEEKS_PER_MONTH)) * freq_value))
            return _quantize_currency(value * (Decimal('7') / freq_value))

        return value

    def calculate_cwi(self, payroll_settings, expected_weekly_hours: float = None) -> CWICalculation | None:
        """
        Calculate CWI (Classroom Wage Index) - expected weekly income for perfect attendance.

        Args:
            payroll_settings: PayrollSettings model instance (source of pay_rate only)
            expected_weekly_hours: Expected hours of attendance per week.
                                   If None, reads from the EconomicEngine version governing
                                   the payroll feature for this class (authoritative source
                                   per DOM-CLASS-002).

        Returns:
            CWICalculation with breakdown, or None if `expected_weekly_hours` is
            unconfigured on both the parameter and the EconomicEngine. Callers must
            handle None (display "configure CWI on Economic Engine" warning; disable
            pricing recommendations).

        NOTE (SPEC-ECON-003 migration): the canonical CWI calculation authority is
        ``app/services/economic_engine.resolve_base`` (per SPEC-ECON-003 §3/§4.1).
        This is a pre-existing duplicate formula site retained during the
        conservative migration; it should be consolidated to consume ``resolve_base``
        once parity is proven for the balance-checker surface. Numerically identical
        today: ``pay_rate_per_minute × 60 × expected_weekly_hours``.
        """
        notes = []

        # Get expected weekly hours from EconomicEngine (canonical source) if not provided
        from app.models import _quantize_currency
        if expected_weekly_hours is None:
            try:
                from app.services.class_configuration_query_service import (
                    get_effective_economic_engine,
                )
                class_id = getattr(payroll_settings, 'class_id', None)
                if class_id:
                    engine = get_effective_economic_engine(class_id, 'payroll')
                    if engine and engine.expected_weekly_hours is not None:
                        expected_weekly_hours = _quantize_currency(engine.expected_weekly_hours)
                        notes.append(f"Using expected weekly hours from EconomicEngine: {expected_weekly_hours} hours")
            except Exception:
                logger.exception(
                    "Failed to resolve expected_weekly_hours from EconomicEngine for class_id=%s",
                    getattr(payroll_settings, 'class_id', None),
                )

            if expected_weekly_hours is None:
                # No configured value → CWI is undefined.
                return None
        else:
            expected_weekly_hours = _quantize_currency(expected_weekly_hours)
            notes.append(f"Using provided expected weekly hours: {expected_weekly_hours} hours")

        # Convert pay_rate to per-minute rate
        # Note: pay_rate is stored as per-minute in the database for storage efficiency
        pay_rate_per_minute = Decimal(str(payroll_settings.pay_rate))
        notes.append(f"Pay rate: ${pay_rate_per_minute:.4f} per minute (from database)")

        # Calculate expected weekly minutes
        expected_weekly_minutes = expected_weekly_hours * Decimal('60')
        notes.append(f"Expected weekly attendance: {expected_weekly_hours} hours = {expected_weekly_minutes} minutes")

        # Calculate weekly income
        cwi = _quantize_currency(expected_weekly_minutes * pay_rate_per_minute)
        notes.append(f"CWI = {expected_weekly_minutes} min × ${pay_rate_per_minute:.4f}/min = ${cwi:.2f}")

        return CWICalculation(
            cwi=float(cwi),  # Convert to float for JSON serialization
            pay_rate=float(payroll_settings.pay_rate),  # Convert to float for JSON serialization
            time_unit=payroll_settings.time_unit or "minutes",
            pay_rate_per_minute=float(pay_rate_per_minute),
            expected_weekly_minutes=float(expected_weekly_minutes),
            payroll_frequency_days=payroll_settings.payroll_frequency_days or 7,
            notes=notes
        )

    def check_rent_balance(self, rent_settings, cwi: float) -> List[BalanceWarning]:
        """
        Check if rent amount is balanced relative to CWI.

        Args:
            rent_settings: RentSettings model instance
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not rent_settings:
            return warnings

        from app.models import _quantize_currency
        custom_frequency_value = rent_settings.custom_frequency_value
        custom_frequency_unit = getattr(rent_settings, 'custom_frequency_unit', None)
        rent_amount = _quantize_currency(rent_settings.rent_amount)
        weekly_rent = self._normalize_to_weekly(
            rent_amount,
            rent_settings.frequency_type,
            custom_frequency_value,
            custom_frequency_unit,
        )

        # Judged in the cadence the teacher set it in, against the band the rent
        # page quotes. Converting to a monthly equivalent first added a rounding
        # step the page did not take, so a value copied off the page could be
        # reported as out of range.
        band = self.rent_band(
            cwi,
            rent_settings.frequency_type,
            custom_frequency_value,
            custom_frequency_unit,
        )
        recommended_min = band['min']
        recommended_max = band['max']
        label = frequency_label(
            rent_settings.frequency_type,
            custom_frequency_value=custom_frequency_value,
            custom_frequency_unit=custom_frequency_unit,
        )
        weekly_ratio = float(weekly_rent / Decimal(str(cwi))) if cwi > 0 else 0

        if rent_amount < recommended_min:
            deviation = float((recommended_min - rent_amount) / recommended_min) if recommended_min else 0
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Rent (${rent_amount:.2f} {label}) is below the recommended minimum of ${recommended_min:.2f}. Students may not learn proper budgeting.",
                current_value=float(rent_amount),
                recommended_min=float(recommended_min),
                recommended_max=float(recommended_max),
                cwi_ratio=weekly_ratio
            ))
        elif rent_amount > recommended_max:
            deviation = float((rent_amount - recommended_max) / recommended_max) if recommended_max else 0
            level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
            warnings.append(BalanceWarning(
                feature="Rent",
                level=level,
                message=f"Rent (${rent_amount:.2f} {label}) is above the recommended maximum of ${recommended_max:.2f}. Students may struggle with other expenses.",
                current_value=float(rent_amount),
                recommended_min=float(recommended_min),
                recommended_max=float(recommended_max),
                cwi_ratio=weekly_ratio
            ))
        else:
            # Within bounds - provide info
            warnings.append(BalanceWarning(
                feature="Rent",
                level=WarningLevel.INFO,
                message=f"Rent is balanced at ${rent_amount:.2f} {label} (${weekly_rent:.2f} per week, {weekly_ratio:.2f}x CWI)",
                current_value=float(rent_amount),
                recommended_min=float(recommended_min),
                recommended_max=float(recommended_max),
                cwi_ratio=weekly_ratio
            ))

        return warnings

    def check_fines_balance(self, fines: List, cwi: float) -> List[BalanceWarning]:
        """
        Check if fines are balanced relative to CWI.

        Args:
            fines: List of PayrollFine model instances
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not fines:
            return warnings

        fine_min_ratio, fine_max_ratio, _ = self._ratio_band("fine_weekly")
        recommended_min = cwi * fine_min_ratio
        recommended_max = cwi * fine_max_ratio

        for fine in fines:

            from app.models import _quantize_currency
            fine_amount = _quantize_currency(fine.amount)
            fine_ratio = float(fine_amount / Decimal(cwi)) if cwi > 0 else 0

            # Check if within bounds
            if fine_ratio < fine_min_ratio:
                deviation = (fine_min_ratio - fine_ratio) / fine_min_ratio
                if deviation > self.MINOR_DEVIATION_THRESHOLD:
                    level = WarningLevel.WARNING
                    warnings.append(BalanceWarning(
                        feature=f"Fine: {fine.name}",
                        level=level,
                        message=f"Fine amount (${abs(fine_amount):.2f}) is too small to be meaningful. Recommended range: ${recommended_min:.2f} - ${recommended_max:.2f}",
                        current_value=float(fine_amount),  # Convert to float for JSON serialization
                        recommended_min=recommended_min,
                        recommended_max=recommended_max,
                        cwi_ratio=fine_ratio
                    ))
            elif fine_ratio > fine_max_ratio:
                deviation = (fine_ratio - fine_max_ratio) / fine_max_ratio
                level = WarningLevel.CRITICAL if deviation > self.MAJOR_DEVIATION_THRESHOLD else WarningLevel.WARNING
                warnings.append(BalanceWarning(
                    feature=f"Fine: {fine.name}",
                    level=level,
                    message=f"Fine amount (${abs(fine_amount):.2f}) is too harsh and may cause student insolvency. Recommended range: ${recommended_min:.2f} - ${recommended_max:.2f}",
                    current_value=fine_amount,
                    recommended_min=recommended_min,
                    recommended_max=recommended_max,
                    cwi_ratio=fine_ratio
                ))
            else:
                # Within bounds
                warnings.append(BalanceWarning(
                    feature=f"Fine: {fine.name}",
                    level=WarningLevel.INFO,
                    message=f"Fine is balanced at ${fine_amount:.2f} ({fine_ratio:.2f}x CWI)",
                    current_value=fine_amount,
                    recommended_min=recommended_min,
                    recommended_max=recommended_max,
                    cwi_ratio=fine_ratio
                ))

        return warnings

    def check_overdraft_fee_balance(self, flat_overdraft_fee, cwi: float) -> List[BalanceWarning]:
        """Check the teacher-set overdraft / NSF fee against its recommended band.

        Per SPEC-ECON-003 §4.6.1.1 the teacher SETS the fee; the CWI helper only
        recommends a range. This surfaces a non-blocking advisory warning when the
        chosen flat fee falls outside the CWI-normed band (via the canonical
        ``resolve_overdraft_fine`` helper, so the band matches what the settings
        page displays). Returns [] when no fee is set or CWI is undefined.
        """
        warnings = []
        if flat_overdraft_fee is None or cwi is None or cwi <= 0:
            return warnings

        from app.services.economic_engine import resolve_overdraft_fine
        reco = resolve_overdraft_fine(cwi=Decimal(str(cwi)), mode=self.policy_mode)
        if reco.flat_fee_lower is None or reco.flat_fee_upper is None:
            return warnings

        fee = Decimal(str(flat_overdraft_fee))
        band = f"${reco.flat_fee_lower:.2f} - ${reco.flat_fee_upper:.2f}"
        if fee < reco.flat_fee_lower:
            warnings.append(BalanceWarning(
                feature="Overdraft Fee",
                level=WarningLevel.WARNING,
                message=f"Overdraft fee (${fee:.2f}) is below the recommended range ({band}). It may be too small to discourage overdrafts.",
                current_value=fee,
                recommended_min=reco.flat_fee_lower,
                recommended_max=reco.flat_fee_upper,
                cwi_ratio=None,
            ))
        elif fee > reco.flat_fee_upper:
            warnings.append(BalanceWarning(
                feature="Overdraft Fee",
                level=WarningLevel.WARNING,
                message=f"Overdraft fee (${fee:.2f}) is above the recommended range ({band}). It may be overly punishing.",
                current_value=fee,
                recommended_min=reco.flat_fee_lower,
                recommended_max=reco.flat_fee_upper,
                cwi_ratio=None,
            ))
        return warnings

    def check_store_items_balance(self, store_items: List, cwi: float) -> List[BalanceWarning]:
        """
        Check if store items are balanced relative to CWI.

        Args:
            store_items: List of StoreProduct model instances
            cwi: Calculated CWI value

        Returns:
            List of balance warnings
        """
        warnings = []

        if not store_items:
            return warnings

        # Availability is the caller's to decide, not this checker's. A product
        # version is sellable when its availability_state is IN_USE, and every
        # caller resolves that through store_service before handing the list
        # over. Re-deriving it here meant reading a v1 `is_active` column that
        # no longer exists, which took the whole analysis down with an
        # AttributeError.
        for item in store_items:
            # Skip long-term goal items from CWI balance checks
            if getattr(item, 'is_long_term_goal', False):
                continue

            # Grant-only products carry no price, so there is nothing to
            # position against the role's band.
            if item.price is None:
                continue

            price = float(item.price)
            price_ratio = price / cwi if cwi > 0 else 0

            try:
                role = EconomicRole(getattr(item, 'economic_role', None))
            except ValueError:
                continue

            band = self.store_role_bands(cwi)[role]
            band_min, band_max = float(band['min']), float(band['max'])
            label = role.value.replace('_', '-').title()

            if band_min <= price <= band_max:
                warnings.append(BalanceWarning(
                    feature=f"Store Item: {item.name}",
                    level=WarningLevel.INFO,
                    message=f"${price:.2f} is within the {label} range (${band_min:.2f}–${band_max:.2f}).",
                    current_value=price,
                    recommended_min=None,
                    recommended_max=None,
                    cwi_ratio=price_ratio
                ))
            elif price > band_max:
                warnings.append(BalanceWarning(
                    feature=f"Store Item: {item.name}",
                    level=WarningLevel.WARNING,
                    message=(
                        f"${price:.2f} is above the {label} range (${band_min:.2f}–${band_max:.2f}). "
                        "It takes students longer to reach than the role suggests."
                    ),
                    current_value=price,
                    recommended_min=band_min,
                    recommended_max=band_max,
                    cwi_ratio=price_ratio
                ))
            else:
                warnings.append(BalanceWarning(
                    feature=f"Store Item: {item.name}",
                    level=WarningLevel.WARNING,
                    message=(
                        f"${price:.2f} is below the {label} range (${band_min:.2f}–${band_max:.2f}). "
                        "Students reach it sooner than the role suggests."
                    ),
                    current_value=price,
                    recommended_min=band_min,
                    recommended_max=band_max,
                    cwi_ratio=price_ratio
                ))

        return warnings

    def validate_rent_value(
        self,
        rent_amount: float,
        frequency_type: str,
        cwi: float,
        custom_frequency_value: Optional[float] = None,
        custom_frequency_unit: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
        """
        Validate rent amount against CWI-based recommendations.

        The band comes from the class's policy-mode weekly burden ratios, scaled
        to the teacher's chosen frequency and rounded once, so the recommendation
        is a value they can actually type.
        """
        # Convert input rent to weekly for comparison
        from app.models import _quantize_currency
        weekly_rent = self._normalize_to_weekly(
            _quantize_currency(rent_amount),
            frequency_type,
            _quantize_currency(custom_frequency_value) if custom_frequency_value is not None else None,
            custom_frequency_unit,
        )

        # One band, in the teacher's own cadence: the same call the balance
        # warning makes (INV-ARC-022).
        band = self.rent_band(
            cwi,
            frequency_type,
            custom_frequency_value,
            custom_frequency_unit,
        )
        recommendations = {key: float(value) for key, value in band.items()}

        cwi_decimal = Decimal(str(cwi)) if isinstance(cwi, (float, int)) else cwi
        ratio = weekly_rent / cwi_decimal if cwi_decimal > 0 else Decimal('0')

        label = frequency_label(
            frequency_type,
            custom_frequency_value=custom_frequency_value,
            custom_frequency_unit=custom_frequency_unit,
        )

        warnings: List[Dict[str, str]] = []
        # Compare against the same rounded band the message quotes back. A raw
        # ratio comparison flags an amount as out of range while naming a
        # boundary that prints identically to the amount itself.
        if rent_amount < recommendations['min']:
            warnings.append({
                'level': 'warning',
                'title': 'Rent may be set too low',
                'message': (
                    f"The rent amount you entered (${rent_amount:.2f} {label}) is "
                    f"below the recommended minimum of ${recommendations['min']:.2f} {label}. "
                    f"This may reduce students' incentive to budget and save."
                ),
            })
        elif rent_amount > recommendations['max']:
            warnings.append({
                'level': 'warning',
                'title': 'Rent may be set too high',
                'message': (
                    f"The rent amount you entered (${rent_amount:.2f} {label}) is "
                    f"above the recommended maximum of ${recommendations['max']:.2f} {label}. "
                    f"Students may have difficulty meeting their other obligations."
                ),
            })
        else:
            warnings.append({
                'level': 'success',
                'title': 'Rent is balanced',
                'message': (
                    f"Rent is set to ${rent_amount:.2f} {label} "
                    f"(${weekly_rent:.2f} per week), within the recommended range."
                ),
            })

        return warnings, recommendations, float(ratio)

    def validate_fine_value(self, fine_amount: float, cwi: float) -> Tuple[List[Dict[str, str]], Dict[str, float], float]:
        fine_amount = float(fine_amount)
        cwi = float(cwi)
        ratio = fine_amount / cwi if cwi > 0 else 0

        # The class's policy mode, not the default-mode constants: a tight or
        # comfortable class was shown its own band and judged against another's.
        # The comparison is on the displayed cents for the same reason rent's is.
        recommendations = {key: float(value) for key, value in self.fine_band(cwi).items()}

        warnings: List[Dict[str, str]] = []
        if fine_amount < recommendations['min']:
            warnings.append({
                'level': 'warning',
                'message': f'Fine (${fine_amount:.2f}) may be too small to be meaningful.',
            })
        elif fine_amount > recommendations['max']:
            warnings.append({
                'level': 'critical',
                'message': f'Fine (${fine_amount:.2f}) is too harsh. May cause student insolvency.',
            })
        else:
            warnings.append({
                'level': 'success',
                'message': f'Fine is balanced at ${fine_amount:.2f}',
            })

        return warnings, recommendations, float(ratio)

    def validate_store_item_value(
        self,
        price: float,
        cwi: float,
        economic_role: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, float]], float]:
        """Position a price against its declared economic role's band.

        The role is an input, not an inference. A price outside its role's band
        stays valid (SPEC-ECON-003 §4.7) — the report says where it sits, it
        does not reclassify the product or reject the value.
        """
        price = float(price)
        cwi = float(cwi)
        ratio = price / cwi if cwi > 0 else 0
        warnings: List[Dict[str, str]] = []

        # Bands are compared on the displayed currency figure, not the raw
        # ratio: a price copied from a band's printed maximum rounds a fraction
        # of a cent above the ratio boundary and read as out of range.
        role_bands = {
            role: {key: float(value) for key, value in band.items()}
            for role, band in self.store_role_bands(cwi).items()
        }
        recommendations: Dict[str, Dict[str, float]] = {
            'roles': {role.value: dict(band) for role, band in role_bands.items()}
        }

        try:
            role = EconomicRole(economic_role)
        except ValueError:
            return warnings, recommendations, float(ratio)

        band = role_bands[role]
        label = role.value.replace('_', '-').title()
        recommendations[role.value] = dict(band)
        recommendations['selected_role'] = dict(band)

        if band['min'] <= price <= band['max']:
            warnings.append({
                'level': 'success',
                'message': f"${price:.2f} is within the {label} range (${band['min']:.2f}–${band['max']:.2f}).",
            })
        elif price > band['max']:
            warnings.append({
                'level': 'warning',
                'message': (
                    f"${price:.2f} is above the {label} range (${band['min']:.2f}–${band['max']:.2f}). "
                    "It takes students longer to reach than the role suggests."
                ),
            })
        else:
            warnings.append({
                'level': 'warning',
                'message': (
                    f"${price:.2f} is below the {label} range (${band['min']:.2f}–${band['max']:.2f}). "
                    "Students reach it sooner than the role suggests."
                ),
            })

        return warnings, recommendations, float(ratio)

    def validate_feature_value(self, feature: str, value: float, cwi: float, **kwargs):
        if feature == 'rent':
            return self.validate_rent_value(
                value,
                kwargs.get('frequency_type', 'monthly'),
                cwi,
                kwargs.get('custom_frequency_value'),
                kwargs.get('custom_frequency_unit'),
            )
        # NOTE (SPEC-ECON-003 migration): insurance validation is owned by the
        # Economic Engine (resolve_insurance) via the product-aware edit flow.
        # The legacy free-form CWI-band validator has been retired; 'insurance'
        # is no longer a supported feature for this generic validator.
        if feature == 'fine':
            return self.validate_fine_value(value, cwi)
        if feature == 'store_item':
            return self.validate_store_item_value(value, cwi, kwargs.get('economic_role'))

        raise ValueError('Unsupported feature type')

    def calculate_budget_survival(
        self,
        cwi: float,
        rent_settings,
        insurance_policies: List,
        average_store_spending: Optional[float] = None
    ) -> Tuple[bool, float]:
        """
        Perform Budget Survival Test per SPEC-ECON-003 §4.2 (weekly savings target) and §7 (Economic Coherence Rules).

        A student with perfect attendance must be able to save at least 10% of CWI weekly.

        Args:
            cwi: Calculated CWI
            rent_settings: RentSettings model instance
            insurance_policies: List of active insurance policies (we'll use average or cheapest)
            average_store_spending: Average weekly store spending (optional, estimated if None)

        Returns:
            Tuple of (passed: bool, weekly_savings: float)
        """
        weekly_income = cwi

        # Calculate weekly rent
        weekly_rent = 0
        if rent_settings:
            rent_amount = float(rent_settings.rent_amount)
            weekly_rent = float(self._normalize_to_weekly(
                rent_amount,
                rent_settings.frequency_type,
                rent_settings.custom_frequency_value,
                getattr(rent_settings, 'custom_frequency_unit', None)
            ))

        # Calculate weekly insurance (use cheapest offered policy as baseline).
        # Same rule as store items: the caller passes the offered set; this
        # checker does not re-derive availability.
        weekly_insurance = 0
        if insurance_policies:
            weekly_premiums = [
                weekly for weekly in (
                    self._weekly_insurance_premium(policy) for policy in insurance_policies
                )
                if weekly is not None
            ]
            weekly_insurance = min(weekly_premiums) if weekly_premiums else 0

        # Estimate weekly store spending if not provided
        if average_store_spending is None:
            # Conservative estimate: 15% of CWI on store items
            average_store_spending = cwi * self.ESTIMATED_WEEKLY_STORE_SPENDING_RATIO

        # Calculate weekly savings
        weekly_savings = weekly_income - weekly_rent - weekly_insurance - average_store_spending

        required_savings = cwi * self._minimum_ratio("savings_weekly")
        passed = weekly_savings >= required_savings

        return passed, weekly_savings

    def analyze_economy(
        self,
        payroll_settings,
        rent_settings=None,
        insurance_policies: List = None,
        fines: List = None,
        store_items: List = None,
        expected_weekly_hours: float = None,
        average_store_spending: Optional[float] = None
    ) -> EconomyBalance:
        """
        Perform comprehensive economy balance analysis.

        Args:
            payroll_settings: PayrollSettings instance
            rent_settings: RentSettings instance (optional)
            insurance_policies: Policy rows (optional)
            fines: List of PayrollFine instances (optional)
            store_items: List of StoreProduct instances (optional)
            expected_weekly_hours: Expected weekly attendance hours
            average_store_spending: Average weekly store spending (estimated if None)

        Returns:
            EconomyBalance with complete analysis
        """
        # Calculate CWI
        cwi_calc = self.calculate_cwi(payroll_settings, expected_weekly_hours)
        if cwi_calc is None:
            # CWI is undefined without expected_weekly_hours; skip pricing analysis.
            # Consumers should show a "configure CWI" warning and hide recommendations.
            return EconomyBalance(
                cwi=None,
                is_balanced=False,
                warnings=[BalanceWarning(
                    feature="CWI",
                    level=WarningLevel.WARNING,
                    message="Expected weekly hours not configured. Set it on the Economic Engine page to enable pricing recommendations.",
                    current_value=None,
                    recommended_min=None,
                    recommended_max=None,
                    cwi_ratio=None,
                )],
                recommendations={},
                budget_survival_test_passed=False,
                weekly_savings=0.0,
            )
        cwi = cwi_calc.cwi

        # Collect all warnings
        all_warnings = []

        # Check rent
        if rent_settings:
            all_warnings.extend(self.check_rent_balance(rent_settings, cwi))

        # NOTE (SPEC-ECON-003 migration): insurance balance analysis is now owned
        # by the Economic Engine (resolve_insurance). The legacy CWI-band checker
        # has been retired; insurance policies are not evaluated here.

        # Check fines
        if fines:
            all_warnings.extend(self.check_fines_balance(fines or [], cwi))

        # Check store items
        if store_items:
            all_warnings.extend(self.check_store_items_balance(store_items or [], cwi))

        # Run budget survival test
        survival_passed, weekly_savings = self.calculate_budget_survival(
            cwi, rent_settings, insurance_policies or [], average_store_spending
        )

        if not survival_passed:
            all_warnings.append(BalanceWarning(
                feature="Budget Survival Test",
                level=WarningLevel.CRITICAL,
                message=f"Students cannot save enough income! Weekly savings: ${weekly_savings:.2f} (need ${cwi * self._minimum_ratio('savings_weekly'):.2f})",
                current_value=weekly_savings,
                recommended_min=cwi * self._minimum_ratio("savings_weekly"),
                recommended_max=None,
                cwi_ratio=weekly_savings / cwi if cwi > 0 else 0
            ))

        recommendations = self.generate_recommendations(cwi, all_warnings)

        # Determine if economy is balanced
        # Balanced if: no critical warnings and survival test passed
        critical_warnings = [w for w in all_warnings if w.level == WarningLevel.CRITICAL]
        is_balanced = len(critical_warnings) == 0 and survival_passed

        return EconomyBalance(
            cwi=cwi_calc,
            is_balanced=is_balanced,
            warnings=all_warnings,
            recommendations=recommendations,
            budget_survival_test_passed=survival_passed,
            weekly_savings=weekly_savings
        )

    def generate_recommendations(self, cwi: float, warnings: Optional[List[BalanceWarning]] = None) -> Dict[str, Any]:
        """
        Generate recommended configurations based on CWI and warnings.

        Args:
            cwi: Calculated CWI
            warnings: Optional list of balance warnings

        Returns:
            Dictionary of recommendations per feature
        """
        recommendations = get_price_recommendation_context(self.policy_mode, cwi)
        return recommendations or {}

    def _generate_recommendations(self, cwi: float, warnings: List[BalanceWarning]) -> Dict[str, Any]:
        return self.generate_recommendations(cwi, warnings)


def format_warnings_for_display(warnings: List[BalanceWarning]) -> str:
    """
    Format warnings as HTML for teacher display.

    Args:
        warnings: List of BalanceWarning objects

    Returns:
        HTML string
    """
    def _alert_card_open(level: str, icon: str, title: str) -> str:
        # Mirrors the `alert_card` macro in templates/macros/cards.html.
        text_class = 'text-dark' if level == 'warning' else 'text-white'
        return (
            f'<div class="card alert-card border-{level} mb-3">'
            f'<div class="card-header bg-{level} {text_class} d-flex align-items-center">'
            f'<span class="material-symbols-outlined me-2" aria-hidden="true">{icon}</span>'
            f'<h3 class="h5 fw-bold mb-0 {text_class}">{title}</h3>'
            '</div>'
            '<div class="card-body">'
        )

    if not warnings:
        return (
            _alert_card_open('success', 'check_circle', 'Economy is balanced')
            + '<p class="mb-0">No balance warnings for the current settings.</p></div></div>'
        )

    # Group by level
    critical = [w for w in warnings if w.level == WarningLevel.CRITICAL]
    warning = [w for w in warnings if w.level == WarningLevel.WARNING]
    info = [w for w in warnings if w.level == WarningLevel.INFO]

    html_parts = []

    if critical:
        html_parts.append(_alert_card_open('danger', 'error', 'Critical economy issues') + '<ul class="mb-0">')
        for w in critical:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div></div>')

    if warning:
        html_parts.append(_alert_card_open('warning', 'warning', 'Economy warnings') + '<ul class="mb-0">')
        for w in warning:
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div></div>')

    if info and not (critical or warning):  # Only show info if no problems
        html_parts.append(_alert_card_open('info', 'info', 'Balance details') + '<ul class="mb-0">')
        for w in info[:5]:  # Limit to 5 info messages
            html_parts.append(f'<li>{w.message}</li>')
        html_parts.append('</ul></div></div>')

    return '\n'.join(html_parts)
