"""Policies-owned, current-only portable definitions. All reads are class scoped."""
from app.services.configuration_fields import project
from app.services.class_configuration_query_service import get_rent_settings
from app.services.payroll.settings import current_payroll_setting
from app.services.hall_pass_configuration import _current_hall_pass_settings
from app.services import store_service, insurance_definition_service


def policy_inventory(context):
    class_id = context.class_id
    payroll = current_payroll_setting(class_id)
    rent = get_rent_settings(class_id)
    hall = _current_hall_pass_settings(class_id)
    linked = {b.get("product_lineage_uuid") for b in rent.get_satisfaction_benefit_grants()} if rent else set()
    store = [project(row, "store", context) for row in store_service.list_products(class_id, states=["IN_USE"])
             if row.product_lineage_uuid not in linked]
    groups = {}
    insurance = []
    for row in insurance_definition_service.list_insurance_definitions(class_id=class_id, availability_states=["IN_USE"]):
        if row.tier_group and not row.tier_group_id:
            raise ValueError("Insurance identity migration must complete before export")
        if row.tier_group_id:
            group = groups.setdefault(row.tier_group_id, {"name": row.tier_group, "policies": []})
            group["policies"].append(project(row, "insurance", context))
        else:
            insurance.append({"name": None, "policies": [project(row, "insurance", context)]})
    insurance.extend(groups.values())
    result = {"store": store, "insurance": insurance}
    if payroll:
        result["payroll"] = project(payroll, "payroll", context)
    if rent:
        result["rent"] = project(rent, "rent", context)
    if hall:
        result["hall_pass"] = {"max_queue_limit": hall.max_queue_limit, "pass_type_payload": hall.pass_type_payload}
    return result
