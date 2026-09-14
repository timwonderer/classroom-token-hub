"""Server-owned Store creation-form legality contract.

The browser may render and switch these contracts, but it must not derive them.
The publication seam remains authoritative for mutation validation.
"""
from dataclasses import dataclass

from app.utils.economy_policy import get_policy_profile


@dataclass(frozen=True)
class FormField:
    name: str
    kind: str
    label: str
    required: bool = False
    depends_on: str | None = None
    help_text: str | None = None


@dataclass(frozen=True)
class FormSection:
    key: str
    title: str
    fields: tuple[FormField, ...]


@dataclass(frozen=True)
class StoreFormContract:
    item_type: str
    rent_linked: bool
    direct_purchase: bool
    sections: tuple[FormSection, ...]
    legal_fields: frozenset[str]


_PURCHASABLE = frozenset({'immediate', 'delayed', 'hall_pass', 'privilege'})
_INVENTORY = frozenset({'immediate', 'delayed', 'hall_pass'})
_HOLDING = frozenset({'immediate', 'delayed', 'hall_pass'})
_EXPIRING = frozenset({'delayed', 'privilege', 'hall_pass'})
_PROMPTABLE = frozenset({'delayed', 'collective'})
_RENT_LINKABLE = frozenset({'immediate', 'delayed', 'hall_pass', 'privilege'})


def resolve_store_form_contract(*, item_type: str, rent_linked: bool,
                                direct_purchase: bool,
                                rent_prevents_purchase_when_late: bool,
                                collective_goal_band: dict | None = None,
                                cwi: float | None = None) -> StoreFormContract:
    """Resolve the complete lawful field set for one form state."""
    basic: list[FormField] = [
        FormField('item_type', 'select', 'Item Type', True),
        FormField('is_long_term_goal', 'hidden', 'Long-Term Goal'),
    ]
    details: list[FormField] = [
        FormField('name', 'text', 'Item Name', True),
        FormField('description', 'markdown', 'Description'),
        # Required for every item type, including grant-only and collective
        # ones: it selects the CWI reference band the pricing helper reports
        # against, so it cannot be gated behind direct purchase.
        FormField(
            'economic_role', 'select', 'Economic Role', True,
            help_text='Guidance only — it sets the reference range shown for the '
                      'price and never decides whether a student may buy the item.',
        ),
    ]
    acquisition: list[FormField] = []
    purchase: list[FormField] = []
    type_specific: list[FormField] = []
    lifecycle: list[FormField] = []
    if item_type in _RENT_LINKABLE:
        acquisition.extend([
            FormField('is_rent_linked', 'checkbox', 'Students receive this item when they pay rent'),
        ])
    if rent_linked and item_type in _RENT_LINKABLE:
        acquisition.append(FormField('rent_linked_quantity', 'number', 'Quantity granted per rent payment', True))
        acquisition.append(FormField('direct_purchase_allowed', 'checkbox', 'Students can purchase this item directly'))
        if direct_purchase and rent_prevents_purchase_when_late:
            acquisition.append(FormField('essential_when_overdue', 'checkbox', 'Essential: allow purchase when rent is overdue'))
    if item_type in _PURCHASABLE and direct_purchase:
        purchase.append(FormField('price', 'currency', 'Price', True))
        purchase.append(FormField(
            'bypass_cwi_warnings', 'checkbox', 'Bypass CWI Warnings',
            help_text='Suppress CWI warnings for this directly purchasable item.',
        ))
    if item_type == 'collective':
        # The band is read from policy authority, never restated here. A literal
        # pair lived at this line and had drifted to 1×–8×, a range no policy mode
        # defines, so the guidance a teacher read was not the band the Economic
        # Engine judged the goal against (INV-ARC-022). Absent an explicit band
        # this resolves the canonical default-mode profile — `get_policy_profile`
        # normalizes ``None`` to `POLICY_MODE_DEFAULT` — so the fallback is a read
        # from the one source rather than a second spelling of it.
        band = collective_goal_band or get_policy_profile(None)['ratios']['collective_goal']
        low, high = band['min'], band['max']
        purchase.append(FormField(
            'price', 'currency', 'Goal Amount', True,
        ))
        # Currency first, multiplier in parentheses. A teacher types a goal in
        # dollars, so a bare "1×–5× CWI" asks them to do the arithmetic the
        # surface exists to do for them. The multiplier stays visible because it
        # is what §4.6 actually specifies and what Rebalance re-derives from.
        multiplier = f"{low:g}×–{high:g}× CWI"
        if cwi and cwi > 0:
            guidance = (
                f"Recommended range: ${cwi * low:,.2f}–${cwi * high:,.2f} "
                f"({multiplier})."
            )
        else:
            # No pay rate or expected weekly hours yet, so there is no CWI to
            # price against. Say that, rather than presenting the bare ratio as
            # though it were the recommendation.
            guidance = (
                f"Recommended range: {multiplier}. Set the class pay rate and "
                f"expected weekly hours to see this range in dollars."
            )
        purchase.append(FormField('collective_goal_guidance', 'info', guidance))
    if item_type in _INVENTORY and direct_purchase:
        purchase.append(FormField('inventory', 'number', 'Inventory'))
    if item_type in _HOLDING and direct_purchase:
        purchase.append(FormField('holding_limit', 'number', 'Holding Limit'))
    if item_type in _EXPIRING:
        lifecycle.append(FormField('auto_expiry_days', 'number', 'Item Expiry in Days'))
    if item_type == 'collective':
        type_specific.extend([
            FormField('collective_goal_type', 'select', 'Unlock mode', True),
            FormField('collective_goal_target', 'number', 'Required student count', depends_on='collective_goal_type:fixed'),
            FormField('collective_goal_expires_at', 'date', 'Goal Expiration Date'),
        ])
    if item_type in _PROMPTABLE:
        lifecycle.extend([
            FormField('redemption_prompt_enabled', 'checkbox', 'Students need to provide extra information'),
            FormField('redemption_prompt', 'markdown', 'Prompt for students to answer when redeeming', depends_on='redemption_prompt_enabled'),
        ])
    if not (rent_linked and not direct_purchase):
        lifecycle.insert(0, FormField('activation_date', 'date', 'Start date'))
    elif item_type in _RENT_LINKABLE:
        lifecycle.insert(0, FormField('rent_link_activation_info', 'info', 'Rent-linked grants begin on the next rent cycle; no separate start date is needed.'))
    if item_type in {'immediate', 'delayed', 'hall_pass'} and direct_purchase:
        purchase.extend([
            FormField('bulk_discount_enabled', 'checkbox', 'Enable Bulk Discount'),
            FormField('bulk_discount_quantity', 'number', 'Minimum Quantity for Discount', depends_on='bulk_discount_enabled'),
            FormField('bulk_discount_percentage', 'number', 'Discount Percentage', depends_on='bulk_discount_enabled'),
        ])
    if item_type in {'delayed', 'hall_pass'}:
        purchase.extend([
            FormField('is_bundle', 'checkbox', 'This is a Bundled Item'),
            FormField('bundle_quantity', 'number', 'Bundle Quantity', depends_on='is_bundle'),
        ])
    groups = (
        ('basic', 'Basic Information', basic),
        ('acquisition', 'How Students Get It', acquisition),
        ('details', 'Item Details', details),
        ('purchase', 'Purchase Settings', purchase),
        ('type_specific', 'Type-specific Settings', type_specific),
        ('lifecycle', 'Lifecycle Settings', lifecycle),
    )
    sections = tuple(
        FormSection(key, title, tuple(group_fields))
        for key, title, group_fields in groups if group_fields
    )
    fields = [field for section in sections for field in section.fields]
    return StoreFormContract(
        item_type=item_type,
        rent_linked=rent_linked,
        direct_purchase=direct_purchase,
        sections=sections,
        legal_fields=frozenset(field.name for field in fields),
    )


