#!/usr/bin/env python3
"""Fetch HMRC's list of software recognised for Making Tax Digital for Income Tax.

Source: https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/
Licence: Open Government Licence v3.0 (Crown copyright), see the footer of that service.

Walks the public finder the same way a person would (choose "show all", then
"agent" view which lists every product), then reads each product's
"features and their availability" page. Read-only; no account or login.

Output: data/products.json (canonical, sorted by HMRC productId) and data/products.csv
"""
import csv, json, re, sys, time, datetime as dt
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE = "https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software"
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "mtd-finder-bot/1.0 (static directory; polite nightly fetch; respects OGL v3 attribution)"
DELAY = 0.6  # seconds between product page requests


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def csrf(html):
    m = re.search(r'name="csrfToken" value="([^"]+)"', html)
    if not m:
        raise RuntimeError("csrfToken not found; HMRC finder layout may have changed")
    return m.group(1)


def get_list(s):
    r = s.get(BASE + "/", timeout=30); r.raise_for_status()
    r = s.post(BASE + "/how-to-find-software", data={"csrfToken": csrf(r.text), "how-you-find-software": "view-all"}, timeout=30); r.raise_for_status()
    r = s.post(BASE + "/about-you", data={"csrfToken": csrf(r.text), "type-of-user": "agent"}, timeout=30); r.raise_for_status()
    if "/software-results" not in r.url:
        raise RuntimeError(f"unexpected page after about-you: {r.url}")
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = clean(soup.h1.get_text()) if soup.h1 else ""
    m = re.search(r"(\d+) software results", h1)
    expected = int(m.group(1)) if m else None
    items = []
    for div in soup.select('div[id^="software-vendor-"]'):
        if not re.fullmatch(r"software-vendor-\d+", div.get("id", "")):
            continue
        name = clean(div.h3.get_text())
        summary = {}
        for row in div.select(".govuk-summary-list__row"):
            summary[clean(row.dt.get_text())] = clean(row.dd.get_text())
        a = div.select_one('a[href*="productId="]')
        pid = int(re.search(r"productId=(\d+)", a["href"]).group(1))
        items.append({"id": pid, "name": name, "summary": summary})
    if expected is not None and len(items) != expected:
        raise RuntimeError(f"parsed {len(items)} products but page says {expected}")
    return items


def table_status(table):
    out = {}
    for tr in table.select("tbody tr"):
        k = clean(tr.th.get_text()) if tr.th else None
        tag = tr.select_one(".govuk-tag")
        if k and tag:
            out[k] = clean(tag.get_text())
    return out


def get_detail(s, pid):
    r = s.get(f"{BASE}/product-details", params={"productId": pid}, timeout=30); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.select_one("main")
    d = {"website": None, "features": {}, "quarterly_income_sources": {}, "tax_return_items": {}, "specs": {}}
    for a in main.select("a[href]"):
        if clean(a.get_text()).startswith("Explore this software on the"):
            d["website"] = a["href"]
            break
    for h2 in main.select("h2"):
        title = clean(h2.get_text())
        nxt = h2.find_next("table") if h2.find_next("table") else None
        if title == "Software features" and nxt:
            d["features"] = table_status(nxt)
        elif title == "What is needed for quarterly updates" and nxt:
            d["quarterly_income_sources"] = table_status(nxt)
        elif title == "What is needed for tax returns" and nxt:
            d["tax_return_items"] = table_status(nxt)
        elif title == "Software specifications":
            dl = h2.find_next("dl")
            for row in dl.select(".govuk-summary-list__row"):
                key = clean(row.dt.get_text())
                lis = [clean(li.get_text()) for li in row.dd.select("li")]
                d["specs"][key] = lis if lis else [clean(row.dd.get_text())]
    return d


def main():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    items = get_list(s)
    products = []
    for i, it in enumerate(sorted(items, key=lambda x: x["id"])):
        time.sleep(DELAY)
        for attempt in range(3):
            try:
                det = get_detail(s, it["id"]); break
            except Exception as e:
                if attempt == 2: raise
                time.sleep(3)
        sm = it["summary"]
        products.append({
            "id": it["id"],
            "name": it["name"],
            "price": sm.get("Price"),
            "software_type": [x.strip() for x in (sm.get("Type of software") or "").split(",") if x.strip()],
            "submission_type": [x.strip() for x in (sm.get("Submission type") or "").split(",") if x.strip()],
            "income_sources": [x.strip() for x in (sm.get("Income sources") or "").split(",") if x.strip()],
            "hmrc_url": f"{BASE}/product-details?productId={it['id']}",
            **det,
        })
        print(f"[{i+1}/{len(items)}] {it['name']}", file=sys.stderr)
    out = {
        "source": BASE + "/",
        "licence": "Open Government Licence v3.0",
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(products),
        "products": products,
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "products.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    with open(DATA / "products.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "price", "software_type", "submission_type", "income_sources", "website", "hmrc_url",
                    "hmrc_assist", "vat", "cis", "os", "software_kind", "language"])
        for p in products:
            sp = p["specs"]
            w.writerow([p["id"], p["name"], p["price"], "; ".join(p["software_type"]), "; ".join(p["submission_type"]),
                        "; ".join(p["income_sources"]), p["website"], p["hmrc_url"],
                        p["features"].get("HMRC Assist (Submission Feedback)"), p["features"].get("Making Tax Digital for VAT"),
                        p["tax_return_items"].get("Construction Industry Scheme"),
                        "; ".join(sp.get("Compatible with", [])),
                        "; ".join(sp.get("Software type", [])), "; ".join(sp.get("Language", []))])
    print(f"saved {len(products)} products", file=sys.stderr)


if __name__ == "__main__":
    main()
