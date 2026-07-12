from datetime import date
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.activity_log import ACTION_LABELS, MODULE_LABELS, log_activity
from app.bulk_upload import build_workbook, get_cell, parse_float_cell, read_upload_rows
from app.extensions import db
from app.models import (
    ActivityLog,
    BankAccount,
    Brand,
    Company,
    ExpenseCategory,
    ExpenseGroup,
    ExpensePayment,
    OpeningBalance,
    Supplier,
    SupplierCategory,
    User,
)
from app.utils import admin_required, clear_test_data, get_test_data_counts, parse_date
from app.permissions import (
    PERMISSION_ACTIONS,
    PERMISSION_MODULES,
    get_user_permissions_map,
    grant_all_permissions,
    save_user_permissions,
)

masters_bp = Blueprint("masters", __name__)

BULK_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "bulk_templates"


def _get_or_create_company(name: str) -> Company:
    company = Company.query.filter_by(name=name).first()
    if not company:
        company = Company(name=name)
        db.session.add(company)
        db.session.flush()
    return company


def _get_category_by_name(name: str):
    if not name:
        return None
    return SupplierCategory.query.filter_by(name=name).first()


@masters_bp.route("/")
@login_required
@admin_required
def index():
    return render_template("masters/index.html")


@masters_bp.route("/delete-test-data", methods=["GET", "POST"])
@login_required
@admin_required
def delete_test_data():
    counts = get_test_data_counts()
    total_records = sum(counts.values())

    if request.method == "POST":
        if request.form.get("confirm_text", "").strip().upper() != "DELETE":
            flash('Type DELETE in the confirmation box to proceed.', "danger")
        else:
            deleted = clear_test_data()
            total_deleted = sum(deleted.values())
            log_activity(
                "clear_data",
                "settings",
                f"Deleted test data ({total_deleted} records removed)",
            )
            flash(f"Test data deleted ({total_deleted} records removed). Master data was kept.", "success")
            return redirect(url_for("masters.index"))

    return render_template(
        "masters/delete_test_data.html",
        counts=counts,
        total_records=total_records,
    )


@masters_bp.route("/activity-log")
@login_required
@admin_required
def activity_log():
    page = request.args.get("page", 1, type=int)
    selected_user_id = request.args.get("user_id", type=int)
    selected_module = request.args.get("module", "").strip()
    selected_action = request.args.get("action", "").strip()

    query = ActivityLog.query.order_by(ActivityLog.created_at.desc())
    if selected_user_id:
        query = query.filter(ActivityLog.user_id == selected_user_id)
    if selected_module:
        query = query.filter(ActivityLog.module == selected_module)
    if selected_action:
        query = query.filter(ActivityLog.action == selected_action)

    pagination = query.paginate(page=page, per_page=50, error_out=False)
    users = User.query.order_by(User.username).all()
    return render_template(
        "masters/activity_log.html",
        logs=pagination.items,
        pagination=pagination,
        users=users,
        module_labels=MODULE_LABELS,
        action_labels=ACTION_LABELS,
        selected_user_id=selected_user_id,
        selected_module=selected_module,
        selected_action=selected_action,
    )


# --- Users ---


@masters_bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "staff")
        if username and password:
            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "warning")
            else:
                user = User(username=username, role=role)
                user.set_password(password)
                db.session.add(user)
                db.session.flush()
                if role != "admin":
                    grant_all_permissions(user.id)
                db.session.commit()
                log_activity("create", "users", f"Created user {username}", username)
                flash("User created with all module permissions selected.", "success")
        else:
            flash("Username and password are required.", "danger")
        return redirect(url_for("masters.users"))

    users_list = User.query.order_by(User.username).all()
    return render_template("masters/users.html", users=users_list)


