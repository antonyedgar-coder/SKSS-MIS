# Run from PowerShell:  cd C:\Users\anton\SKSS-MIS; .\deploy\push-to-github.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

git remote set-url origin https://github.com/antonyedgar-coder/SKSS-MIS.git

$status = git status --short
if ($status) {
    git add deploy/ requirements.txt
    git commit -m "Add production deploy scripts and gunicorn"
}

Write-Host "Checking GitHub CLI auth..."
gh auth status

Write-Host "Creating repo (if needed) and pushing..."
gh repo create SKSS-MIS --private --source=. --remote=origin --push 2>$null
if ($LASTEXITCODE -ne 0) {
    git push -u origin main
}

Write-Host ""
Write-Host "Done. Repo: https://github.com/antonyedgar-coder/SKSS-MIS"