def contract_payload(*, rent_prevents_purchase_when_late: bool,
                     collective_goal_band: dict | None = None,
                     cwi: float | None = None) -> dict:
    """Serializable state-contract catalogue consumed by the browser."""
    payload = {}
    for item_type in sorted(_PURCHASABLE | {'collective'}):
        for rent_linked in (False, True):
            direct_values = (True, False) if rent_linked else (True,)
            for direct in direct_values:
                contract = resolve_store_form_contract(
                    item_type=item_type,
                    rent_linked=rent_linked,
                    direct_purchase=direct,
                    rent_prevents_purchase_when_late=rent_prevents_purchase_when_late,
                    collective_goal_band=collective_goal_band,
                    cwi=cwi,
                )
                payload[f'{item_type}|{int(rent_linked)}|{int(direct)}'] = {
                    'legal_fields': sorted(contract.legal_fields),
                    'sections': [
                        {'key': section.key, 'title': section.title,
                         'fields': [field.__dict__ for field in section.fields]}
                        for section in contract.sections
                    ],
                }
    return payload


def form_field_catalog(*, rent_prevents_purchase_when_late: bool,
                       collective_goal_band: dict | None = None,
                       cwi: float | None = None) -> tuple[FormSection, ...]:
    """Return every renderable field, grouped by its canonical section.

    The browser needs the complete presentation vocabulary so a type change can
    switch contracts without inventing controls in JavaScript. Legality still
    comes exclusively from the selected contract.
    """
    sections: dict[str, tuple[str, list[FormField]]] = {}
    known_fields: set[str] = set()
    for item_type in sorted(_PURCHASABLE | {'collective'}):
        for rent_linked in (False, True):
            for direct in ((True, False) if rent_linked else (True,)):
                contract = resolve_store_form_contract(
                    item_type=item_type,
                    rent_linked=rent_linked,
                    direct_purchase=direct,
                    rent_prevents_purchase_when_late=rent_prevents_purchase_when_late,
                    collective_goal_band=collective_goal_band,
                    cwi=cwi,
                )
                for section in contract.sections:
                    key_title = sections.setdefault(section.key, (section.title, []))
                    new_fields = [field for field in section.fields if field.name not in known_fields]
                    key_title[1].extend(new_fields)
                    known_fields.update(field.name for field in new_fields)
    section_order = (
        ('basic', 'Basic Information'),
        ('acquisition', 'How Students Get It'),
        ('details', 'Item Details'),
        ('purchase', 'Purchase Settings'),
        ('type_specific', 'Type-specific Settings'),
        ('lifecycle', 'Lifecycle Settings'),
    )
    return tuple(
        FormSection(key, title, tuple(sections[key][1]))
        for key, title in section_order
        if key in sections and sections[key][1]
    )
