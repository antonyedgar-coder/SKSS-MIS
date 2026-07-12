from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    BankAccount,
    Brand,
    CashBankInflow,
    Company,
    ExpenseCategory,
    ExpenseGroup,
    ExpensePayment,
    PurchaseOrder,
    PurchaseReturn,
    Supplier,
    SupplierBill,
    SupplierPayment,
)
from app.utils import (
    generate_order_number,
    generate_expense_payment_number,
    generate_payment_number,
    generate_return_number,
    parse_date,
    parse_account_id,
    parse_payment_account,
    receipt_type_label,
    variation_status_for_amounts,
)
from app.activity_log import log_activity
from app.permissions import module_access, permission_required

entries_bp = Blueprint("entries", __name__)


def _banks():
    return BankAccount.query.filter_by(is_active=True).order_by(BankAccount.name).all()


def _accounts():
    return _banks()


def _brands():
    return Brand.query.join(Company).order_by(Company.name, Brand.name).all()


@entries_bp.route("/")
@login_required
def index():
    return render_template("entries/index.html")


# --- Purchase Orders ---


@entries_bp.route("/purchase-orders", methods=["GET", "POST"])
@login_required
@module_access("purchase_order")
def purchase_orders():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    brands = _brands()
    next_order_number = generate_order_number(
        parse_date(request.form.get("order_date")) or date.today()
    )

    if request.method == "POST":
        order_date = parse_date(request.form.get("order_date"))
        supplier_id = int(request.form["supplier_id"])
        brand_id = int(request.form["brand_id"])
        ordered_amount = float(request.form.get("ordered_amount") or 0)
        remarks = request.form.get("remarks", "").strip()

        if order_date and ordered_amount > 0:
            order_number = generate_order_number(order_date)
            db.session.add(
                PurchaseOrder(
                    order_date=order_date,
                    order_number=order_number,
                    supplier_id=supplier_id,
                    brand_id=brand_id,
                    ordered_amount=ordered_amount,
                    remarks=remarks or None,
                    status="pending",
                    created_by_id=current_user.id,
                )
            )
            db.session.commit()
            log_activity("create", "purchase_order", f"Created purchase order {order_number}", order_number)
            flash(f"Purchase order {order_number} created.", "success")
            return redirect(url_for("entries.purchase_orders"))
        flash("Please fill all required fields.", "danger")

    orders = (
        PurchaseOrder.query.order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "entries/purchase_orders.html",
        suppliers=suppliers,
        brands=brands,
        orders=orders,
        next_order_number=next_order_number,
    )


@entries_bp.route("/purchase-orders/<int:order_id>/cancel", methods=["POST"])
@login_required
@permission_required("purchase_order", "delete")
def cancel_purchase_order(order_id):
    order = db.get_or_404(PurchaseOrder, order_id)
    if order.status != "pending":
        flash("Only pending orders can be cancelled.", "danger")
    else:
        order.status = "cancelled"
        db.session.commit()
        log_activity("delete", "purchase_order", f"Cancelled purchase order {order.order_number}", order.order_number)
        flash("Purchase order cancelled.", "success")
    return redirect(url_for("entries.purchase_orders"))


# --- Supplier Purchase (receive from PO) ---


