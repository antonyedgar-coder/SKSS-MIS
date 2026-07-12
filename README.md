# SKSS-MIS

Supermarket Management Information System for local network (LAN) use.

## Features

- **Supplier MIS** — purchase bills (bill total), payments, outstanding balance (all suppliers, category-wise, per-supplier ledger in Excel)
- **Expenses MIS** — categorized expense payments with category-wise and detail reports
- **Cash Report** — separate cash and multiple bank accounts with inflows (sales/deposits) and outflows
- **Roles** — Admin (masters + delete) and Staff (entries + reports)
- **Export** — Excel download for all three reports with date range selection

## Requirements

- Python 3.10 or later
- Windows PC on the supermarket LAN (server machine)

## Quick Start

1. Double-click **`setup.bat`** once (first time only — installs Python deps)
2. Double-click **`start.bat`** to run the server
3. Open browser: `http://127.0.0.1:5000` on the server PC
4. Other staff on LAN: `http://<server-ip>:5000` (IP shown when server starts)

### Manual setup (PowerShell)

```powershell
cd C:\Users\anton\SKSS-MIS
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed_staff.py staff staff123
python run.py
```

> **Note:** On PowerShell use `Activate.ps1` (not `activate`). If blocked, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Manual setup (Command Prompt)

```bat
cd C:\Users\anton\SKSS-MIS
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python seed_staff.py staff staff123
python run.py
```

## Default login

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |

Change the admin password after first login (via database or add user management in a future update).

### Create staff user

```bat
.venv\Scripts\activate
python seed_staff.py staff staff123
```

Staff cannot access **Masters** (suppliers, expense categories, banks, opening balances).

## First-time setup (Admin)

1. **Masters → Bank Accounts** — add bank account(s)
2. **Masters → Opening Balances** — enter cash and bank opening balances
3. **Masters → Supplier Categories** — e.g. Dairy, Grocery, Beverages
4. **Masters → Suppliers** — add vendors
5. **Masters → Expense Categories** — e.g. Rent, Salary, Electricity
6. Start daily **Entries** and run **Reports** as needed

## LAN access

- Server binds to `0.0.0.0:5000` (all network interfaces)
- Allow port **5000** in Windows Firewall on the server PC if other devices cannot connect
- Keep the server PC running while staff use the system

## Backup

Copy the file **`skss_mis.db`** from the project folder regularly (e.g. daily to USB or another PC).

## Project structure

```
SKSS-MIS/
├── app/
│   ├── models.py          # Database models
│   ├── routes/            # Auth, masters, entries, reports
│   ├── templates/         # HTML pages
│   └── static/            # CSS, JS
├── run.py                 # Start server
├── start.bat              # Windows launcher
├── seed_staff.py          # Create staff user
└── requirements.txt
```

## Reports

| Report        | Excel sheets                                      |
|---------------|---------------------------------------------------|
| Supplier MIS  | All Suppliers, By Category, one sheet per supplier |
| Expenses MIS  | Summary, By Category, Detail                      |
| Cash Report   | Summary, Cash, one sheet per bank account         |

Outstanding balance is calculated **as on the selected To date**.
