from __future__ import annotations

from datetime import date
from functools import wraps

from flask import abort
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Branch,
    BudgetExpenseLine,
    BudgetPurchaseLine,
    BudgetReceiptLine,
    CashBankInflow,
    ExpenseCategory,
    ExpenseGroup,
    ExpensePayment,
    MonthlyBudget,
    OpeningBalance,
    PurchaseOrder,
    PurchaseReturn,
    Supplier,
    SupplierBill,
    SupplierCategory,
    SupplierPayment,
)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated


def approver_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_approver:
            abort(403)
        return f(*args, **kwargs)

    return decorated


def generate_order_number(order_date: date) -> str:
    prefix = order_date.strftime("%b-%Y")  # e.g. Jul-2026
    pattern = f"{prefix}-%"
    orders = PurchaseOrder.query.filter(PurchaseOrder.order_number.like(pattern)).all()
    max_seq = 0
    for order in orders:
        try:
            seq = int(order.order_number.rsplit("-", 1)[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{max_seq + 1:04d}"


def _max_sequence_for_prefix(model, number_field, prefix: str) -> int:
    pattern = f"{prefix}-%"
    records = model.query.filter(getattr(model, number_field).like(pattern)).all()
    max_seq = 0
    for record in records:
        number = getattr(record, number_field)
        if not number:
            continue
        try:
            seq = int(number.rsplit("-", 1)[-1])
            max_seq = max(max_seq, seq)
        except (ValueError, IndexError):
            continue
    return max_seq


def generate_payment_number(payment_date: date) -> str:
    prefix = f"sup-{payment_date.strftime('%b-%Y')}"
    max_seq = _max_sequence_for_prefix(SupplierPayment, "payment_number", prefix)
    return f"{prefix}-{max_seq + 1:04d}"


def generate_expense_payment_number(payment_date: date) -> str:
    from app.models import ExpensePayment

    prefix = f"exp-{payment_date.strftime('%b-%Y')}"
    max_seq = _max_sequence_for_prefix(ExpensePayment, "payment_number", prefix)
    return f"{prefix}-{max_seq + 1:04d}"


def generate_return_number(return_date: date) -> str:
    prefix = return_date.strftime("%b-%Y")
    max_seq = _max_sequence_for_prefix(PurchaseReturn, "return_number", prefix)
    return f"{prefix}-{max_seq + 1:04d}"


def variation_status_for_amounts(ordered: float, purchased: float) -> str:
    if abs(purchased - ordered) < 0.01:
        return "none"
    return "pending"


def parse_date(value: str) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def payment_mode_label(mode: str, bank_name: str | None = None) -> str:
    if bank_name:
        return bank_name
    return "Cash"


def parse_payment_account(value: str) -> tuple[str | None, int | None]:
    account_id = parse_account_id(value)
    if not account_id:
        return None, None
    from app.models import BankAccount

    account = db.session.get(BankAccount, account_id)
    if not account or not account.is_active:
        return None, None
    return account.account_type or "bank", account.id


def parse_account_id(value: str) -> int | None:
    if not value:
        return None
    if value == "cash":
        return get_default_cash_account_id()
    if value.startswith("bank-"):
        try:
            return int(value.split("-", 1)[1])
        except (ValueError, IndexError):
            return None
    if value.startswith("account-"):
        try:
            return int(value.split("-", 1)[1])
        except (ValueError, IndexError):
            return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def get_default_cash_account_id() -> int | None:
    from app.models import BankAccount

    account = BankAccount.query.filter_by(account_type="cash", is_active=True).order_by(BankAccount.id).first()
    return account.id if account else None


def account_display_name(account) -> str:
    if not account:
        return "-"
    return account.name


def receipt_type_label(receipt_type: str) -> str:
    if receipt_type == "cash":
        return "Cash Deposit / Petty Cash"
    return "Sales Collection"


def payment_account_label(payment_mode: str, bank_name: str | None = None) -> str:
    return payment_mode_label(payment_mode, bank_name)


def expense_payment_particulars(payment) -> str:
    if payment.bank_account:
        return payment.bank_account.name
    return "Cash"


def _bill_filters(supplier_id: int, brand_id: int | None = None):
    filters = [SupplierBill.supplier_id == supplier_id]
    if brand_id is not None:
        filters.append(SupplierBill.brand_id == brand_id)
    return filters


def _payment_filters(supplier_id: int, brand_id: int | None = None):
    filters = [SupplierPayment.supplier_id == supplier_id]
    if brand_id is not None:
        filters.append(SupplierPayment.brand_id == brand_id)
    return filters


def _return_filters(supplier_id: int, brand_id: int | None = None):
    filters = [PurchaseReturn.supplier_id == supplier_id]
    if brand_id is not None:
        filters.append(PurchaseReturn.brand_id == brand_id)
    return filters


def _sum_returns(supplier_id: int, brand_id: int | None, from_date: date | None, to_date: date | None):
    query = db.session.query(func.coalesce(func.sum(PurchaseReturn.amount), 0)).filter(
        *_return_filters(supplier_id, brand_id)
    )
    if from_date is not None:
        query = query.filter(PurchaseReturn.return_date >= from_date)
    if to_date is not None:
        query = query.filter(PurchaseReturn.return_date <= to_date)
    return float(query.scalar())


def supplier_totals(supplier_id: int, as_on: date, brand_id: int | None = None):
    from app.models import Supplier

    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(*_bill_filters(supplier_id, brand_id), SupplierBill.bill_date <= as_on)
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(*_payment_filters(supplier_id, brand_id), SupplierPayment.payment_date <= as_on)
        .scalar()
    )
    returns = _sum_returns(supplier_id, brand_id, None, as_on)
    opening = 0.0
    if brand_id is None:
        supplier = db.session.get(Supplier, supplier_id)
        opening = float(supplier.opening_balance) if supplier else 0.0
    return float(purchases), float(paid), opening + float(purchases) - float(paid) - returns


def supplier_period_totals(supplier_id: int, from_date: date, to_date: date, brand_id: int | None = None):
    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(
            *_bill_filters(supplier_id, brand_id),
            SupplierBill.bill_date >= from_date,
            SupplierBill.bill_date <= to_date,
        )
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(
            *_payment_filters(supplier_id, brand_id),
            SupplierPayment.payment_date >= from_date,
            SupplierPayment.payment_date <= to_date,
        )
        .scalar()
    )
    returns = _sum_returns(supplier_id, brand_id, from_date, to_date)
    credit = float(purchases)
    debit = float(paid) + returns
    return credit, debit, credit - debit


