"""User module permissions for SKSS-MIS."""

from functools import wraps

from flask import abort
from flask_login import current_user

from app.extensions import db

PERMISSION_MODULES = [
    ("purchase_order", "Purchase Order"),
    ("supplier_purchase", "Supplier Purchase"),
    ("purchase_return", "Purchase Return"),
    ("supplier_payment", "Supplier Payment"),
    ("expense_payment", "Expense Payment"),
    ("receipt_mis", "Receipt MIS"),
    ("supplier_mis_report", "Supplier MIS Report"),
    ("po_variation_report", "PO Variation Report"),
    ("expenses_mis_report", "Expenses MIS Report"),
    ("cash_report", "Cash Report"),
]

PERMISSION_ACTIONS = [
    ("view", "View"),
    ("create", "Create"),
    ("edit", "Edit"),
    ("delete", "Delete"),
]


def user_has_permission(user, module: str, action: str = "view") -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_admin:
        return True
    from app.models import UserModulePermission

    perm = UserModulePermission.query.filter_by(user_id=user.id, module=module).first()
    if not perm:
        return False
    return bool(getattr(perm, f"can_{action}", False))


def permission_required(module: str, action: str = "view"):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not user_has_permission(current_user, module, action):
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def module_access(module: str):
    """Require view on GET and create on POST for combined entry routes."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from flask import request

            if not current_user.is_authenticated:
                abort(401)
            action = "create" if request.method == "POST" else "view"
            if not user_has_permission(current_user, module, action):
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


def get_user_permissions_map(user_id: int) -> dict:
    from app.models import UserModulePermission

    perms = UserModulePermission.query.filter_by(user_id=user_id).all()
    return {p.module: p for p in perms}


def grant_all_permissions(user_id: int) -> None:
    """Give the user View/Create/Edit/Delete on every module."""
    from app.models import UserModulePermission

    UserModulePermission.query.filter_by(user_id=user_id).delete()
    for module_key, _label in PERMISSION_MODULES:
        db.session.add(
            UserModulePermission(
                user_id=user_id,
                module=module_key,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True,
            )
        )


def save_user_permissions(user_id: int, form_data) -> None:
    from app.models import UserModulePermission

    UserModulePermission.query.filter_by(user_id=user_id).delete()
    for module_key, _label in PERMISSION_MODULES:
        perm = UserModulePermission(
            user_id=user_id,
            module=module_key,
            can_view=form_data.get(f"perm_{module_key}_view") == "on",
            can_create=form_data.get(f"perm_{module_key}_create") == "on",
            can_edit=form_data.get(f"perm_{module_key}_edit") == "on",
            can_delete=form_data.get(f"perm_{module_key}_delete") == "on",
        )
        if perm.can_view or perm.can_create or perm.can_edit or perm.can_delete:
            db.session.add(perm)
