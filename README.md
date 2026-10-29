# MTD Software Finder (static site)

Independent, searchable copy of HMRC's list of software recognised for Making Tax Digital for Income Tax.
Data: HMRC finder (https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/), Open Government Licence v3.0.

## Layout
- `scripts/fetch_hmrc.py` – reads the public HMRC finder (list + each product page) → `data/products.json`, `data/products.csv`
- `scripts/update.py` – nightly: fetch → diff vs latest `data/snapshots/*.json` → append to `data/changes.json` only if something changed → build
- `scripts/build.py` – builds `public/` (no network). Stable product URLs kept in `data/slugs.json`.
- `scripts/nightly.sh` – cron/routine wrapper, logs to `logs/YYYY-MM-DD.log`; runs `./deploy.sh` if present (not created yet)
- `config.json` – site name, **base_url (set to real domain before deploying)**, approved affiliate links by HMRC productId, contact email, Search Console verification token
- `public/` – the built site (deploy this folder)

## Commands
    python3 scripts/update.py            # full nightly run (≈2 min, 104 polite requests)
    python3 scripts/update.py --no-fetch # rebuild from stored data
    python3 -m http.server 8765 --directory public   # preview at http://localhost:8765/

## Rules
- Software list, not tax advice. No rankings ("best") the data can't support.
- Affiliate links only after approval; they're added in config.json and rendered rel="sponsored" with disclosure.
- If the fetch fails or returns <20 products, the previous data and site are kept (exit 2).