def get_supplier_brand_pairs():
    bill_pairs = db.session.query(SupplierBill.supplier_id, SupplierBill.brand_id).distinct().all()
    payment_pairs = (
        db.session.query(SupplierPayment.supplier_id, SupplierPayment.brand_id).distinct().all()
    )
    return_pairs = (
        db.session.query(PurchaseReturn.supplier_id, PurchaseReturn.brand_id).distinct().all()
    )
    return sorted(set(bill_pairs) | set(payment_pairs) | set(return_pairs))


def get_supplier_brand_pairs_in_period(from_date: date, to_date: date):
    bill_pairs = (
        db.session.query(SupplierBill.supplier_id, SupplierBill.brand_id)
        .filter(SupplierBill.bill_date >= from_date, SupplierBill.bill_date <= to_date)
        .distinct()
        .all()
    )
    payment_pairs = (
        db.session.query(SupplierPayment.supplier_id, SupplierPayment.brand_id)
        .filter(
            SupplierPayment.payment_date >= from_date,
            SupplierPayment.payment_date <= to_date,
        )
        .distinct()
        .all()
    )
    return_pairs = (
        db.session.query(PurchaseReturn.supplier_id, PurchaseReturn.brand_id)
        .filter(
            PurchaseReturn.return_date >= from_date,
            PurchaseReturn.return_date <= to_date,
        )
        .distinct()
        .all()
    )
    return sorted(set(bill_pairs) | set(payment_pairs) | set(return_pairs))


def supplier_outstanding_excl_opening(
    supplier_id: int, as_on: date, brand_id: int | None = None
) -> float:
    """Outstanding from transactions only — excludes supplier opening balance."""
    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(*_bill_filters(supplier_id, brand_id), SupplierBill.bill_date <= as_on)
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(*_payment_filters(supplier_id, brand_id), SupplierPayment.payment_date <= as_on)
        .scalar()
    )
    returns = _sum_returns(supplier_id, brand_id, None, as_on)
    return float(purchases) - float(paid) - returns


def supplier_balance_before(
    supplier_id: int, before_date: date, brand_id: int | None = None
) -> float:
    from app.models import Supplier

    opening = 0.0
    if brand_id is None:
        supplier = db.session.get(Supplier, supplier_id)
        opening = float(supplier.opening_balance) if supplier else 0.0
    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(*_bill_filters(supplier_id, brand_id), SupplierBill.bill_date < before_date)
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(*_payment_filters(supplier_id, brand_id), SupplierPayment.payment_date < before_date)
        .scalar()
    )
    returns = (
        db.session.query(func.coalesce(func.sum(PurchaseReturn.amount), 0))
        .filter(*_return_filters(supplier_id, brand_id), PurchaseReturn.return_date < before_date)
        .scalar()
    )
    return opening + float(purchases) - float(paid) - float(returns)