@masters_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        user.role = request.form.get("role", "staff")
        user.is_active = request.form.get("is_active") == "on"
        new_password = request.form.get("password", "").strip()
        if new_password:
            user.set_password(new_password)
        if user.role != "admin":
            save_user_permissions(user.id, request.form)
        else:
            from app.models import UserModulePermission

            UserModulePermission.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        log_activity("update", "users", f"Updated user {user.username}", user.username)
        flash("User updated.", "success")
        return redirect(url_for("masters.users"))
    permissions_map = get_user_permissions_map(user.id)
    # Existing users with no permissions yet: show all modules selected on edit.
    if user.role != "admin" and not permissions_map:
        grant_all_permissions(user.id)
        db.session.commit()
        permissions_map = get_user_permissions_map(user.id)
    return render_template(
        "masters/edit_user.html",
        user=user,
        permissions_map=permissions_map,
        permission_modules=PERMISSION_MODULES,
        permission_actions=PERMISSION_ACTIONS,
    )


@masters_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
    elif user.username == "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("Cannot delete the only admin account.", "danger")
    else:
        db.session.delete(user)
        db.session.commit()
        log_activity("delete", "users", f"Deleted user {user.username}", user.username)
        flash("User deleted.", "success")
    return redirect(url_for("masters.users"))


# --- Brands ---


@masters_bp.route("/brands", methods=["GET", "POST"])
@login_required
@admin_required
def brands():
    companies = Company.query.order_by(Company.name).all()
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        brand_name = request.form.get("brand_name", "").strip()
        if company_name and brand_name:
            company = _get_or_create_company(company_name)
            existing = Brand.query.filter_by(company_id=company.id, name=brand_name).first()
            if existing:
                flash("This brand already exists under the company.", "warning")
            else:
                db.session.add(Brand(company_id=company.id, name=brand_name))
                db.session.commit()
                log_activity("create", "brands", f"Added brand {brand_name} under {company_name}", brand_name)
                flash("Brand added.", "success")
        else:
            flash("Company name and brand name are required.", "danger")
        return redirect(url_for("masters.brands"))

    brands_list = (
        Brand.query.join(Company).order_by(Company.name, Brand.name).all()
    )
    return render_template("masters/brands.html", brands=brands_list, companies=companies)


