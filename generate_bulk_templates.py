"""Generate Excel bulk upload templates. Run: python generate_bulk_templates.py"""
from pathlib import Path

from openpyxl import Workbook

OUT_DIR = Path(__file__).parent / "bulk_templates"
OUT_DIR.mkdir(exist_ok=True)

SUPPLIER_HEADERS = ["Name", "Opening Balance", "Contact", "Email", "Address", "Category"]
SUPPLIER_SAMPLES = [
    ["ABC Distributors", 15000, "9876543210", "abc@example.com", "12 Market Road, City", "Grocery"],
    ["XYZ Wholesale", 8500, "9123456780", "xyz@example.com", "45 Industrial Area", "Dairy"],
    ["Fresh Foods Pvt Ltd", 0, "9988776655", "fresh@example.com", "78 Wholesale Market", "Vegetables"],
]

BANK_HEADERS = ["Account Name", "Account Type", "Opening Balance", "As On Date"]
BANK_SAMPLES = [
    ["Cash", "Cash", 50000, "2026-07-01"],
    ["HDFC Current", "Bank", 250000, "2026-07-01"],
    ["SBI Savings", "Bank", 120000, "2026-07-01"],
]

BRAND_HEADERS = ["Company Name", "Brand Name"]
BRAND_SAMPLES = [
    ["HUL", "Dove"],
    ["HUL", "Lux"],
    ["HUL", "Surf Excel"],
    ["Britannia", "Good Day"],
    ["Britannia", "Bourbon"],
    ["Himalaya", "Face Wash"],
    ["Himalaya", "Shampoo"],
]

EXPENSE_CATEGORY_HEADERS = ["Category Name", "Expense Group"]
EXPENSE_CATEGORY_SAMPLES = [
    ["Rent", "Fixed Expenses"],
    ["Electricity", "Utilities"],
    ["Staff Salary", "Payroll"],
    ["Transport", "Operations"],
    ["Packaging", "Operations"],
    ["Maintenance", "Operations"],
    ["Bank Charges", "Finance"],
]


def save_workbook(headers, samples, filename):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in samples:
        ws.append(row)
    path = OUT_DIR / filename
    wb.save(path)
    print(f"Created: {path}")


if __name__ == "__main__":
    save_workbook(SUPPLIER_HEADERS, SUPPLIER_SAMPLES, "supplier_upload_template.xlsx")
    save_workbook(BANK_HEADERS, BANK_SAMPLES, "bank_account_upload_template.xlsx")
    save_workbook(BRAND_HEADERS, BRAND_SAMPLES, "brand_upload_template.xlsx")
    save_workbook(EXPENSE_CATEGORY_HEADERS, EXPENSE_CATEGORY_SAMPLES, "expense_category_upload_template.xlsx")