def build_supplier_ledger(
    supplier_id: int,
    from_date: date,
    to_date: date,
    brand_id: int | None = None,
    category_id: int | None = None,
):
    from app.models import Supplier

    supplier = db.session.get(Supplier, supplier_id)
    if not supplier:
        return []

    if category_id and (
        not supplier.category_id or str(supplier.category_id) != str(category_id)
    ):
        return []

    balance = supplier_balance_before(supplier_id, from_date, brand_id)
    ledger = []

    if abs(balance) >= 0.01:
        ledger.append(
            {
                "date": from_date,
                "particulars": "Opening Balance",
                "reference": "",
                "debit": 0.0,
                "credit": 0.0,
                "balance": balance,
            }
        )

    events = []

    bill_q = SupplierBill.query.filter(
        SupplierBill.supplier_id == supplier_id,
        SupplierBill.bill_date >= from_date,
        SupplierBill.bill_date <= to_date,
    )
    if brand_id is not None:
        bill_q = bill_q.filter(SupplierBill.brand_id == brand_id)
    for bill in bill_q.all():
        events.append(
            {
                "sort_date": bill.bill_date,
                "sort_id": bill.id,
                "date": bill.bill_date,
                "particulars": "Purchase",
                "reference": bill.bill_no,
                "debit": 0.0,
                "credit": float(bill.total_amount),
            }
        )

    payment_q = SupplierPayment.query.filter(
        SupplierPayment.supplier_id == supplier_id,
        SupplierPayment.payment_date >= from_date,
        SupplierPayment.payment_date <= to_date,
    )
    if brand_id is not None:
        payment_q = payment_q.filter(SupplierPayment.brand_id == brand_id)
    for payment in payment_q.all():
        events.append(
            {
                "sort_date": payment.payment_date,
                "sort_id": payment.id,
                "date": payment.payment_date,
                "particulars": "Payment",
                "reference": payment.payment_number or f"PAY-{payment.id:04d}",
                "debit": float(payment.amount),
                "credit": 0.0,
            }
        )

    return_q = PurchaseReturn.query.filter(
        PurchaseReturn.supplier_id == supplier_id,
        PurchaseReturn.return_date >= from_date,
        PurchaseReturn.return_date <= to_date,
    )
    if brand_id is not None:
        return_q = return_q.filter(PurchaseReturn.brand_id == brand_id)
    for purchase_return in return_q.all():
        events.append(
            {
                "sort_date": purchase_return.return_date,
                "sort_id": purchase_return.id,
                "date": purchase_return.return_date,
                "particulars": "Purchase Return",
                "reference": purchase_return.return_number,
                "debit": float(purchase_return.amount),
                "credit": 0.0,
            }
        )

    events.sort(key=lambda e: (e["sort_date"], e["sort_id"]))
    for event in events:
        balance += event["credit"] - event["debit"]
        ledger.append(
            {
                "date": event["date"],
                "particulars": event["particulars"],
                "reference": event["reference"],
                "debit": event["debit"],
                "credit": event["credit"],
                "balance": balance,
            }
        )

    return ledger


def brand_totals(brand_id: int, as_on: date):
    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(SupplierBill.brand_id == brand_id, SupplierBill.bill_date <= as_on)
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(SupplierPayment.brand_id == brand_id, SupplierPayment.payment_date <= as_on)
        .scalar()
    )
    return float(purchases), float(paid), float(purchases) - float(paid)


def brand_period_totals(brand_id: int, from_date: date, to_date: date):
    purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(
            SupplierBill.brand_id == brand_id,
            SupplierBill.bill_date >= from_date,
            SupplierBill.bill_date <= to_date,
        )
        .scalar()
    )
    paid = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(
            SupplierPayment.brand_id == brand_id,
            SupplierPayment.payment_date >= from_date,
            SupplierPayment.payment_date <= to_date,
        )
        .scalar()
    )
    return float(purchases), float(paid)


def get_opening_balance_for_account(account_id: int, before_date: date):
    from app.models import BankAccount

    record = (
        OpeningBalance.query.filter(
            OpeningBalance.bank_account_id == account_id,
            OpeningBalance.as_on_date <= before_date,
        )
        .order_by(OpeningBalance.as_on_date.desc())
        .first()
    )
    if record:
        return float(record.amount), record.as_on_date

    account = db.session.get(BankAccount, account_id)
    if account and account.account_type == "cash":
        legacy = (
            OpeningBalance.query.filter(
                OpeningBalance.account_type == "cash",
                OpeningBalance.bank_account_id.is_(None),
                OpeningBalance.as_on_date <= before_date,
            )
            .order_by(OpeningBalance.as_on_date.desc())
            .first()
        )
        if legacy:
            return float(legacy.amount), legacy.as_on_date
    return 0.0, None


