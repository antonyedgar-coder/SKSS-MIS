# Push SKSS-MIS to GitHub (no gh CLI required)
# Run:  cd C:\Users\anton\SKSS-MIS; .\deploy\push-to-github.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

git remote set-url origin https://github.com/antonyedgar-coder/SKSS-MIS.git

$status = git status --porcelain
if ($status) {
    Write-Host "Uncommitted changes found. Staging project files..."
    git add app/ deploy/ requirements.txt run.py config.py
    git status --short
    git commit -m "Add monthly budget, branch master, and budget vs actual report"
}

Write-Host "Pushing to GitHub..."
git push -u origin main

Write-Host ""
Write-Host "Done. Repo: https://github.com/antonyedgar-coder/SKSS-MIS"
Write-Host "Next: SSH to your droplet and run the server install commands."
