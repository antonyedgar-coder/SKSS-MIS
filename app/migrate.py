from sqlalchemy import inspect, text

from app.extensions import db


def _migrate_db():
    """Apply lightweight schema updates for existing SQLite databases."""
    db.create_all()
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    if "suppliers" in table_names:
        supplier_cols = {c["name"] for c in inspector.get_columns("suppliers")}
        if "email" not in supplier_cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE suppliers ADD COLUMN email VARCHAR(200)"))
        if "address" not in supplier_cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE suppliers ADD COLUMN address VARCHAR(500)"))
        if "opening_balance" not in supplier_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE suppliers ADD COLUMN opening_balance FLOAT NOT NULL DEFAULT 0")
                )

    if "brands" in table_names:
        brand_cols = {c["name"] for c in inspector.get_columns("brands")}
        if "company_id" not in brand_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE brands ADD COLUMN company_id INTEGER REFERENCES companies(id)")
                )

    if "users" in table_names:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "is_active" not in user_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
                )

    if "supplier_bills" in table_names:
        bill_cols = {c["name"] for c in inspector.get_columns("supplier_bills")}
        bill_migrations = {
            "purchase_order_id": "INTEGER REFERENCES purchase_orders(id)",
            "ordered_amount": "FLOAT",
            "variation_status": "VARCHAR(20) DEFAULT 'none'",
            "variation_closed_by_id": "INTEGER REFERENCES users(id)",
            "variation_closed_at": "DATETIME",
            "approver_remarks": "VARCHAR(500)",
        }
        for col, col_type in bill_migrations.items():
            if col not in bill_cols:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE supplier_bills ADD COLUMN {col} {col_type}"))

    if "supplier_payments" in table_names:
        payment_cols = {c["name"] for c in inspector.get_columns("supplier_payments")}
        if "payment_number" not in payment_cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE supplier_payments ADD COLUMN payment_number VARCHAR(30)"))
        _backfill_supplier_payment_numbers()

    if "expense_payments" in table_names:
        expense_cols = {c["name"] for c in inspector.get_columns("expense_payments")}
        if "payment_number" not in expense_cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE expense_payments ADD COLUMN payment_number VARCHAR(30)"))
        _backfill_expense_payment_numbers()

    if "expense_categories" in table_names:
        category_cols = {c["name"] for c in inspector.get_columns("expense_categories")}
        if "group_id" not in category_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE expense_categories ADD COLUMN group_id INTEGER REFERENCES expense_groups(id)")
                )

    if "bank_accounts" in table_names:
        bank_cols = {c["name"] for c in inspector.get_columns("bank_accounts")}
        if "account_type" not in bank_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE bank_accounts ADD COLUMN account_type VARCHAR(10) NOT NULL DEFAULT 'bank'")
                )
        _ensure_default_cash_account()
        _backfill_payment_accounts()

    if "cash_bank_inflows" in table_names:
        inflow_cols = {c["name"] for c in inspector.get_columns("cash_bank_inflows")}
        if "receipt_type" not in inflow_cols:
            with db.engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE cash_bank_inflows ADD COLUMN receipt_type VARCHAR(20) NOT NULL DEFAULT 'sales_collection'"
                    )
                )
        _backfill_inflow_accounts()

    _ensure_default_company_and_brand()


def _ensure_default_cash_account():
    from app.models import BankAccount

    cash_account = BankAccount.query.filter_by(account_type="cash").first()
    if not cash_account:
        existing = BankAccount.query.filter_by(name="Cash").first()
        if existing:
            existing.account_type = "cash"
        else:
            db.session.add(BankAccount(name="Cash", account_type="cash", is_active=True))
        db.session.commit()


