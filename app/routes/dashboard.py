from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import (
    CashBankInflow,
    ExpensePayment,
    Supplier,
    SupplierBill,
    SupplierPayment,
)
from app.utils import supplier_totals

dashboard_bp = Blueprint("dashboard", __name__)


def _month_end(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year, 12, 31)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def _monthly_chart_data(today: date, months: int = 6) -> dict:
    labels = []
    purchases = []
    expenses = []
    payments = []
    receipts = []

    cur = today.replace(day=1)
    for _ in range(months):
        month_start = cur
        month_end = _month_end(cur)
        labels.insert(0, cur.strftime("%b %Y"))

        purchases.insert(
            0,
            float(
                db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
                .filter(SupplierBill.bill_date >= month_start, SupplierBill.bill_date <= month_end)
                .scalar()
            ),
        )
        expenses.insert(
            0,
            float(
                db.session.query(func.coalesce(func.sum(ExpensePayment.amount), 0))
                .filter(
                    ExpensePayment.payment_date >= month_start,
                    ExpensePayment.payment_date <= month_end,
                )
                .scalar()
            ),
        )
        payments.insert(
            0,
            float(
                db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
                .filter(
                    SupplierPayment.payment_date >= month_start,
                    SupplierPayment.payment_date <= month_end,
                )
                .scalar()
            ),
        )
        receipts.insert(
            0,
            float(
                db.session.query(func.coalesce(func.sum(CashBankInflow.amount), 0))
                .filter(
                    CashBankInflow.inflow_date >= month_start,
                    CashBankInflow.inflow_date <= month_end,
                )
                .scalar()
            ),
        )
        cur = (cur - timedelta(days=1)).replace(day=1)

    return {
        "labels": labels,
        "purchases": purchases,
        "expenses": expenses,
        "payments": payments,
        "receipts": receipts,
    }


def _expense_group_chart(month_start: date, today: date) -> dict:
    from collections import defaultdict

    group_totals = defaultdict(float)
    expense_payments = ExpensePayment.query.filter(
        ExpensePayment.payment_date >= month_start,
        ExpensePayment.payment_date <= today,
    ).all()
    for payment in expense_payments:
        if payment.category and payment.category.group:
            group_name = payment.category.group.name
        else:
            group_name = "Ungrouped"
        group_totals[group_name] += float(payment.amount)

    sorted_groups = sorted(group_totals.items(), key=lambda x: x[1], reverse=True)
    return {
        "labels": [name for name, _ in sorted_groups] or ["No expenses"],
        "values": [amount for _, amount in sorted_groups] or [0],
    }


@dashboard_bp.route("/")
@login_required
def index():
    today = date.today()
    suppliers = Supplier.query.order_by(Supplier.name).all()
    summary = []
    total_outstanding = 0.0
    for s in suppliers:
        purchases, paid, outstanding = supplier_totals(s.id, today)
        if purchases or paid or (s.opening_balance or 0):
            summary.append(
                {
                    "supplier": s,
                    "purchases": purchases,
                    "paid": paid,
                    "outstanding": outstanding,
                }
            )
            total_outstanding += outstanding

    summary.sort(key=lambda row: row["outstanding"], reverse=True)
    top_suppliers = summary[:8]

    month_start = today.replace(day=1)
    month_expenses = (
        db.session.query(func.coalesce(func.sum(ExpensePayment.amount), 0))
        .filter(ExpensePayment.payment_date >= month_start)
        .scalar()
    )
    month_purchases = (
        db.session.query(func.coalesce(func.sum(SupplierBill.total_amount), 0))
        .filter(SupplierBill.bill_date >= month_start)
        .scalar()
    )
    month_supplier_payments = (
        db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0))
        .filter(SupplierPayment.payment_date >= month_start)
        .scalar()
    )
    month_receipts = (
        db.session.query(func.coalesce(func.sum(CashBankInflow.amount), 0))
        .filter(CashBankInflow.inflow_date >= month_start)
        .scalar()
    )

    monthly_chart = _monthly_chart_data(today)
    expense_group_chart = _expense_group_chart(month_start, today)
    supplier_chart = {
        "labels": [row["supplier"].name for row in top_suppliers] or ["No data"],
        "values": [row["outstanding"] for row in top_suppliers] or [0],
    }

    return render_template(
        "dashboard/index.html",
        summary=summary,
        total_outstanding=total_outstanding,
        month_expenses=float(month_expenses),
        month_purchases=float(month_purchases),
        month_supplier_payments=float(month_supplier_payments),
        month_receipts=float(month_receipts),
        monthly_chart=monthly_chart,
        expense_group_chart=expense_group_chart,
        supplier_chart=supplier_chart,
        today=today,
    )
