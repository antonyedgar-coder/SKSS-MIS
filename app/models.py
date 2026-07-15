from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_approver(self) -> bool:
        return self.role in ("admin", "approver")

    permissions = db.relationship(
        "UserModulePermission", back_populates="user", cascade="all, delete-orphan", lazy=True
    )


class UserModulePermission(db.Model):
    __tablename__ = "user_module_permissions"
    __table_args__ = (db.UniqueConstraint("user_id", "module", name="uq_user_module"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    module = db.Column(db.String(40), nullable=False)
    can_view = db.Column(db.Boolean, default=False, nullable=False)
    can_create = db.Column(db.Boolean, default=False, nullable=False)
    can_edit = db.Column(db.Boolean, default=False, nullable=False)
    can_delete = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="permissions")


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    module = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    record_ref = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", backref="activity_logs", lazy=True)


class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    brands = db.relationship("Brand", back_populates="company", lazy=True)


class Brand(db.Model):
    __tablename__ = "brands"
    __table_args__ = (db.UniqueConstraint("company_id", "name", name="uq_company_brand"),)

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    company = db.relationship("Company", back_populates="brands")
    bills = db.relationship("SupplierBill", back_populates="brand", lazy=True)
    payments = db.relationship("SupplierPayment", back_populates="brand", lazy=True)
    purchase_returns = db.relationship("PurchaseReturn", back_populates="brand", lazy=True)


class SupplierCategory(db.Model):
    __tablename__ = "supplier_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    suppliers = db.relationship("Supplier", back_populates="category", lazy=True)


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(200))
    email = db.Column(db.String(200))
    address = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey("supplier_categories.id"))
    opening_balance = db.Column(db.Float, nullable=False, default=0)
    category = db.relationship("SupplierCategory", back_populates="suppliers")
    bills = db.relationship("SupplierBill", back_populates="supplier", lazy=True)
    payments = db.relationship("SupplierPayment", back_populates="supplier", lazy=True)
    purchase_returns = db.relationship("PurchaseReturn", back_populates="supplier", lazy=True)
    purchase_orders = db.relationship("PurchaseOrder", back_populates="supplier", lazy=True)


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.Date, nullable=False)
    order_number = db.Column(db.String(25), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    ordered_amount = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    supplier = db.relationship("Supplier", back_populates="purchase_orders")
    brand = db.relationship("Brand")
    created_by = db.relationship("User")
    bill = db.relationship("SupplierBill", back_populates="purchase_order", uselist=False)


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    receipts = db.relationship("CashBankInflow", back_populates="branch", lazy=True)


class ExpenseGroup(db.Model):
    __tablename__ = "expense_groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    categories = db.relationship("ExpenseCategory", back_populates="group", lazy=True)


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("expense_groups.id"))
    group = db.relationship("ExpenseGroup", back_populates="categories")
    expenses = db.relationship("ExpensePayment", back_populates="category", lazy=True)


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    account_type = db.Column(db.String(10), nullable=False, default="bank")
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class SupplierBill(db.Model):
    __tablename__ = "supplier_bills"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), unique=True)
    bill_date = db.Column(db.Date, nullable=False)
    bill_no = db.Column(db.String(100), nullable=False)
    ordered_amount = db.Column(db.Float)
    total_amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(500))
    variation_status = db.Column(db.String(20), default="none")
    variation_closed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    variation_closed_at = db.Column(db.DateTime)
    approver_remarks = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", back_populates="bills")
    brand = db.relationship("Brand", back_populates="bills")
    purchase_order = db.relationship("PurchaseOrder", back_populates="bill")
    variation_closed_by = db.relationship("User")

    @property
    def variation_amount(self) -> float:
        if self.ordered_amount is None:
            return 0.0
        return float(self.total_amount) - float(self.ordered_amount)

    @property
    def has_variation(self) -> bool:
        return abs(self.variation_amount) >= 0.01