def account_balance_before_id(account_id: int, before_date: date) -> float:
    balance, opening_date = get_opening_balance_for_account(account_id, before_date)

    inflow_q = CashBankInflow.query.filter(
        CashBankInflow.bank_account_id == account_id,
        CashBankInflow.inflow_date < before_date,
    )
    sp_q = SupplierPayment.query.filter(
        SupplierPayment.bank_account_id == account_id,
        SupplierPayment.payment_date < before_date,
    )
    ep_q = ExpensePayment.query.filter(
        ExpensePayment.bank_account_id == account_id,
        ExpensePayment.payment_date < before_date,
    )

    if opening_date:
        inflow_q = inflow_q.filter(CashBankInflow.inflow_date >= opening_date)
        sp_q = sp_q.filter(SupplierPayment.payment_date >= opening_date)
        ep_q = ep_q.filter(ExpensePayment.payment_date >= opening_date)

    inflows = sum(i.amount for i in inflow_q.all())
    supplier_out = sum(p.amount for p in sp_q.all())
    expense_out = sum(e.amount for e in ep_q.all())
    return balance + inflows - supplier_out - expense_out


def build_cash_report_ledger(from_date: date, to_date: date, account_id: int | None = None):
    from app.models import BankAccount

    show_particulars = account_id is None
    if account_id:
        account_ids = [int(account_id)]
    else:
        account_ids = [
            a.id for a in BankAccount.query.filter_by(is_active=True).order_by(BankAccount.name).all()
        ]

    opening = sum(account_balance_before_id(aid, from_date) for aid in account_ids)
    balance = opening
    ledger = []

    if abs(opening) >= 0.01:
        ledger.append(
            {
                "date": from_date,
                "particulars": "Opening Balance" if show_particulars else "",
                "head": "",
                "balance": opening,
            }
        )

    events = []

    inflows = CashBankInflow.query.filter(
        CashBankInflow.inflow_date >= from_date,
        CashBankInflow.inflow_date <= to_date,
        CashBankInflow.bank_account_id.in_(account_ids),
    ).all()
    for inflow in inflows:
        label = receipt_type_label(getattr(inflow, "receipt_type", "sales_collection") or "sales_collection")
        particulars = label
        if show_particulars and inflow.bank_account:
            particulars = f"{label} — {inflow.bank_account.name}"
        events.append(
            {
                "sort_date": inflow.inflow_date,
                "sort_id": inflow.id,
                "sort_kind": 0,
                "date": inflow.inflow_date,
                "particulars": particulars,
                "head": "Receipt",
                "amount_in": float(inflow.amount),
            }
        )

    supplier_payments = SupplierPayment.query.filter(
        SupplierPayment.payment_date >= from_date,
        SupplierPayment.payment_date <= to_date,
        SupplierPayment.bank_account_id.in_(account_ids),
    ).all()
    for payment in supplier_payments:
        particulars = payment.bank_account.name if show_particulars and payment.bank_account else ""
        events.append(
            {
                "sort_date": payment.payment_date,
                "sort_id": payment.id,
                "sort_kind": 1,
                "date": payment.payment_date,
                "particulars": particulars,
                "head": "Supplier Payment",
                "amount_out": float(payment.amount),
            }
        )

    expense_payments = ExpensePayment.query.filter(
        ExpensePayment.payment_date >= from_date,
        ExpensePayment.payment_date <= to_date,
        ExpensePayment.bank_account_id.in_(account_ids),
    ).all()
    for payment in expense_payments:
        particulars = payment.bank_account.name if show_particulars and payment.bank_account else ""
        events.append(
            {
                "sort_date": payment.payment_date,
                "sort_id": payment.id,
                "sort_kind": 2,
                "date": payment.payment_date,
                "particulars": particulars,
                "head": "Expense Payment",
                "amount_out": float(payment.amount),
            }
        )

    events.sort(key=lambda e: (e["sort_date"], e["sort_kind"], e["sort_id"]))
    for event in events:
        if event.get("amount_in"):
            balance += event["amount_in"]
        else:
            balance -= event["amount_out"]
        ledger.append(
            {
                "date": event["date"],
                "particulars": event["particulars"],
                "head": event["head"],
                "balance": balance,
            }
        )

    return ledger, show_particulars


