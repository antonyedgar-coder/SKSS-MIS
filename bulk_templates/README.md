# SKSS-MIS Bulk Upload Templates

Use these files to bulk upload **Suppliers**, **Brands**, and **Expense Categories**.

## Download options

### From the app (after login as Admin)
- **Settings → Suppliers** → **Excel Template** or **CSV Template**
- **Settings → Brands** → **Excel Template** or **CSV Template**
- **Settings → Expense Categories** → **Excel Template** or **CSV Template**

### From this folder
| File | Format |
|------|--------|
| `supplier_upload_template.csv` | CSV |
| `brand_upload_template.csv` | CSV |
| `expense_category_upload_template.csv` | CSV |
| `bank_account_upload_template.csv` | CSV |

Open any CSV in Excel, fill your data, then upload the same file (.csv or save as .xlsx).

---

## Supplier upload format

| Column | Required | Example |
|--------|----------|---------|
| Name | Yes | ABC Distributors |
| Opening Balance | No | 15000 |
| Contact | No | 9876543210 |
| Email | No | abc@example.com |
| Address | No | 12 Market Road, City |
| Category | No | Grocery |

- Category must already exist in **Supplier Categories** (matched by name).
- Duplicate supplier names are skipped.

---

## Bank account upload format

| Column | Required | Example |
|--------|----------|---------|
| Bank Account Name | Yes | HDFC Current |
| Opening Balance | No | 250000 |
| As On Date | No | 2026-07-01 |

- If As On Date is blank, today's date is used.
- Duplicate bank account names are skipped.

---

## Brand upload format

| Column | Required | Example |
|--------|----------|---------|
| Company Name | Yes | HUL |
| Brand Name | Yes | Dove |

- One company can have many brands (repeat Company Name for each brand).
- New companies are created automatically.
- Duplicate company + brand pairs are skipped.

---

## Expense category upload format

| Column | Required | Example |
|--------|----------|---------|
| Category Name | Yes | Rent |

Sample categories: Rent, Electricity, Staff Salary, Transport, Packaging, Maintenance, Bank Charges

- Duplicate category names are skipped.

---

## Generate Excel (.xlsx) files locally

```powershell
cd C:\Users\anton\SKSS-MIS
.\.venv\Scripts\Activate.ps1
python generate_bulk_templates.py
```

This creates `supplier_upload_template.xlsx`, `brand_upload_template.xlsx`, and `expense_category_upload_template.xlsx` in this folder.