class SupplierPayment(db.Model):
    __tablename__ = "supplier_payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(30), unique=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(10), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier", back_populates="payments")
    brand = db.relationship("Brand", back_populates="payments")
    bank_account = db.relationship("BankAccount")


class PurchaseReturn(db.Model):
    __tablename__ = "purchase_returns"

    id = db.Column(db.Integer, primary_key=True)
    return_date = db.Column(db.Date, nullable=False)
    return_number = db.Column(db.String(25), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey("brands.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    supplier = db.relationship("Supplier", back_populates="purchase_returns")
    brand = db.relationship("Brand", back_populates="purchase_returns")
    created_by = db.relationship("User")


class ExpensePayment(db.Model):
    __tablename__ = "expense_payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(30), unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payee = db.Column(db.String(200))
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(10), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship("ExpenseCategory", back_populates="expenses")
    bank_account = db.relationship("BankAccount")


class CashBankInflow(db.Model):
    __tablename__ = "cash_bank_inflows"

    id = db.Column(db.Integer, primary_key=True)
    inflow_date = db.Column(db.Date, nullable=False)
    receipt_type = db.Column(db.String(20), nullable=False, default="sales_collection")
    description = db.Column(db.String(300))
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(10), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"))
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"), nullable=False)
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    branch = db.relationship("Branch", back_populates="receipts")
    bank_account = db.relationship("BankAccount")


class OpeningBalance(db.Model):
    __tablename__ = "opening_balances"

    id = db.Column(db.Integer, primary_key=True)
    account_type = db.Column(db.String(10), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey("bank_accounts.id"))
    amount = db.Column(db.Float, nullable=False, default=0)
    as_on_date = db.Column(db.Date, nullable=False)
    bank_account = db.relationship("BankAccount")


class MonthlyBudget(db.Model):
    __tablename__ = "monthly_budgets"
    __table_args__ = (db.UniqueConstraint("year", "month", name="uq_budget_year_month"),)

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    purchase_amount = db.Column(db.Float, nullable=False, default=0)  # legacy; use purchase_lines
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    receipt_lines = db.relationship(
        "BudgetReceiptLine", back_populates="budget", cascade="all, delete-orphan", lazy=True
    )
    purchase_lines = db.relationship(
        "BudgetPurchaseLine", back_populates="budget", cascade="all, delete-orphan", lazy=True
    )
    expense_lines = db.relationship(
        "BudgetExpenseLine", back_populates="budget", cascade="all, delete-orphan", lazy=True
    )


class BudgetReceiptLine(db.Model):
    __tablename__ = "budget_receipt_lines"
    __table_args__ = (db.UniqueConstraint("budget_id", "branch_id", name="uq_budget_branch"),)

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("monthly_budgets.id"), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)

    budget = db.relationship("MonthlyBudget", back_populates="receipt_lines")
    branch = db.relationship("Branch")


class BudgetPurchaseLine(db.Model):
    __tablename__ = "budget_purchase_lines"
    __table_args__ = (
        db.UniqueConstraint("budget_id", "supplier_category_id", name="uq_budget_supplier_category"),
    )

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("monthly_budgets.id"), nullable=False)
    supplier_category_id = db.Column(
        db.Integer, db.ForeignKey("supplier_categories.id"), nullable=False
    )
    amount = db.Column(db.Float, nullable=False, default=0)

    budget = db.relationship("MonthlyBudget", back_populates="purchase_lines")
    supplier_category = db.relationship("SupplierCategory")


class BudgetExpenseLine(db.Model):
    __tablename__ = "budget_expense_lines"
    __table_args__ = (db.UniqueConstraint("budget_id", "expense_group_id", name="uq_budget_expense_group"),)

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("monthly_budgets.id"), nullable=False)
    expense_group_id = db.Column(db.Integer, db.ForeignKey("expense_groups.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)

    budget = db.relationship("MonthlyBudget", back_populates="expense_lines")
    expense_group = db.relationship("ExpenseGroup")