def build_cash_report_matrix(from_date: date, to_date: date, account_ids: list[int] | None = None):
    """Build cash report as account columns with opening, receipts, payments, closing rows."""
    from collections import defaultdict

    from sqlalchemy import func

    from app.models import BankAccount, CashBankInflow, ExpensePayment, SupplierPayment

    query = BankAccount.query.filter_by(is_active=True)
    if account_ids:
        query = query.filter(BankAccount.id.in_(account_ids))
    accounts = query.all()
    accounts = sorted(accounts, key=lambda a: (0 if a.account_type == "cash" else 1, a.name.lower()))

    columns = [{"id": a.id, "name": a.name, "account_type": a.account_type} for a in accounts]
    column_ids = [c["id"] for c in columns]

    def empty_amounts():
        return {cid: 0.0 for cid in column_ids}

    def row_total(amounts):
        return sum(amounts.values())

    def amounts_from_query(query_results):
        amounts = empty_amounts()
        for account_id, total in query_results:
            if account_id in amounts:
                amounts[account_id] = float(total or 0)
        return amounts

    opening_amounts = {aid: account_balance_before_id(aid, from_date) for aid in column_ids}
    opening_row = {
        "label": "Opening Balance",
        "amounts": opening_amounts,
        "total": row_total(opening_amounts),
    }

    receipt_results = (
        db.session.query(CashBankInflow.bank_account_id, func.sum(CashBankInflow.amount))
        .filter(
            CashBankInflow.inflow_date >= from_date,
            CashBankInflow.inflow_date <= to_date,
        )
        .group_by(CashBankInflow.bank_account_id)
        .all()
    )
    receipt_amounts = amounts_from_query(receipt_results)
    receipt_row = {
        "label": "Receipts",
        "amounts": receipt_amounts,
        "total": row_total(receipt_amounts),
    }

    sp_results = (
        db.session.query(SupplierPayment.bank_account_id, func.sum(SupplierPayment.amount))
        .filter(
            SupplierPayment.payment_date >= from_date,
            SupplierPayment.payment_date <= to_date,
        )
        .group_by(SupplierPayment.bank_account_id)
        .all()
    )
    supplier_amounts = amounts_from_query(sp_results)
    payment_rows = [
        {
            "label": "Supplier Payments",
            "amounts": supplier_amounts,
            "total": row_total(supplier_amounts),
        }
    ]

    expense_payments = ExpensePayment.query.filter(
        ExpensePayment.payment_date >= from_date,
        ExpensePayment.payment_date <= to_date,
    ).all()
    group_map = defaultdict(empty_amounts)
    for payment in expense_payments:
        group_name = "Ungrouped"
        if payment.category and payment.category.group:
            group_name = payment.category.group.name
        aid = payment.bank_account_id
        if aid in group_map[group_name]:
            group_map[group_name][aid] += float(payment.amount)

    for group_name in sorted(group_map.keys()):
        amounts = group_map[group_name]
        payment_rows.append(
            {"label": group_name, "amounts": amounts, "total": row_total(amounts)}
        )

    total_payment_amounts = empty_amounts()
    for row in payment_rows:
        for aid, amt in row["amounts"].items():
            total_payment_amounts[aid] += amt

    closing_amounts = {
        aid: opening_amounts[aid] + receipt_amounts[aid] - total_payment_amounts[aid]
        for aid in column_ids
    }
    closing_row = {
        "label": "Closing Balance",
        "amounts": closing_amounts,
        "total": row_total(closing_amounts),
    }

    return {
        "columns": columns,
        "sections": [
            {"title": "1. Opening Balance", "rows": [opening_row], "highlight": True},
            {"title": "2. Receipts", "rows": [receipt_row]},
            {"title": "3. Payments", "rows": payment_rows},
            {"title": "4. Closing Balance", "rows": [closing_row], "highlight": True},
        ],
    }