@entries_bp.route("/supplier-bills")
@login_required
@permission_required("supplier_purchase", "view")
def supplier_bills():
    pending_orders = (
        PurchaseOrder.query.filter_by(status="pending")
        .order_by(PurchaseOrder.order_date.desc(), PurchaseOrder.id.desc())
        .all()
    )
    bills = (
        SupplierBill.query.order_by(SupplierBill.bill_date.desc(), SupplierBill.id.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "entries/supplier_bills.html",
        pending_orders=pending_orders,
        bills=bills,
    )


@entries_bp.route("/supplier-bills/receive/<int:order_id>", methods=["GET", "POST"])
@login_required
@module_access("supplier_purchase")
def receive_supplier_bill(order_id):
    order = db.get_or_404(PurchaseOrder, order_id)
    if order.status != "pending":
        flash("This order is already delivered or cancelled.", "warning")
        return redirect(url_for("entries.supplier_bills"))

    if request.method == "POST":
        bill_date = parse_date(request.form.get("bill_date"))
        total_amount = float(request.form.get("total_amount") or 0)
        note = request.form.get("note", "").strip()

        if bill_date and total_amount > 0:
            var_status = variation_status_for_amounts(order.ordered_amount, total_amount)
            bill = SupplierBill(
                supplier_id=order.supplier_id,
                brand_id=order.brand_id,
                purchase_order_id=order.id,
                bill_date=bill_date,
                bill_no=order.order_number,
                ordered_amount=order.ordered_amount,
                total_amount=total_amount,
                note=note or order.remarks,
                variation_status=var_status,
            )
            order.status = "delivered"
            db.session.add(bill)
            db.session.commit()
            log_activity(
                "create",
                "supplier_purchase",
                f"Booked supplier purchase for order {order.order_number}",
                order.order_number,
            )

            if var_status == "pending":
                flash(
                    f"Purchase booked for order {order.order_number}. "
                    "Amount variation detected — pending approver review.",
                    "warning",
                )
            else:
                flash(f"Purchase booked for order {order.order_number}.", "success")
            return redirect(url_for("entries.supplier_bills"))
        flash("Please fill all required fields.", "danger")

    return render_template("entries/receive_supplier_bill.html", order=order)


@entries_bp.route("/supplier-bills/<int:bill_id>/delete", methods=["POST"])
@login_required
@permission_required("supplier_purchase", "delete")
def delete_supplier_bill(bill_id):
    bill = db.get_or_404(SupplierBill, bill_id)
    if bill.purchase_order_id:
        po = db.session.get(PurchaseOrder, bill.purchase_order_id)
        if po:
            po.status = "pending"
    db.session.delete(bill)
    db.session.commit()
    log_activity("delete", "supplier_purchase", f"Deleted supplier purchase {bill.bill_no}", bill.bill_no)
    flash("Purchase deleted. Order restored to pending if linked.", "success")
    return redirect(url_for("entries.supplier_bills"))


# --- Supplier Payments ---


@entries_bp.route("/supplier-payments", methods=["GET", "POST"])
@login_required
@module_access("supplier_payment")
def supplier_payments():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    brands = _brands()
    banks = _banks()
    next_payment_number = generate_payment_number(
        parse_date(request.form.get("payment_date")) or date.today()
    )
    if request.method == "POST":
        supplier_id = int(request.form["supplier_id"])
        brand_id = int(request.form["brand_id"])
        payment_date = parse_date(request.form.get("payment_date"))
        amount = float(request.form.get("amount") or 0)
        payment_mode, bank_account_id = parse_payment_account(
            request.form.get("payment_account", "")
        )
        note = request.form.get("note", "").strip()
        if payment_date and amount > 0 and bank_account_id:
            payment_number = generate_payment_number(payment_date)
            db.session.add(
                SupplierPayment(
                    payment_number=payment_number,
                    supplier_id=supplier_id,
                    brand_id=brand_id,
                    payment_date=payment_date,
                    amount=amount,
                    payment_mode=payment_mode,
                    bank_account_id=bank_account_id,
                    note=note or None,
                )
            )
            db.session.commit()
            log_activity("create", "supplier_payment", f"Recorded supplier payment {payment_number}", payment_number)
            flash("Supplier payment recorded.", "success")
        else:
            flash("Please fill all required fields.", "danger")
        return redirect(url_for("entries.supplier_payments"))

    payments = (
        SupplierPayment.query.order_by(
            SupplierPayment.payment_date.desc(), SupplierPayment.id.desc()
        )
        .limit(100)
        .all()
    )
    return render_template(
        "entries/supplier_payments.html",
        suppliers=suppliers,
        brands=brands,
        banks=banks,
        payments=payments,
        next_payment_number=next_payment_number,
    )


@entries_bp.route("/supplier-payments/<int:payment_id>/delete", methods=["POST"])
@login_required
@permission_required("supplier_payment", "delete")
def delete_supplier_payment(payment_id):
    payment = db.get_or_404(SupplierPayment, payment_id)
    ref = payment.payment_number or str(payment_id)
    db.session.delete(payment)
    db.session.commit()
    log_activity("delete", "supplier_payment", f"Deleted supplier payment {ref}", ref)
    flash("Payment deleted.", "success")
    return redirect(url_for("entries.supplier_payments"))


# --- Purchase Returns ---


@entries_bp.route("/purchase-returns", methods=["GET", "POST"])
@login_required
@module_access("purchase_return")
def purchase_returns():
    suppliers = Supplier.query.order_by(Supplier.name).all()
    brands = _brands()
    next_return_number = generate_return_number(
        parse_date(request.form.get("return_date")) or date.today()
    )

    if request.method == "POST":
        supplier_id = int(request.form["supplier_id"])
        brand_id = int(request.form["brand_id"])
        return_date = parse_date(request.form.get("return_date"))
        amount = float(request.form.get("amount") or 0)
        note = request.form.get("note", "").strip()

        if return_date and amount > 0:
            return_number = generate_return_number(return_date)
            db.session.add(
                PurchaseReturn(
                    return_date=return_date,
                    return_number=return_number,
                    supplier_id=supplier_id,
                    brand_id=brand_id,
                    amount=amount,
                    note=note or None,
                    created_by_id=current_user.id,
                )
            )
            db.session.commit()
            log_activity("create", "purchase_return", f"Recorded purchase return {return_number}", return_number)
            flash(f"Purchase return {return_number} recorded.", "success")
            return redirect(url_for("entries.purchase_returns"))
        flash("Please fill all required fields.", "danger")

    returns = (
        PurchaseReturn.query.order_by(
            PurchaseReturn.return_date.desc(), PurchaseReturn.id.desc()
        )
        .limit(100)
        .all()
    )
    return render_template(
        "entries/purchase_returns.html",
        suppliers=suppliers,
        brands=brands,
        returns=returns,
        next_return_number=next_return_number,
    )


@entries_bp.route("/purchase-returns/<int:return_id>/delete", methods=["POST"])
@login_required
@permission_required("purchase_return", "delete")
def delete_purchase_return(return_id):
    purchase_return = db.get_or_404(PurchaseReturn, return_id)
    ref = purchase_return.return_number
    db.session.delete(purchase_return)
    db.session.commit()
    log_activity("delete", "purchase_return", f"Deleted purchase return {ref}", ref)
    flash("Purchase return deleted.", "success")
    return redirect(url_for("entries.purchase_returns"))


# --- Expense Payments ---


@entries_bp.route("/expense-payments", methods=["GET", "POST"])
@login_required
@module_access("expense_payment")
def expense_payments():
    categories = (
        ExpenseCategory.query.join(ExpenseGroup, isouter=True)
        .order_by(ExpenseCategory.name)
        .all()
    )
    banks = _banks()
    next_payment_number = generate_expense_payment_number(
        parse_date(request.form.get("payment_date")) or date.today()
    )
    if request.method == "POST":
        category_id = int(request.form["category_id"])
        payment_date = parse_date(request.form.get("payment_date"))
        payee = request.form.get("payee", "").strip()
        amount = float(request.form.get("amount") or 0)
        payment_mode, bank_account_id = parse_payment_account(
            request.form.get("payment_account", "")
        )
        note = request.form.get("note", "").strip()
        if payment_date and amount > 0 and bank_account_id:
            payment_number = generate_expense_payment_number(payment_date)
            db.session.add(
                ExpensePayment(
                    payment_number=payment_number,
                    category_id=category_id,
                    payment_date=payment_date,
                    payee=payee or None,
                    amount=amount,
                    payment_mode=payment_mode,
                    bank_account_id=bank_account_id,
                    note=note or None,
                )
            )
            db.session.commit()
            log_activity("create", "expense_payment", f"Recorded expense payment {payment_number}", payment_number)
            flash("Expense payment recorded.", "success")
        else:
            flash("Please fill all required fields.", "danger")
        return redirect(url_for("entries.expense_payments"))

    payments = (
        ExpensePayment.query.order_by(
            ExpensePayment.payment_date.desc(), ExpensePayment.id.desc()
        )
        .limit(100)
        .all()
    )
    return render_template(
        "entries/expense_payments.html",
        categories=categories,
        banks=banks,
        payments=payments,
        next_payment_number=next_payment_number,
    )


@entries_bp.route("/expense-payments/<int:payment_id>/delete", methods=["POST"])
@login_required
@permission_required("expense_payment", "delete")
def delete_expense_payment(payment_id):
    payment = db.get_or_404(ExpensePayment, payment_id)
    ref = payment.payment_number or str(payment_id)
    db.session.delete(payment)
    db.session.commit()
    log_activity("delete", "expense_payment", f"Deleted expense payment {ref}", ref)
    flash("Expense deleted.", "success")
    return redirect(url_for("entries.expense_payments"))


# --- Receipt MIS ---


@entries_bp.route("/inflows", methods=["GET", "POST"])
@login_required
@module_access("receipt_mis")
def inflows():
    accounts = _accounts()
    if request.method == "POST":
        inflow_date = parse_date(request.form.get("inflow_date"))
        receipt_type = request.form.get("receipt_type", "sales_collection")
        amount = float(request.form.get("amount") or 0)
        note = request.form.get("note", "").strip()
        account_id = parse_account_id(request.form.get("account_id", ""))
        if account_id:
            from app.models import BankAccount

            account = db.session.get(BankAccount, account_id)
            payment_mode = account.account_type if account else "bank"
        else:
            payment_mode = None

        if (
            inflow_date
            and amount > 0
            and account_id
            and receipt_type in ("sales_collection", "cash")
        ):
            db.session.add(
                CashBankInflow(
                    inflow_date=inflow_date,
                    receipt_type=receipt_type,
                    description=receipt_type_label(receipt_type),
                    amount=amount,
                    payment_mode=payment_mode or "bank",
                    bank_account_id=account_id,
                    note=note or None,
                )
            )
            db.session.commit()
            log_activity(
                "create",
                "receipt_mis",
                f"Recorded receipt of ₹{amount:.2f} ({receipt_type_label(receipt_type)})",
            )
            flash("Receipt recorded.", "success")
        else:
            flash("Please fill all required fields.", "danger")
        return redirect(url_for("entries.inflows"))

    inflow_list = (
        CashBankInflow.query.order_by(
            CashBankInflow.inflow_date.desc(), CashBankInflow.id.desc()
        )
        .limit(100)
        .all()
    )
    return render_template("entries/inflows.html", accounts=accounts, inflows=inflow_list)


@entries_bp.route("/inflows/<int:inflow_id>/delete", methods=["POST"])
@login_required
@permission_required("receipt_mis", "delete")
def delete_inflow(inflow_id):
    inflow = db.get_or_404(CashBankInflow, inflow_id)
    db.session.delete(inflow)
    db.session.commit()
    log_activity("delete", "receipt_mis", f"Deleted receipt dated {inflow.inflow_date}", str(inflow_id))
    flash("Inflow deleted.", "success")
    return redirect(url_for("entries.inflows"))