@masters_bp.route("/brands/<int:brand_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_brand(brand_id):
    brand = db.get_or_404(Brand, brand_id)
    if brand.bills or brand.payments:
        flash("Cannot delete brand with linked transactions.", "danger")
    else:
        db.session.delete(brand)
        db.session.commit()
        log_activity("delete", "brands", f"Deleted brand {brand.name}", brand.name)
        flash("Brand deleted.", "success")
    return redirect(url_for("masters.brands"))


@masters_bp.route("/brands/bulk-template")
@login_required
@admin_required
def brands_bulk_template():
    path = BULK_TEMPLATE_DIR / "brand_upload_template.xlsx"
    if not path.exists():
        buffer = build_workbook(
            ["Company Name", "Brand Name"],
            [
                ["HUL", "Dove"],
                ["HUL", "Lux"],
                ["Britannia", "Good Day"],
                ["Himalaya", "Face Wash"],
            ],
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name="brand_upload_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return send_file(path, as_attachment=True, download_name="brand_upload_template.xlsx")


@masters_bp.route("/brands/bulk-template-csv")
@login_required
@admin_required
def brands_bulk_template_csv():
    path = BULK_TEMPLATE_DIR / "brand_upload_template.csv"
    return send_file(path, as_attachment=True, download_name="brand_upload_template.csv", mimetype="text/csv")


@masters_bp.route("/brands/bulk-upload", methods=["POST"])
@login_required
@admin_required
def brands_bulk_upload():
    file = request.files.get("upload_file")
    if not file or not file.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("masters.brands"))

    try:
        rows = read_upload_rows(file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("masters.brands"))

    added = 0
    skipped = 0
    for row in rows:
        company_name = get_cell(row, "company name", "company")
        brand_name = get_cell(row, "brand name", "brand")
        if not company_name or not brand_name:
            skipped += 1
            continue

        company = _get_or_create_company(company_name)
        if Brand.query.filter_by(company_id=company.id, name=brand_name).first():
            skipped += 1
            continue

        db.session.add(Brand(company_id=company.id, name=brand_name))
        added += 1

    db.session.commit()
    log_activity("bulk_upload", "brands", f"Bulk upload brands: {added} added, {skipped} skipped")
    flash(f"Bulk upload complete: {added} added, {skipped} skipped.", "success")
    return redirect(url_for("masters.brands"))


# --- Supplier Categories ---


@masters_bp.route("/supplier-categories", methods=["GET", "POST"])
@login_required
@admin_required
def supplier_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            if SupplierCategory.query.filter_by(name=name).first():
                flash("Category already exists.", "warning")
            else:
                db.session.add(SupplierCategory(name=name))
                db.session.commit()
                log_activity("create", "supplier_categories", f"Added supplier category {name}", name)
                flash("Supplier category added.", "success")
        return redirect(url_for("masters.supplier_categories"))

    categories = SupplierCategory.query.order_by(SupplierCategory.name).all()
    return render_template("masters/supplier_categories.html", categories=categories)


@masters_bp.route("/supplier-categories/<int:cat_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_supplier_category(cat_id):
    cat = db.get_or_404(SupplierCategory, cat_id)
    if cat.suppliers:
        flash("Cannot delete category with linked suppliers.", "danger")
    else:
        db.session.delete(cat)
        db.session.commit()
        log_activity("delete", "supplier_categories", f"Deleted supplier category {cat.name}", cat.name)
        flash("Category deleted.", "success")
    return redirect(url_for("masters.supplier_categories"))


# --- Suppliers ---


@masters_bp.route("/suppliers", methods=["GET", "POST"])
@login_required
@admin_required
def suppliers():
    categories = SupplierCategory.query.order_by(SupplierCategory.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        opening_balance = float(request.form.get("opening_balance") or 0)
        category_id = request.form.get("category_id") or None
        if category_id:
            category_id = int(category_id)
        if name:
            db.session.add(
                Supplier(
                    name=name,
                    contact=contact or None,
                    email=email or None,
                    address=address or None,
                    opening_balance=opening_balance,
                    category_id=category_id,
                )
            )
            db.session.commit()
            log_activity("create", "suppliers", f"Added supplier {name}", name)
            flash("Supplier added.", "success")
        return redirect(url_for("masters.suppliers"))

    suppliers_list = Supplier.query.order_by(Supplier.name).all()
    return render_template(
        "masters/suppliers.html", suppliers=suppliers_list, categories=categories
    )


@masters_bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    categories = SupplierCategory.query.order_by(SupplierCategory.name).all()
    if request.method == "POST":
        supplier.name = request.form.get("name", "").strip()
        supplier.contact = request.form.get("contact", "").strip() or None
        supplier.email = request.form.get("email", "").strip() or None
        supplier.address = request.form.get("address", "").strip() or None
        supplier.opening_balance = float(request.form.get("opening_balance") or 0)
        category_id = request.form.get("category_id") or None
        supplier.category_id = int(category_id) if category_id else None
        db.session.commit()
        log_activity("update", "suppliers", f"Updated supplier {supplier.name}", supplier.name)
        flash("Supplier updated.", "success")
        return redirect(url_for("masters.suppliers"))
    return render_template(
        "masters/edit_supplier.html", supplier=supplier, categories=categories
    )


@masters_bp.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_supplier(supplier_id):
    supplier = db.get_or_404(Supplier, supplier_id)
    if supplier.bills or supplier.payments:
        flash("Cannot delete supplier with transactions.", "danger")
    else:
        db.session.delete(supplier)
        db.session.commit()
        log_activity("delete", "suppliers", f"Deleted supplier {supplier.name}", supplier.name)
        flash("Supplier deleted.", "success")
    return redirect(url_for("masters.suppliers"))


@masters_bp.route("/suppliers/bulk-template")
@login_required
@admin_required
def suppliers_bulk_template():
    path = BULK_TEMPLATE_DIR / "supplier_upload_template.xlsx"
    if not path.exists():
        buffer = build_workbook(
            ["Name", "Opening Balance", "Contact", "Email", "Address", "Category"],
            [
                ["ABC Distributors", 15000, "9876543210", "abc@example.com", "12 Market Road, City", "Grocery"],
                ["XYZ Wholesale", 8500, "9123456780", "xyz@example.com", "45 Industrial Area", "Dairy"],
            ],
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name="supplier_upload_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return send_file(path, as_attachment=True, download_name="supplier_upload_template.xlsx")


@masters_bp.route("/suppliers/bulk-template-csv")
@login_required
@admin_required
def suppliers_bulk_template_csv():
    path = BULK_TEMPLATE_DIR / "supplier_upload_template.csv"
    return send_file(path, as_attachment=True, download_name="supplier_upload_template.csv", mimetype="text/csv")


@masters_bp.route("/suppliers/bulk-upload", methods=["POST"])
@login_required
@admin_required
def suppliers_bulk_upload():
    file = request.files.get("upload_file")
    if not file or not file.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("masters.suppliers"))

    try:
        rows = read_upload_rows(file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("masters.suppliers"))

    added = 0
    skipped = 0
    for row in rows:
        name = get_cell(row, "name", "supplier name", "supplier")
        if not name:
            skipped += 1
            continue

        if Supplier.query.filter_by(name=name).first():
            skipped += 1
            continue

        contact = get_cell(row, "contact", "phone", "mobile")
        email = get_cell(row, "email", "email id", "e-mail")
        address = get_cell(row, "address")
        opening_balance = parse_float_cell(row, "opening balance", "opening bal", "balance")
        category_name = get_cell(row, "category", "supplier category")
        category = _get_category_by_name(category_name)

        db.session.add(
            Supplier(
                name=name,
                contact=contact or None,
                email=email or None,
                address=address or None,
                opening_balance=opening_balance,
                category_id=category.id if category else None,
            )
        )
        added += 1

    db.session.commit()
    log_activity("bulk_upload", "suppliers", f"Bulk upload suppliers: {added} added, {skipped} skipped")
    flash(f"Bulk upload complete: {added} added, {skipped} skipped.", "success")
    return redirect(url_for("masters.suppliers"))
def _get_or_create_expense_group(name: str) -> ExpenseGroup:
    group = ExpenseGroup.query.filter_by(name=name).first()
    if not group:
        group = ExpenseGroup(name=name)
        db.session.add(group)
        db.session.flush()
    return group


# --- Expense Groups ---


@masters_bp.route("/expense-groups", methods=["GET", "POST"])
@login_required
@admin_required
def expense_groups():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            if ExpenseGroup.query.filter_by(name=name).first():
                flash("Expense group already exists.", "warning")
            else:
                db.session.add(ExpenseGroup(name=name))
                db.session.commit()
                log_activity("create", "expense_groups", f"Added expense group {name}", name)
                flash("Expense group added.", "success")
        return redirect(url_for("masters.expense_groups"))

    groups = ExpenseGroup.query.order_by(ExpenseGroup.name).all()
    return render_template("masters/expense_groups.html", groups=groups)


@masters_bp.route("/expense-groups/<int:group_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_expense_group(group_id):
    group = db.get_or_404(ExpenseGroup, group_id)
    if group.categories:
        flash("Cannot delete group with linked expense categories.", "danger")
    else:
        db.session.delete(group)
        db.session.commit()
        log_activity("delete", "expense_groups", f"Deleted expense group {group.name}", group.name)
        flash("Expense group deleted.", "success")
    return redirect(url_for("masters.expense_groups"))


# --- Expense Categories ---


@masters_bp.route("/expense-categories", methods=["GET", "POST"])
@login_required
@admin_required
def expense_categories():
    groups = ExpenseGroup.query.order_by(ExpenseGroup.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        group_id = request.form.get("group_id") or None
        if name and group_id:
            if ExpenseCategory.query.filter_by(name=name).first():
                flash("Category already exists.", "warning")
            else:
                db.session.add(
                    ExpenseCategory(name=name, group_id=int(group_id))
                )
                db.session.commit()
                log_activity("create", "expense_categories", f"Added expense category {name}", name)
                flash("Expense category added.", "success")
        else:
            flash("Category name and expense group are required.", "danger")
        return redirect(url_for("masters.expense_categories"))

    categories = (
        ExpenseCategory.query.join(ExpenseGroup, isouter=True)
        .order_by(ExpenseCategory.name)
        .all()
    )
    return render_template(
        "masters/expense_categories.html", categories=categories, groups=groups
    )


@masters_bp.route("/expense-categories/bulk-template")
@login_required
@admin_required
def expense_categories_bulk_template():
    path = BULK_TEMPLATE_DIR / "expense_category_upload_template.xlsx"
    if not path.exists():
        buffer = build_workbook(
            ["Category Name", "Expense Group"],
            [
                ["Rent", "Fixed Expenses"],
                ["Electricity", "Utilities"],
                ["Staff Salary", "Payroll"],
                ["Transport", "Operations"],
                ["Packaging", "Operations"],
                ["Maintenance", "Operations"],
                ["Bank Charges", "Finance"],
            ],
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name="expense_category_upload_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return send_file(path, as_attachment=True, download_name="expense_category_upload_template.xlsx")


@masters_bp.route("/expense-categories/bulk-template-csv")
@login_required
@admin_required
def expense_categories_bulk_template_csv():
    path = BULK_TEMPLATE_DIR / "expense_category_upload_template.csv"
    return send_file(
        path,
        as_attachment=True,
        download_name="expense_category_upload_template.csv",
        mimetype="text/csv",
    )


@masters_bp.route("/expense-categories/bulk-upload", methods=["POST"])
@login_required
@admin_required
def expense_categories_bulk_upload():
    file = request.files.get("upload_file")
    if not file or not file.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("masters.expense_categories"))

    try:
        rows = read_upload_rows(file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("masters.expense_categories"))

    added = 0
    skipped = 0
    for row in rows:
        name = get_cell(row, "category name", "name", "category", "expense category")
        group_name = get_cell(row, "expense group", "group", "group name")
        if not name or not group_name:
            skipped += 1
            continue

        if ExpenseCategory.query.filter_by(name=name).first():
            skipped += 1
            continue

        group = _get_or_create_expense_group(group_name)
        db.session.add(ExpenseCategory(name=name, group_id=group.id))
        added += 1

    db.session.commit()
    log_activity("bulk_upload", "expense_categories", f"Bulk upload expense categories: {added} added, {skipped} skipped")
    flash(f"Bulk upload complete: {added} added, {skipped} skipped.", "success")
    return redirect(url_for("masters.expense_categories"))
@masters_bp.route("/expense-categories/<int:cat_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_expense_category(cat_id):
    cat = db.get_or_404(ExpenseCategory, cat_id)
    if cat.expenses:
        flash("Cannot delete category with expense entries.", "danger")
    else:
        db.session.delete(cat)
        db.session.commit()
        log_activity("delete", "expense_categories", f"Deleted expense category {cat.name}", cat.name)
        flash("Category deleted.", "success")
    return redirect(url_for("masters.expense_categories"))


# --- Bank Accounts ---


@masters_bp.route("/bank-accounts", methods=["GET", "POST"])
@login_required
@admin_required
def bank_accounts():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        account_type = request.form.get("account_type", "bank")
        opening_amount = float(request.form.get("opening_balance") or 0)
        as_on = parse_date(request.form.get("as_on_date")) or date.today()
        if name and account_type in ("bank", "cash"):
            if BankAccount.query.filter_by(name=name).first():
                flash("Account already exists.", "warning")
            else:
                account = BankAccount(name=name, account_type=account_type)
                db.session.add(account)
                db.session.flush()
                if opening_amount:
                    db.session.add(
                        OpeningBalance(
                            account_type=account_type,
                            bank_account_id=account.id,
                            amount=opening_amount,
                            as_on_date=as_on,
                        )
                    )
                db.session.commit()
                log_activity("create", "bank_accounts", f"Added account {name}", name)
                flash("Account added.", "success")
        return redirect(url_for("masters.bank_accounts"))

    accounts = BankAccount.query.order_by(BankAccount.account_type, BankAccount.name).all()
    openings = {}
    for acc in accounts:
        ob = (
            OpeningBalance.query.filter_by(bank_account_id=acc.id)
            .order_by(OpeningBalance.as_on_date.desc())
            .first()
        )
        openings[acc.id] = ob
    return render_template(
        "masters/bank_accounts.html", accounts=accounts, openings=openings
    )


@masters_bp.route("/bank-accounts/<int:account_id>/toggle", methods=["POST"])
@login_required
@admin_required
def toggle_bank_account(account_id):
    account = db.get_or_404(BankAccount, account_id)
    account.is_active = not account.is_active
    db.session.commit()
    log_activity("update", "bank_accounts", f"Updated bank/cash account {account.name}", account.name)
    flash("Bank account updated.", "success")
    return redirect(url_for("masters.bank_accounts"))


@masters_bp.route("/bank-accounts/bulk-template")
@login_required
@admin_required
def bank_accounts_bulk_template():
    path = BULK_TEMPLATE_DIR / "bank_account_upload_template.xlsx"
    if not path.exists():
        buffer = build_workbook(
            ["Account Name", "Account Type", "Opening Balance", "As On Date"],
            [
                ["Cash", "Cash", 50000, "2026-07-01"],
                ["HDFC Current", "Bank", 250000, "2026-07-01"],
                ["SBI Savings", "Bank", 120000, "2026-07-01"],
            ],
        )
        return send_file(
            buffer,
            as_attachment=True,
            download_name="bank_account_upload_template.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return send_file(path, as_attachment=True, download_name="bank_account_upload_template.xlsx")


@masters_bp.route("/bank-accounts/bulk-template-csv")
@login_required
@admin_required
def bank_accounts_bulk_template_csv():
    path = BULK_TEMPLATE_DIR / "bank_account_upload_template.csv"
    return send_file(
        path,
        as_attachment=True,
        download_name="bank_account_upload_template.csv",
        mimetype="text/csv",
    )


@masters_bp.route("/bank-accounts/bulk-upload", methods=["POST"])
@login_required
@admin_required
def bank_accounts_bulk_upload():
    file = request.files.get("upload_file")
    if not file or not file.filename:
        flash("Please choose a file to upload.", "danger")
        return redirect(url_for("masters.bank_accounts"))

    try:
        rows = read_upload_rows(file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("masters.bank_accounts"))

    added = 0
    skipped = 0
    for row in rows:
        name = get_cell(row, "bank account name", "bank account", "account name", "name")
        type_raw = (get_cell(row, "account type", "type") or "bank").strip().lower()
        account_type = "cash" if type_raw.startswith("cash") else "bank"
        if not name:
            skipped += 1
            continue

        if BankAccount.query.filter_by(name=name).first():
            skipped += 1
            continue

        opening_amount = parse_float_cell(row, "opening balance", "opening bal", "balance")
        as_on = parse_date(get_cell(row, "as on date", "as on", "date")) or date.today()

        account = BankAccount(name=name, account_type=account_type)
        db.session.add(account)
        db.session.flush()
        if opening_amount:
            db.session.add(
                OpeningBalance(
                    account_type=account_type,
                    bank_account_id=account.id,
                    amount=opening_amount,
                    as_on_date=as_on,
                )
            )
        added += 1

    db.session.commit()
    log_activity("bulk_upload", "bank_accounts", f"Bulk upload bank/cash accounts: {added} added, {skipped} skipped")
    flash(f"Bulk upload complete: {added} added, {skipped} skipped.", "success")
    return redirect(url_for("masters.bank_accounts"))
# --- Opening Balances ---


@masters_bp.route("/opening-balances", methods=["GET", "POST"])
@login_required
@admin_required
def opening_balances():
    accounts = BankAccount.query.filter_by(is_active=True).order_by(BankAccount.name).all()
    if request.method == "POST":
        as_on = parse_date(request.form.get("as_on_date"))
        if not as_on:
            flash("Valid date is required.", "danger")
            return redirect(url_for("masters.opening_balances"))

        for account in accounts:
            amount = float(request.form.get(f"account_{account.id}") or 0)
            db.session.add(
                OpeningBalance(
                    account_type=account.account_type,
                    bank_account_id=account.id,
                    amount=amount,
                    as_on_date=as_on,
                )
            )
        db.session.commit()
        log_activity("update", "opening_balances", "Saved opening balances")
        flash("Opening balances saved.", "success")
        return redirect(url_for("masters.opening_balances"))

    latest = OpeningBalance.query.order_by(OpeningBalance.as_on_date.desc()).first()
    return render_template("masters/opening_balances.html", accounts=accounts, latest=latest)