def month_date_range(year: int, month: int) -> tuple[date, date]:
    """Return first and last calendar day for a year/month."""
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def year_date_range(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def _variation_pct(actual: float, budget: float) -> float | None:
    if abs(budget) < 0.0001:
        return None
    return ((actual - budget) / budget) * 100.0


def _comparison_row(label: str, budget: float, actual: float, indent: bool = False, is_total: bool = False):
    variation = actual - budget
    return {
        "label": label,
        "budget": float(budget or 0),
        "actual": float(actual or 0),
        "variation": float(variation),
        "pct": _variation_pct(float(actual or 0), float(budget or 0)),
        "indent": indent,
        "is_total": is_total,
    }


def build_budget_vs_actual(period_type: str, year: int, month: int | None = None) -> dict:
    """
    Build budget vs actual cash-flow comparison.
    Receipts are branch-wise; purchases are supplier-category-wise; expenses are group-wise.
    Actual purchases = SupplierBill totals in the period (by supplier category).
    """
    if period_type == "year":
        from_date, to_date = year_date_range(year)
        budgets = MonthlyBudget.query.filter_by(year=year).all()
        period_label = str(year)
    else:
        if not month or month < 1 or month > 12:
            raise ValueError("Month is required for month-wise report")
        from_date, to_date = month_date_range(year, month)
        budgets = MonthlyBudget.query.filter_by(year=year, month=month).all()
        period_label = date(year, month, 1).strftime("%b %Y")

    # --- Budget totals ---
    budget_receipts: dict[int, float] = {}
    budget_purchases: dict[int, float] = {}
    budget_expenses: dict[int, float] = {}
    for budget in budgets:
        for line in budget.receipt_lines:
            budget_receipts[line.branch_id] = budget_receipts.get(line.branch_id, 0.0) + float(line.amount or 0)
        for line in budget.purchase_lines:
            budget_purchases[line.supplier_category_id] = budget_purchases.get(
                line.supplier_category_id, 0.0
            ) + float(line.amount or 0)
        # Legacy single purchase_amount (pre category-wise)
        if not budget.purchase_lines and float(budget.purchase_amount or 0) > 0:
            budget_purchases[0] = budget_purchases.get(0, 0.0) + float(budget.purchase_amount or 0)
        for line in budget.expense_lines:
            budget_expenses[line.expense_group_id] = budget_expenses.get(line.expense_group_id, 0.0) + float(
                line.amount or 0
            )

    # --- Actual receipts by branch ---
    actual_receipt_rows = (
        db.session.query(CashBankInflow.branch_id, func.coalesce(func.sum(CashBankInflow.amount), 0))
        .filter(CashBankInflow.inflow_date >= from_date, CashBankInflow.inflow_date <= to_date)
        .group_by(CashBankInflow.branch_id)
        .all()
    )
    actual_receipts: dict[int | None, float] = {
        branch_id: float(total or 0) for branch_id, total in actual_receipt_rows
    }

    # --- Actual purchases by supplier category ---
    cat_label = func.coalesce(SupplierCategory.name, "Uncategorised")
    actual_purchase_rows = (
        db.session.query(Supplier.category_id, cat_label, func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .select_from(SupplierBill)
        .join(Supplier, SupplierBill.supplier_id == Supplier.id)
        .outerjoin(SupplierCategory, Supplier.category_id == SupplierCategory.id)
        .filter(SupplierBill.bill_date >= from_date, SupplierBill.bill_date <= to_date)
        .group_by(Supplier.category_id, cat_label)
        .all()
    )
    actual_purchases: dict[int | None, float] = {}
    actual_purchase_names: dict[int | None, str] = {}
    for category_id, name, total in actual_purchase_rows:
        actual_purchases[category_id] = float(total or 0)
        actual_purchase_names[category_id] = name

    # --- Actual expenses by group ---
    group_label = func.coalesce(ExpenseGroup.name, "Ungrouped")
    actual_expense_rows = (
        db.session.query(ExpenseCategory.group_id, group_label, func.coalesce(func.sum(ExpensePayment.amount), 0))
        .select_from(ExpensePayment)
        .join(ExpenseCategory, ExpensePayment.category_id == ExpenseCategory.id)
        .outerjoin(ExpenseGroup, ExpenseCategory.group_id == ExpenseGroup.id)
        .filter(ExpensePayment.payment_date >= from_date, ExpensePayment.payment_date <= to_date)
        .group_by(ExpenseCategory.group_id, group_label)
        .all()
    )
    actual_expenses: dict[int | None, float] = {}
    actual_expense_names: dict[int | None, str] = {}
    for group_id, name, total in actual_expense_rows:
        actual_expenses[group_id] = float(total or 0)
        actual_expense_names[group_id] = name

    # Branch names
    branch_ids = set(budget_receipts.keys()) | {bid for bid in actual_receipts if bid is not None}
    branches = {b.id: b.name for b in Branch.query.filter(Branch.id.in_(branch_ids)).all()} if branch_ids else {}
    for b in Branch.query.filter_by(is_active=True).order_by(Branch.name).all():
        branches.setdefault(b.id, b.name)

    # Supplier category names (only those used in budget or actual)
    purchase_cat_ids = {cid for cid in budget_purchases if cid} | {
        cid for cid in actual_purchases if cid is not None
    }
    categories = {
        c.id: c.name for c in SupplierCategory.query.filter(SupplierCategory.id.in_(purchase_cat_ids)).all()
    } if purchase_cat_ids else {}

    # Expense group names (only those used in budget or actual)
    group_ids = set(budget_expenses.keys()) | {gid for gid in actual_expenses if gid is not None}
    groups = {
        g.id: g.name for g in ExpenseGroup.query.filter(ExpenseGroup.id.in_(group_ids)).all()
    } if group_ids else {}

    # --- Build row sections ---
    receipt_rows = []
    for branch_id in sorted(set(branches.keys()) | set(budget_receipts.keys()), key=lambda i: branches.get(i, "").lower()):
        receipt_rows.append(
            _comparison_row(
                branches.get(branch_id, f"Branch #{branch_id}"),
                budget_receipts.get(branch_id, 0.0),
                actual_receipts.get(branch_id, 0.0),
                indent=True,
            )
        )
    unassigned_actual = actual_receipts.get(None, 0.0)
    if abs(unassigned_actual) >= 0.01:
        receipt_rows.append(
            _comparison_row("Unassigned (no branch)", 0.0, unassigned_actual, indent=True)
        )

    total_receipt_budget = sum(r["budget"] for r in receipt_rows)
    total_receipt_actual = sum(r["actual"] for r in receipt_rows)
    receipt_total = _comparison_row("Total Receipts", total_receipt_budget, total_receipt_actual, is_total=True)

    purchase_rows = []
    all_purchase_keys = set(budget_purchases.keys()) | {cid for cid in actual_purchases if cid}
    all_purchase_keys.discard(0)
    for category_id in sorted(
        all_purchase_keys,
        key=lambda i: (categories.get(i) or actual_purchase_names.get(i) or "").lower(),
    ):
        purchase_rows.append(
            _comparison_row(
                categories.get(category_id) or actual_purchase_names.get(category_id) or f"Category #{category_id}",
                budget_purchases.get(category_id, 0.0),
                actual_purchases.get(category_id, 0.0),
                indent=True,
            )
        )
    if 0 in budget_purchases:
        purchase_rows.append(
            _comparison_row("General (legacy)", budget_purchases.get(0, 0.0), 0.0, indent=True)
        )
    uncat_actual = actual_purchases.get(None, 0.0)
    if abs(uncat_actual) >= 0.01:
        purchase_rows.append(_comparison_row("Uncategorised", 0.0, uncat_actual, indent=True))

    total_purchase_budget = sum(r["budget"] for r in purchase_rows)
    total_purchase_actual = sum(r["actual"] for r in purchase_rows)
    purchase_total = _comparison_row("Total Purchases", total_purchase_budget, total_purchase_actual, is_total=True)

    expense_rows = []
    all_group_keys = set(budget_expenses.keys()) | {gid for gid in actual_expenses if gid}
    for group_id in sorted(all_group_keys, key=lambda i: (groups.get(i) or actual_expense_names.get(i) or "").lower()):
        expense_rows.append(
            _comparison_row(
                groups.get(group_id) or actual_expense_names.get(group_id) or f"Group #{group_id}",
                budget_expenses.get(group_id, 0.0),
                actual_expenses.get(group_id, 0.0),
                indent=True,
            )
        )
    ungrouped_actual = actual_expenses.get(None, 0.0)
    if abs(ungrouped_actual) >= 0.01:
        expense_rows.append(_comparison_row("Ungrouped", 0.0, ungrouped_actual, indent=True))

    total_expense_budget = sum(r["budget"] for r in expense_rows)
    total_expense_actual = sum(r["actual"] for r in expense_rows)
    expense_total = _comparison_row("Total Expenses", total_expense_budget, total_expense_actual, is_total=True)

    net_budget = total_receipt_budget - total_purchase_budget - total_expense_budget
    net_actual = total_receipt_actual - total_purchase_actual - total_expense_actual
    net_row = _comparison_row("Net Balance (Receipts − Purchases − Expenses)", net_budget, net_actual, is_total=True)

    return {
        "period_type": period_type,
        "period_label": period_label,
        "from_date": from_date,
        "to_date": to_date,
        "has_budget": bool(budgets),
        "sections": [
            {"title": "Proposed Receipts (Branch-wise)", "rows": receipt_rows, "total": receipt_total},
            {"title": "Purchases (Supplier Category)", "rows": purchase_rows, "total": purchase_total},
            {"title": "Expenses (Group-wise)", "rows": expense_rows, "total": expense_total},
            {"title": "Net", "rows": [net_row], "total": None},
        ],
    }


def get_test_data_counts() -> dict[str, int]:
    return {
        "purchase_orders": PurchaseOrder.query.count(),
        "supplier_bills": SupplierBill.query.count(),
        "purchase_returns": PurchaseReturn.query.count(),
        "supplier_payments": SupplierPayment.query.count(),
        "expense_payments": ExpensePayment.query.count(),
        "receipts": CashBankInflow.query.count(),
        "opening_balances": OpeningBalance.query.count(),
        "monthly_budgets": MonthlyBudget.query.count(),
    }


def clear_test_data() -> dict[str, int]:
    """Delete transactional MIS data. Master data (users, suppliers, brands, etc.) is kept."""
    counts = get_test_data_counts()

    BudgetReceiptLine.query.delete()
    BudgetPurchaseLine.query.delete()
    BudgetExpenseLine.query.delete()
    MonthlyBudget.query.delete()
    SupplierBill.query.delete()
    PurchaseOrder.query.delete()
    PurchaseReturn.query.delete()
    SupplierPayment.query.delete()
    ExpensePayment.query.delete()
    CashBankInflow.query.delete()
    OpeningBalance.query.delete()
    db.session.query(Supplier).update({Supplier.opening_balance: 0}, synchronize_session=False)
    db.session.commit()

    return counts


def get_opening_balance(account_type: str, bank_account_id: int | None, before_date: date):
    query = OpeningBalance.query.filter(OpeningBalance.as_on_date <= before_date)
    query = query.filter_by(account_type=account_type)
    if account_type == "bank":
        query = query.filter_by(bank_account_id=bank_account_id)
    else:
        query = query.filter(OpeningBalance.bank_account_id.is_(None))
    record = query.order_by(OpeningBalance.as_on_date.desc()).first()
    if record:
        return float(record.amount), record.as_on_date
    return 0.0, None


def account_balance_before(account_type: str, bank_account_id: int | None, before_date: date) -> float:
    balance, opening_date = get_opening_balance(account_type, bank_account_id, before_date)

    inflow_q = CashBankInflow.query.filter(CashBankInflow.inflow_date < before_date)
    sp_q = SupplierPayment.query.filter(SupplierPayment.payment_date < before_date)
    ep_q = ExpensePayment.query.filter(ExpensePayment.payment_date < before_date)

    if opening_date:
        inflow_q = inflow_q.filter(CashBankInflow.inflow_date >= opening_date)
        sp_q = sp_q.filter(SupplierPayment.payment_date >= opening_date)
        ep_q = ep_q.filter(ExpensePayment.payment_date >= opening_date)

    if account_type == "cash":
        inflow_q = inflow_q.filter_by(payment_mode="cash")
        sp_q = sp_q.filter_by(payment_mode="cash")
        ep_q = ep_q.filter_by(payment_mode="cash")
    else:
        inflow_q = inflow_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)
        sp_q = sp_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)
        ep_q = ep_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)

    inflows = sum(i.amount for i in inflow_q.all())
    supplier_out = sum(p.amount for p in sp_q.all())
    expense_out = sum(e.amount for e in ep_q.all())
    return balance + inflows - supplier_out - expense_out


