"""User activity logging for SKSS-MIS."""

from flask import request
from flask_login import current_user

from app.extensions import db

MODULE_LABELS = {
    "auth": "Login / Logout",
    "purchase_order": "Purchase Order",
    "supplier_purchase": "Supplier Purchase",
    "purchase_return": "Purchase Return",
    "supplier_payment": "Supplier Payment",
    "expense_payment": "Expense Payment",
    "receipt_mis": "Receipt MIS",
    "monthly_budget": "Monthly Budget",
    "supplier_mis_report": "Supplier MIS Report",
    "po_variation_report": "PO Variation Report",
    "expenses_mis_report": "Expenses MIS Report",
    "cash_report": "Cash Report",
    "budget_vs_actual_report": "Budget vs Actual Report",
    "users": "Users",
    "brands": "Brands",
    "supplier_categories": "Supplier Categories",
    "suppliers": "Suppliers",
    "branches": "Branches",
    "expense_groups": "Expense Groups",
    "expense_categories": "Expense Categories",
    "bank_accounts": "Bank and Cash Master",
    "opening_balances": "Opening Balances",
    "settings": "Settings",
}

ACTION_LABELS = {
    "create": "Create",
    "update": "Update",
    "delete": "Delete",
    "export": "Export",
    "approve": "Approve",
    "login": "Login",
    "logout": "Logout",
    "bulk_upload": "Bulk Upload",
    "clear_data": "Clear Data",
}


def log_activity(
    action: str,
    module: str,
    description: str,
    record_ref: str | None = None,
    user=None,
) -> None:
    from app.models import ActivityLog

    actor = user or current_user
    if not actor or not getattr(actor, "is_authenticated", False):
        return

    entry = ActivityLog(
        user_id=actor.id,
        username=actor.username,
        action=action,
        module=module,
        description=description[:500],
        record_ref=(record_ref[:100] if record_ref else None),
        ip_address=(request.remote_addr or "")[:45] if request else None,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