def _backfill_payment_accounts():
    from app.models import BankAccount, ExpensePayment, SupplierPayment

    cash_id = None
    cash_account = BankAccount.query.filter_by(account_type="cash").order_by(BankAccount.id).first()
    if cash_account:
        cash_id = cash_account.id

    for payment in SupplierPayment.query.filter(
        (SupplierPayment.bank_account_id.is_(None)) | (SupplierPayment.bank_account_id == 0)
    ).all():
        if payment.payment_mode == "cash" and cash_id:
            payment.bank_account_id = cash_id
        elif payment.payment_mode == "bank" and not payment.bank_account_id:
            first_bank = BankAccount.query.filter_by(account_type="bank", is_active=True).first()
            if first_bank:
                payment.bank_account_id = first_bank.id
        db.session.add(payment)

    for payment in ExpensePayment.query.filter(
        (ExpensePayment.bank_account_id.is_(None)) | (ExpensePayment.bank_account_id == 0)
    ).all():
        if payment.payment_mode == "cash" and cash_id:
            payment.bank_account_id = cash_id
        elif payment.payment_mode == "bank" and not payment.bank_account_id:
            first_bank = BankAccount.query.filter_by(account_type="bank", is_active=True).first()
            if first_bank:
                payment.bank_account_id = first_bank.id
        db.session.add(payment)

    db.session.commit()


def _backfill_inflow_accounts():
    from app.models import BankAccount, CashBankInflow

    cash_account = BankAccount.query.filter_by(account_type="cash").order_by(BankAccount.id).first()
    if not cash_account:
        return

    updated = False
    for inflow in CashBankInflow.query.filter(
        (CashBankInflow.bank_account_id.is_(None)) | (CashBankInflow.bank_account_id == 0)
    ).all():
        if inflow.payment_mode == "bank":
            first_bank = BankAccount.query.filter_by(account_type="bank", is_active=True).first()
            inflow.bank_account_id = first_bank.id if first_bank else cash_account.id
        else:
            inflow.bank_account_id = cash_account.id
        db.session.add(inflow)
        updated = True
    if updated:
        db.session.commit()


def _backfill_supplier_payment_numbers():
    from app.models import SupplierPayment
    from app.utils import generate_payment_number

    payments = (
        SupplierPayment.query.order_by(SupplierPayment.payment_date, SupplierPayment.id).all()
    )
    to_update = [
        p
        for p in payments
        if not p.payment_number or not str(p.payment_number).startswith("sup-")
    ]
    for payment in to_update:
        payment.payment_number = generate_payment_number(payment.payment_date)
        db.session.add(payment)
    if to_update:
        db.session.commit()


def _backfill_expense_payment_numbers():
    from app.models import ExpensePayment
    from app.utils import generate_expense_payment_number

    payments = (
        ExpensePayment.query.order_by(ExpensePayment.payment_date, ExpensePayment.id).all()
    )
    to_update = [
        p
        for p in payments
        if not p.payment_number or not str(p.payment_number).startswith("exp-")
    ]
    for payment in to_update:
        payment.payment_number = generate_expense_payment_number(payment.payment_date)
        db.session.add(payment)
    if to_update:
        db.session.commit()


def _ensure_default_company_and_brand():
    from app.models import Brand, Company

    default_company = Company.query.filter_by(name="General").first()
    if not default_company:
        default_company = Company(name="General")
        db.session.add(default_company)
        db.session.commit()

    brands_without_company = Brand.query.filter(
        (Brand.company_id.is_(None)) | (Brand.company_id == 0)
    ).all()
    for brand in brands_without_company:
        brand.company_id = default_company.id

    if not Brand.query.first():
        db.session.add(Brand(name="General", company_id=default_company.id))
    else:
        general_brand = Brand.query.filter_by(name="General").first()
        if general_brand and not general_brand.company_id:
            general_brand.company_id = default_company.id

    db.session.commit()

    with db.engine.begin() as conn:
        conn.execute(text("UPDATE supplier_bills SET brand_id = 1 WHERE brand_id IS NULL"))
        conn.execute(text("UPDATE supplier_payments SET brand_id = 1 WHERE brand_id IS NULL"))
        if "purchase_returns" in inspect(db.engine).get_table_names():
            conn.execute(text("UPDATE purchase_returns SET brand_id = 1 WHERE brand_id IS NULL"))