def account_period_movements(account_type: str, bank_account_id: int | None, from_date: date, to_date: date):
    inflow_q = CashBankInflow.query.filter(
        CashBankInflow.inflow_date >= from_date, CashBankInflow.inflow_date <= to_date
    )
    sp_q = SupplierPayment.query.filter(
        SupplierPayment.payment_date >= from_date, SupplierPayment.payment_date <= to_date
    )
    ep_q = ExpensePayment.query.filter(
        ExpensePayment.payment_date >= from_date, ExpensePayment.payment_date <= to_date
    )

    if account_type == "cash":
        inflow_q = inflow_q.filter_by(payment_mode="cash")
        sp_q = sp_q.filter_by(payment_mode="cash")
        ep_q = ep_q.filter_by(payment_mode="cash")
    else:
        inflow_q = inflow_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)
        sp_q = sp_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)
        ep_q = ep_q.filter_by(payment_mode="bank", bank_account_id=bank_account_id)

    inflows = inflow_q.order_by(CashBankInflow.inflow_date).all()
    supplier_payments = sp_q.order_by(SupplierPayment.payment_date).all()
    expense_payments = ep_q.order_by(ExpensePayment.payment_date).all()

    total_in = sum(i.amount for i in inflows)
    total_supplier = sum(p.amount for p in supplier_payments)
    total_expense = sum(e.amount for e in expense_payments)

    return {
        "inflows": inflows,
        "supplier_payments": supplier_payments,
        "expense_payments": expense_payments,
        "total_in": total_in,
        "total_supplier": total_supplier,
        "total_expense": total_expense,
        "total_out": total_supplier + total_expense,
    }
