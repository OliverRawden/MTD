#!/usr/bin/env python3
"""Build the static site into ./public from data/*.json. No network access."""
import json, re, html, csv, shutil, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "public"
CFG = json.loads((ROOT / "config.json").read_text())
SITE = CFG["site_name"]
BASE = CFG["base_url"].rstrip("/")
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)

HMRC_FINDER = "https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/"
GOV_WHEN = "https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax"
GOV_QTR = "https://www.gov.uk/guidance/use-making-tax-digital-for-income-tax/send-quarterly-updates"
GOV_CHOOSE = "https://www.gov.uk/guidance/choose-the-right-software-for-making-tax-digital-for-income-tax"
GOV_SIGNUP = "https://www.gov.uk/guidance/sign-up-for-making-tax-digital-for-income-tax"
GOV_EXEMPT = "https://www.gov.uk/guidance/apply-for-an-exemption-from-making-tax-digital-for-income-tax"
OGL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"

data = json.loads((DATA / "products.json").read_text())
P = data["products"]
changes = json.loads((DATA / "changes.json").read_text()) if (DATA / "changes.json").exists() else []
fetched = dt.datetime.fromisoformat(data["fetched_at"]).astimezone()
CHECKED = fetched.strftime("%-d %B %Y")
CHECKED_ISO = fetched.date().isoformat()

# ---------- stable slugs ----------
slug_file = DATA / "slugs.json"
slugs = {int(k): v for k, v in json.loads(slug_file.read_text()).items()} if slug_file.exists() else {}
def slugify(s):
    s = s.lower().replace("&", " and ").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70] or "product"
used = set(slugs.values())
for p in sorted(P, key=lambda x: x["id"]):
    if p["id"] not in slugs:
        s = slugify(p["name"])
        if s in used: s = f"{s}-{p['id']}"
        slugs[p["id"]] = s; used.add(s)
slug_file.write_text(json.dumps({str(k): v for k, v in sorted(slugs.items())}, indent=1))
for p in P: p["slug"] = slugs[p["id"]]

# ---------- derived facts ----------
READY, DEV, NO = "Ready now", "In development", "Not included"
def feat(p, k): return p["features"].get(k)
def q(p, k): return p["quarterly_income_sources"].get(k)
def tr(p, k): return p["tax_return_items"].get(k)
def spec(p, k): return p["specs"].get(k, [])
def is_free(p): return feat(p, "Free version") == READY or p["price"] == "Free version"
def creates(p): return feat(p, "Software that creates digital records") == READY
def bridging(p): return feat(p, "Bridging software that connects to records") == READY
def files_return(p): return "Tax return" in p["submission_type"]
def mobile(p): return bool(spec(p, "Mobile App"))
def welsh(p): return "Welsh" in spec(p, "Language")
def assist(p): return feat(p, "HMRC Assist (Submission Feedback)") == READY
def vat(p): return feat(p, "Making Tax Digital for VAT") == READY
def ready_count(p): return sum(1 for v in p["tax_return_items"].values() if v == READY)
TR_ITEMS = list(P[0]["tax_return_items"].keys()) if P else []
ACCESS = ["Blindness or impaired vision", "Deafness or impaired hearing", "Motor or physical difficulties", "Cognitive impairments"]

# ---------- page helpers ----------
CSS = """
:root{--ink:#1b1f23;--mut:#5b6670;--line:#dde3e8;--bg:#fff;--soft:#f5f7f9;--acc:#0b5cad;--ok:#0a7a3e;--dev:#8a5a00;--no:#a1262b}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--acc)}a:hover{text-decoration:none}
.wrap{max-width:1060px;margin:0 auto;padding:0 18px}
header.site{border-bottom:1px solid var(--line);background:#fff}header.site .wrap{display:flex;gap:18px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:12px 18px}
.brand{font-weight:700;color:var(--ink);text-decoration:none;font-size:1.1rem}nav a{margin-left:14px;text-decoration:none;font-size:.95rem}
main{padding:22px 0 40px}h1{font-size:1.9rem;line-height:1.2;margin:.3em 0 .4em}h2{font-size:1.35rem;margin:1.6em 0 .5em}h3{font-size:1.08rem;margin:1.2em 0 .3em}
.lede{font-size:1.1rem;color:#333}.mut{color:var(--mut);font-size:.92rem}.crumbs{font-size:.88rem;color:var(--mut)}
.note{background:var(--soft);border-left:4px solid var(--acc);padding:10px 14px;margin:14px 0;font-size:.95rem}
.warn{border-left-color:var(--dev)}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:.95rem}th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}th{background:var(--soft);font-weight:600}
.t{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.8rem;font-weight:600;white-space:nowrap}
.t-ok{background:#e3f4ea;color:var(--ok)}.t-dev{background:#fdf1d8;color:var(--dev)}.t-no{background:#fbe6e7;color:var(--no)}.t-free{background:#e6effa;color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:8px;padding:12px 14px;background:#fff}.card h3{margin:0 0 4px;font-size:1.02rem}.card p{margin:4px 0;font-size:.88rem;color:var(--mut)}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}.stat{background:var(--soft);border-radius:8px;padding:10px 14px;min-width:140px}.stat b{display:block;font-size:1.5rem}
.filters{background:var(--soft);border-radius:8px;padding:12px 14px;margin:12px 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:4px 16px;font-size:.93rem}
.filters fieldset{border:0;margin:0;padding:0}.filters legend{font-weight:600;margin-bottom:2px}.filters label{display:block}
#dir tr[hidden]{display:none}.btn{display:inline-block;background:var(--acc);color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none}
footer{border-top:1px solid var(--line);background:var(--soft);font-size:.86rem;color:var(--mut);padding:18px 0 28px}
details{margin:6px 0}summary{cursor:pointer;font-weight:600}
@media(max-width:640px){nav a{margin:0 10px 0 0}h1{font-size:1.5rem}.hide-sm{display:none}}
"""

def tag(status):
    c = {READY: "t-ok", DEV: "t-dev", NO: "t-no"}.get(status, "")
    return f'<span class="t {c}">{E(status or "—")}</span>'

def page(path, title, desc, body, depth, jsonld=None, crumbs=None, extra_head=""):
    """path like 'software/xero/' ; writes OUT/path/index.html (or exact file if endswith .html)"""
    r = "../" * depth
    canon = f"{BASE}/{path}"
    lds = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    if crumbs:
        items = [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{BASE}/{u}"} for i, (n, u) in enumerate(crumbs)]
        lds += f'<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}, ensure_ascii=False)}</script>'
        cr = '<div class="crumbs">' + " › ".join(f'<a href="{r}{u}">{E(n)}</a>' if i < len(crumbs) - 1 else E(n) for i, (n, u) in enumerate(crumbs)) + "</div>"
    else:
        cr = ""
    gsv = f'<meta name="google-site-verification" content="{E(CFG["google_site_verification"])}">' if CFG.get("google_site_verification") else ""
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{E(canon)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="{E(SITE)}"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{E(canon)}"><meta property="og:locale" content="en_GB">
<meta name="twitter:card" content="summary">{gsv}
<link rel="stylesheet" href="{r}assets/style.css"><link rel="icon" href="{r}assets/favicon.svg" type="image/svg+xml">{extra_head}{lds}</head>
<body><header class="site"><div class="wrap"><a class="brand" href="{r}">{E(SITE)}</a><nav><a href="{r}software/">All software</a><a href="{r}guides/">Guides</a><a href="{r}changes/">What changed</a><a href="{r}about/">About</a></nav></div></header>
<main><div class="wrap">{cr}{body}</div></main>
<footer><div class="wrap"><p><strong>A software list, not tax advice.</strong> HMRC does not recommend any product and neither do we. Check whether and when you need Making Tax Digital on <a href="{GOV_WHEN}">GOV.UK</a>, and speak to an accountant if unsure.</p>
<p>Product data from HMRC's <a href="{HMRC_FINDER}">software finder</a>, last checked {E(CHECKED)}. Contains public sector information licensed under the <a href="{OGL}">Open Government Licence v3.0</a>. © Crown copyright. Not affiliated with or endorsed by HMRC.</p>
<p><a href="{r}about/">About, disclaimer &amp; affiliate disclosure</a> · <a href="{r}data/products.csv">Download the data (CSV)</a> · <a href="{r}sitemap.xml">Sitemap</a></p></div></footer></body></html>"""
    f = OUT / path / "index.html" if (path == "" or path.endswith("/")) else OUT / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(re.sub(r"\n\s*\n", "\n", doc))
    sitemap.append((canon, CHECKED_ISO))

def out_link(p):
    """Vendor link. If an approved affiliate link is configured, mark it sponsored and disclose."""
    aff = CFG.get("affiliate_links", {}).get(str(p["id"]))
    if aff:
        return f'<a class="btn" href="{E(aff)}" rel="sponsored noopener" target="_blank">Visit {E(p["name"])} website</a> <span class="mut">(affiliate link — <a href="../../about/#affiliate">how we make money</a>)</span>'
    if p.get("website"):
        return f'<a class="btn" href="{E(p["website"])}" rel="noopener nofollow" target="_blank">Visit {E(p["name"])} website</a>'
    return ""

def product_row(p, r):
    srcs = ", ".join(p["income_sources"])
    return (f'<tr data-p="{p["id"]}"><td><a href="{r}software/{p["slug"]}/">{E(p["name"])}</a>{" " + "<span class=\"t t-free\">Free version</span>" if is_free(p) else ""}</td>'
            f'<td>{E(" + ".join("Records" if "creates" in t else "Bridging" for t in p["software_type"]))}</td>'
            f'<td>{E(srcs)}</td><td>{E(", ".join(p["submission_type"]))}</td>'
            f'<td class="hide-sm">{ready_count(p)}/{len(TR_ITEMS)}</td></tr>')

def product_table(items, r, tid=None):
    head = '<tr><th>Software</th><th>Type</th><th>Income sources (quarterly)</th><th>Submits</th><th class="hide-sm" title="Other income items for the tax return marked Ready now by HMRC">Tax-return items ready</th></tr>'
    rows = "".join(product_row(p, r) for p in sorted(items, key=lambda x: x["name"].lower()))
    return f'<table{f" id={chr(34)}{tid}{chr(34)}" if tid else ""}><thead>{head}</thead><tbody>{rows}</tbody></table>'

def itemlist(name, items):
    return {"@context": "https://schema.org", "@type": "ItemList", "name": name, "numberOfItems": len(items),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{BASE}/software/{p['slug']}/", "name": p["name"]}
                                for i, p in enumerate(sorted(items, key=lambda x: x["name"].lower()))]}

def faq(pairs):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": qq, "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}} for qq, a in pairs]}

def faq_html(pairs):
    return "".join(f"<h3>{E(qq)}</h3><p>{a}</p>" for qq, a in pairs)

# ---------- build ----------
if OUT.exists(): shutil.rmtree(OUT)
(OUT / "assets").mkdir(parents=True)
(OUT / "assets/style.css").write_text(re.sub(r"\n", "", CSS))
(OUT / "assets/favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#0b5cad"/><text x="16" y="22" font-size="14" text-anchor="middle" fill="#fff" font-family="Arial" font-weight="700">MTD</text></svg>')
sitemap = []

N = len(P)
free = [p for p in P if is_free(p)]
bridge = [p for p in P if bridging(p)]
landlord = [p for p in P if q(p, "UK property") == READY]
foreign = [p for p in P if q(p, "Foreign property") == READY]
soletrader = [p for p in P if q(p, "Sole trader") == READY]
cis = [p for p in P if tr(p, "Construction Industry Scheme") in (READY, DEV)]
cis_ready = [p for p in P if tr(p, "Construction Industry Scheme") == READY]
full = [p for p in P if files_return(p)]
mob = [p for p in P if mobile(p)]
cy = [p for p in P if welsh(p)]
assist_l = [p for p in P if assist(p)]
vat_l = [p for p in P if vat(p)]
mac = [p for p in P if "Mac OS" in spec(p, "Compatible with")]
linux = [p for p in P if "Linux" in spec(p, "Compatible with")]

# guides: intent pages (slug, h1, title, meta, intro html, items, how-selected, extra)
GUIDES = [
 ("free-mtd-software", "Free MTD for Income Tax software",
  f"Free MTD Software for Income Tax ({len(free)} HMRC-recognised options) | {SITE}",
  f"{len(free)} products on HMRC's MTD for Income Tax list have a free version. Compare income sources, bridging vs records, and tax-return coverage. Checked {CHECKED}.",
  f"<p>HMRC says free products are available \u201cfor those with simple tax affairs but there may be limits on how the product can be used, for example they could have a limited number of transactions\u201d (<a href=\"{GOV_CHOOSE}\">GOV.UK</a>). Of the {N} products HMRC currently recognises, <strong>{len(free)}</strong> are marked as having a free version. Check each provider's site for the limits.</p>",
  free, "HMRC feature \u201cFree version\u201d = Ready now."),
 ("mtd-software-for-landlords", "MTD software for landlords (UK property)",
  f"Best MTD Software for Landlords? {len(landlord)} HMRC-Recognised Options Compared",
  f"{len(landlord)} products can send MTD quarterly updates for UK property income. Filter by free, bridging, foreign property and tax-return coverage. HMRC data, checked {CHECKED}.",
  f"<p>Landlords with qualifying income over the threshold must keep digital records of property income and expenses and send quarterly updates (<a href=\"{GOV_WHEN}\">GOV.UK</a>). These <strong>{len(landlord)}</strong> products are marked by HMRC as <em>Ready now</em> for UK property quarterly updates. We don't rank them as \u201cbest\u201d \u2014 HMRC recommends none \u2014 but the table shows the facts that decide fit. {len([p for p in landlord if is_free(p)])} of them have a free version and {len([p for p in landlord if q(p,'Foreign property')==READY])} also handle foreign property.</p><p class=\"note\">Jointly let property: GOV.UK explains you can choose to include property income only in quarterly updates and report jointly-let expenses later (<a href=\"{GOV_QTR}\">GOV.UK</a>).</p>",
  landlord, "HMRC quarterly income source \u201cUK property\u201d = Ready now."),
 ("mtd-software-for-sole-traders", "MTD software for sole traders (self-employment)",
  f"Best MTD Software for Sole Traders? {len(soletrader)} HMRC-Recognised Options",
  f"Compare {len(soletrader)} MTD for Income Tax products that send quarterly updates for self-employment income. Free versions, bridging, mobile apps. Checked {CHECKED}.",
  f"<p>Sole traders over the qualifying-income threshold must send quarterly updates from software (<a href=\"{GOV_WHEN}\">GOV.UK</a>). These <strong>{len(soletrader)}</strong> products are marked <em>Ready now</em> for self-employment quarterly updates; {len([p for p in soletrader if is_free(p)])} have a free version and {len([p for p in soletrader if mobile(p)])} have a mobile app.</p>",
  soletrader, "HMRC quarterly income source \u201cSole trader\u201d = Ready now."),
 ("mtd-bridging-software-spreadsheets", "MTD bridging software for spreadsheets",
  f"MTD Bridging Software for Spreadsheets: {len(bridge)} HMRC-Recognised Tools",
  f"Keep your Excel or Google Sheets records and submit to HMRC. {len(bridge)} recognised bridging products for MTD for Income Tax, with free options. Checked {CHECKED}.",
  f"<p>Bridging software \u201cwill connect to existing records kept in spreadsheets or other accounting tools\u201d and make your submissions to HMRC (<a href=\"{GOV_CHOOSE}\">GOV.UK</a>). <strong>{len(bridge)}</strong> products are marked <em>Ready now</em> for bridging; {len([p for p in bridge if is_free(p)])} have a free version. Watch the <em>Submits</em> column: some only send quarterly updates, so you'd need another product for the tax return.</p>",
  bridge, "HMRC feature \u201cBridging software that connects to records\u201d = Ready now."),
 ("mtd-software-quarterly-updates-and-tax-return", "MTD software that does quarterly updates and the tax return",
  f"MTD Software for Quarterly Updates AND Tax Return ({len(full)} products)",
  f"{len(full)} of {N} HMRC-recognised MTD products submit both quarterly updates and the final tax return, so you need only one product. Checked {CHECKED}.",
  f"<p>Under MTD for Income Tax you send quarterly updates and then submit your tax return by 31 January (<a href=\"{GOV_CHOOSE}\">GOV.UK</a>). You can use more than one product, but they must work together. These <strong>{len(full)}</strong> products are listed by HMRC as handling both submission types. The last column shows how many other tax-return income items (pensions, dividends, Student Loan, etc.) are already <em>Ready now</em>.</p>",
  full, "HMRC submission type includes \u201cTax return\u201d."),
 ("mtd-software-for-cis-subcontractors", "MTD software for CIS subcontractors",
  f"MTD Software for CIS Subcontractors: {len(cis_ready)} Ready, {len(cis)-len(cis_ready)} In Development",
  f"Which MTD for Income Tax products handle Construction Industry Scheme deductions on the tax return? {len(cis_ready)} ready now, {len(cis)-len(cis_ready)} in development. Checked {CHECKED}.",
  f"<p>HMRC lists <em>Construction Industry Scheme</em> as a tax-return item. <strong>{len(cis_ready)}</strong> products are marked <em>Ready now</em>; {len(cis)-len(cis_ready)} more are <em>In development</em>, which HMRC defines as \u201cthe software provider has committed to building this in time for the 2026 to 2027 tax return\u201d.</p>",
  cis, "HMRC tax-return item \u201cConstruction Industry Scheme\u201d = Ready now or In development."),
 ("mtd-software-foreign-property", "MTD software for foreign property income",
  f"MTD Software for Foreign Property Income ({len(foreign)} products)",
  f"{len(foreign)} HMRC-recognised MTD for Income Tax products send quarterly updates for foreign property. Compare free, bridging and tax-return coverage. Checked {CHECKED}.",
  f"<p>If you let property abroad, your software must support foreign property as a quarterly income source. HMRC marks <strong>{len(foreign)}</strong> products as <em>Ready now</em> for it.</p>",
  foreign, "HMRC quarterly income source \u201cForeign property\u201d = Ready now."),
 ("mtd-software-with-mobile-app", "MTD software with a mobile app",
  f"MTD for Income Tax Software with a Mobile App ({len(mob)} products)",
  f"{len(mob)} HMRC-recognised MTD products offer an Android and/or iPhone app for recording income, expenses and receipts. Checked {CHECKED}.",
  f"<p>HMRC records which platforms each product runs on. <strong>{len(mob)}</strong> list a mobile app ({len([p for p in mob if 'Android' in spec(p,'Mobile App')])} Android, {len([p for p in mob if 'Apple iOS' in spec(p,'Mobile App')])} Apple iOS).</p>",
  mob, "HMRC specification \u201cMobile App\u201d is listed."),
 ("mtd-software-hmrc-assist", "MTD software with HMRC Assist",
  f"MTD Software with HMRC Assist Submission Feedback ({len(assist_l)} products)",
  f"HMRC Assist flags likely mistakes on your tax return. {len(assist_l)} recognised MTD products have it ready now. Checked {CHECKED}.",
  f"<p>GOV.UK describes HMRC Assist as a feature that \u201cprovides feedback and highlights errors for your tax return\u201d using your submissions and data HMRC holds (<a href=\"{GOV_CHOOSE}\">GOV.UK</a>). <strong>{len(assist_l)}</strong> products have it <em>Ready now</em>.</p>",
  assist_l, "HMRC feature \u201cHMRC Assist (Submission Feedback)\u201d = Ready now."),
 ("mtd-software-also-for-vat", "MTD software that also does VAT",
  f"MTD Software for Income Tax and VAT ({len(vat_l)} products)",
  f"VAT-registered? {len(vat_l)} HMRC-recognised MTD for Income Tax products are also marked compatible with MTD for VAT. Checked {CHECKED}.",
  f"<p>GOV.UK suggests VAT-registered businesses check whether their VAT software also works for MTD for Income Tax (<a href=\"{GOV_CHOOSE}\">GOV.UK</a>). <strong>{len(vat_l)}</strong> products are marked <em>Ready now</em> for MTD for VAT.</p>",
  vat_l, "HMRC feature \u201cMaking Tax Digital for VAT\u201d = Ready now."),
 ("mtd-software-mac-linux", "MTD software for Mac and Linux",
  f"MTD for Income Tax Software for Mac ({len(mac)}) and Linux ({len(linux)})",
  f"{len(mac)} recognised MTD products run on Mac OS and {len(linux)} on Linux (mostly web-based). Compare from HMRC's list, checked {CHECKED}.",
  f"<p>Most products are web-based. HMRC lists <strong>{len(mac)}</strong> as compatible with Mac OS and <strong>{len(linux)}</strong> with Linux.</p>",
  [p for p in P if p in mac or p in linux], "HMRC specification \u201cCompatible with\u201d includes Mac OS or Linux."),
 ("mtd-software-in-welsh", "MTD software available in Welsh",
  f"MTD for Income Tax Software in Welsh (Cymraeg) \u2013 {len(cy)} products",
  f"{len(cy)} HMRC-recognised MTD for Income Tax products are available in Welsh. Checked {CHECKED}.",
  f"<p>HMRC lists <strong>{len(cy)}</strong> products with Welsh as a language.</p>", cy, "HMRC specification \u201cLanguage\u201d includes Welsh."),
]

# product pages
def related(p):
    same = [x for x in P if x["id"] != p["id"] and set(x["software_type"]) == set(p["software_type"]) and set(p["income_sources"]) <= set(x["income_sources"])]
    same.sort(key=lambda x: (-ready_count(x), x["name"].lower()))
    return same[:6]

def guides_for(p):
    g = []
    for slug, h1, *_rest in GUIDES:
        items = _rest[3]
        if p in items: g.append((slug, h1))
    return g

for p in P:
    r = "../../"
    trc = ready_count(p)
    types = " and ".join(t.lower() for t in p["software_type"])
    desc = (f"{p['name']}: HMRC-recognised MTD for Income Tax software ({p['price'].lower()}). "
            f"{', '.join(p['income_sources'])}; submits {', '.join(p['submission_type']).lower()}. {trc}/{len(TR_ITEMS)} tax-return items ready. Checked {CHECKED}.")
    title = f"{p['name']} – MTD for Income Tax features & HMRC status | {SITE}"
    ft = "".join(f"<tr><td>{E(k)}</td><td>{tag(v)}</td></tr>" for k, v in p["features"].items() if k not in ACCESS)
    acc = "".join(f"<tr><td>{E(k)}</td><td>{tag(p['features'].get(k))}</td></tr>" for k in ACCESS)
    qt = "".join(f"<tr><td>{E(k)}</td><td>{tag(v)}</td></tr>" for k, v in p["quarterly_income_sources"].items())
    tt = "".join(f"<tr><td>{E(k)}</td><td>{tag(v)}</td></tr>" for k, v in p["tax_return_items"].items())
    sp = "".join(f"<tr><td>{E(k)}</td><td>{E(', '.join(v))}</td></tr>" for k, v in p["specs"].items())
    gaps = [k for k, v in p["tax_return_items"].items() if v != READY]
    dev = [k for k, v in p["tax_return_items"].items() if v == DEV]
    noi = [k for k, v in p["tax_return_items"].items() if v == NO]
    summary = (f"<p class=\"lede\">{E(p['name'])} is on HMRC's list of software recognised for Making Tax Digital for Income Tax. "
               f"HMRC lists it as {E(types)}, {('with a free version' if is_free(p) else 'a paid product')}, covering "
               f"{E(', '.join(p['income_sources']).lower())} quarterly updates"
               f"{' and the end-of-year tax return' if files_return(p) else ' (quarterly updates only — you would need another product for the tax return)'}.</p>")
    if files_return(p):
        summary += f"<p>Of the {len(TR_ITEMS)} other tax-return income items HMRC tracks, <strong>{trc}</strong> are ready now"
        summary += (f", {len(dev)} in development" if dev else "") + (f" and {len(noi)} not included" if noi else "") + ".</p>"
    hist = []
    for c in changes:
        if c.get("type") != "diff": continue
        for a in c.get("added", []):
            if a["id"] == p["id"]: hist.append(f"<li>{E(c['date'])}: added to HMRC's list</li>")
        for ch in c.get("changed", []):
            if ch["id"] == p["id"]:
                hist.append(f"<li>{E(c['date'])}: " + "; ".join(f"{E(x['label'])}: {E(x['old'])} → {E(x['new'])}" for x in ch["changes"]) + "</li>")
    hist_html = f"<h2>Change history</h2><ul>{''.join(reversed(hist))}</ul>" if hist else f"<h2>Change history</h2><p class=\"mut\">No changes to this entry since we started tracking HMRC's list ({E(changes[0]['date'] if changes else CHECKED_ISO)}). <a href=\"{r}changes/\">See all changes</a>.</p>"
    rel = related(p)
    rel_html = "<h2>Similar products</h2><div class=\"grid\">" + "".join(
        f'<div class="card"><h3><a href="{r}software/{x["slug"]}/">{E(x["name"])}</a></h3><p>{E(x["price"])} · {E(", ".join(x["income_sources"]))} · {ready_count(x)}/{len(TR_ITEMS)} tax-return items ready</p></div>' for x in rel) + "</div>" if rel else ""
    gl = guides_for(p)
    gl_html = "<p>Listed in: " + ", ".join(f'<a href="{r}guides/{s}/">{E(h)}</a>' for s, h in gl) + "</p>" if gl else ""
    body = f"""<h1>{E(p['name'])}</h1>{summary}
<p>{out_link(p)}</p>
<p class="mut">Source: <a href="{E(p['hmrc_url'])}">HMRC product entry</a> (HMRC productId {p['id']}), last checked {E(CHECKED)}. Prices are not published by HMRC — check the provider's website.</p>
<div class="note"><strong>What the statuses mean (HMRC):</strong> {tag(READY)} ready to use now · {tag(DEV)} provider has committed to building it in time for the 2026 to 2027 tax return · {tag(NO)} not available in this product.</div>
<h2>Software features</h2><table><thead><tr><th>Feature</th><th>Status</th></tr></thead><tbody>{ft}</tbody></table>
<h2>Quarterly updates: income sources</h2><table><thead><tr><th>Income source</th><th>Status</th></tr></thead><tbody>{qt}</tbody></table>
<h2>Tax return: other income and items</h2><table><thead><tr><th>Item</th><th>Status</th></tr></thead><tbody>{tt}</tbody></table>
<h2>Accessibility</h2><table><thead><tr><th>Need</th><th>Status</th></tr></thead><tbody>{acc}</tbody></table>
<h2>Specifications</h2><table><tbody>{sp}</tbody></table>
{gl_html}{hist_html}{rel_html}
<h2>Before you use it</h2><p>You will need to <a href="{GOV_SIGNUP}">sign up for Making Tax Digital for Income Tax</a> and authorise the software with HMRC. Not sure if you need MTD yet? <a href="{GOV_WHEN}">Check on GOV.UK</a>.</p>"""
    app = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": p["name"], "applicationCategory": "FinanceApplication",
           "operatingSystem": ", ".join(spec(p, "Compatible with") + spec(p, "Mobile App")), "url": f"{BASE}/software/{p['slug']}/",
           "inLanguage": ["cy" if l == "Welsh" else "en" for l in spec(p, "Language")], "featureList": [k for k, v in p["features"].items() if v == READY]}
    if p.get("website"): app["sameAs"] = p["website"]
    if is_free(p): app["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "GBP", "description": "Free version (limits may apply; see provider)"}
    page(f"software/{p['slug']}/", title, desc[:300], body, 2, [app], [("Home", ""), ("All software", "software/"), (p["name"], f"software/{p['slug']}/")])

# directory
r = "../"
def chk(name, val, label): return f'<label><input type="checkbox" data-f="{name}" value="{val}"> {E(label)}</label>'
rows = []
for p in sorted(P, key=lambda x: x["name"].lower()):
    attrs = {"src": " ".join(k.replace(" ", "_") for k, v in p["quarterly_income_sources"].items() if v == READY),
             "free": "1" if is_free(p) else "", "type": ("rec " if creates(p) else "") + ("bri" if bridging(p) else ""),
             "ret": "1" if files_return(p) else "", "assist": "1" if assist(p) else "", "vat": "1" if vat(p) else "",
             "mob": "1" if mobile(p) else "", "cy": "1" if welsh(p) else "",
             "cis": "1" if tr(p, "Construction Industry Scheme") == READY else "",
             "os": " ".join(x.split()[-1] for x in spec(p, "Compatible with"))}
    a = " ".join(f'data-{k}="{E(v)}"' for k, v in attrs.items())
    rows.append(product_row(p, r).replace(f'<tr data-p="{p["id"]}">', f"<tr {a}>", 1))
filters = f"""<form class="filters" id="flt" onsubmit="return false">
<fieldset><legend>Quarterly income source</legend>{chk('src','Sole_trader','Sole trader')}{chk('src','UK_property','UK property (landlords)')}{chk('src','Foreign_property','Foreign property')}</fieldset>
<fieldset><legend>Type</legend>{chk('type','rec','Creates digital records')}{chk('type','bri','Bridging (spreadsheets)')}</fieldset>
<fieldset><legend>Must have</legend>{chk('free','1','Free version')}{chk('ret','1','Submits tax return too')}{chk('assist','1','HMRC Assist')}{chk('cis','1','CIS ready on tax return')}</fieldset>
<fieldset><legend>Other</legend>{chk('vat','1','Also MTD for VAT')}{chk('mob','1','Mobile app')}{chk('cy','1','Welsh language')}{chk('os','OS','Mac')}{chk('os','Linux','Linux')}</fieldset>
<div><span id="cnt">{N}</span> of {N} shown · <a href="#" id="clr">Clear</a></div></form>"""
js = """<script>(function(){var f=document.getElementById('flt'),rows=[].slice.call(document.querySelectorAll('#dir tbody tr')),c=document.getElementById('cnt');
function run(){var on=[].slice.call(f.querySelectorAll('input:checked')),n=0;rows.forEach(function(r){var ok=on.every(function(i){var v=r.getAttribute('data-'+i.dataset.f)||'';return v.split(' ').indexOf(i.value)>-1});r.hidden=!ok;if(ok)n++});c.textContent=n;
var q=on.map(function(i){return i.dataset.f+'='+i.value}).join('&');history.replaceState(null,'',q?'?'+q:location.pathname)}
f.addEventListener('change',run);document.getElementById('clr').onclick=function(e){e.preventDefault();f.reset();run()};
new URLSearchParams(location.search).forEach(function(v,k){var i=f.querySelector('input[data-f="'+k+'"][value="'+v+'"]');if(i)i.checked=true});run()})();</script>"""
head = '<tr><th>Software</th><th>Type</th><th>Income sources (quarterly)</th><th>Submits</th><th class="hide-sm" title="Other income items for the tax return marked Ready now by HMRC">Tax-return items ready</th></tr>'
body = f"""<h1>All {N} HMRC-recognised MTD for Income Tax software products</h1>
<p class="lede">The complete list from HMRC's software finder, with filters for the features HMRC records. Tick boxes to narrow it down; every product links to a page with its full HMRC feature table.</p>
<p class="mut">Last checked {E(CHECKED)}. HMRC shows results in random order and doesn't recommend any product; we sort A–Z. “Tax-return items ready” counts the {len(TR_ITEMS)} other income items (pensions, dividends, CIS, Student Loan…) HMRC marks Ready now.</p>
{filters}<table id="dir"><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>
<p>Prefer a shortcut? See the <a href="{r}guides/">guides</a>: {', '.join(f'<a href="{r}guides/{g[0]}/">{E(g[1].replace("MTD software ","").replace("MTD ",""))}</a>' for g in GUIDES[:5])}.</p>{js}"""
page("software/", f"All {N} MTD for Income Tax Software Products – Filterable List | {SITE}",
     f"Filter all {N} HMRC-recognised Making Tax Digital for Income Tax products by landlord, sole trader, free version, bridging, tax return, HMRC Assist, CIS and more. Checked {CHECKED}.",
     body, 1, [itemlist("HMRC-recognised MTD for Income Tax software", P)], [("Home", ""), ("All software", "software/")])

# guides
for slug, h1, title, desc, intro, items, method in GUIDES:
    r = "../../"
    fr = [p for p in items if is_free(p)]
    body = f"""<h1>{E(h1)}</h1>{intro}
<div class="stats"><div class="stat"><b>{len(items)}</b>products</div><div class="stat"><b>{len(fr)}</b>with a free version</div><div class="stat"><b>{len([p for p in items if files_return(p)])}</b>also submit the tax return</div><div class="stat"><b>{len([p for p in items if bridging(p)])}</b>offer bridging</div></div>
{product_table(items, r)}
<p class="mut"><strong>How this list is made:</strong> {E(method)} Data from HMRC's <a href="{HMRC_FINDER}">software finder</a>, checked {E(CHECKED)}, updated automatically when HMRC changes it. Sorted A–Z; inclusion is not a recommendation. <a href="{r}software/">Filter the full list</a> for more combinations.</p>
<p>Related: {' · '.join(f'<a href="{r}guides/{s}/">{E(h)}</a>' for s, h, *_ in GUIDES if s != slug)}</p>"""
    page(f"guides/{slug}/", title, desc[:300], body, 2, [itemlist(h1, items)], [("Home", ""), ("Guides", "guides/"), (h1, f"guides/{slug}/")])

r = "../"
gbody = "<h1>MTD for Income Tax software guides</h1><p class=\"lede\">Shortlists built directly from HMRC's recognised-software data. Each one states exactly how products were selected.</p><div class=\"grid\">" + "".join(
    f'<div class="card"><h3><a href="{r}guides/{s}/">{E(h)}</a></h3><p>{len(items)} products</p></div>' for s, h, _t, _d, _i, items, _m in GUIDES) + "</div>"
page("guides/", f"MTD for Income Tax Software Guides | {SITE}", "Shortlists of HMRC-recognised MTD for Income Tax software for landlords, sole traders, spreadsheets (bridging), free versions, CIS, VAT and more.", gbody, 1, None, [("Home", ""), ("Guides", "guides/")])

# changes page
r = "../"
def change_entry(c):
    if c["type"] == "baseline":
        return f'<h2 id="d{E(c["date"])}">{E(c["date"])}</h2><p>{E(c["note"])}</p>'
    lk = lambda i, n: f'<a href="{r}software/{slugs.get(i, "")}/">{E(n)}</a>' if i in slugs else E(n)
    s = f'<h2 id="d{E(c["date"])}">{E(c["date"])}</h2><p>{len(c["added"])} added, {len(c["removed"])} removed, {len(c["changed"])} updated · {c["count"]} products on the list (compared with {E(c["previous_snapshot"])}).</p>'
    if c["added"]: s += "<h3>Added</h3><ul>" + "".join(f"<li>{lk(a['id'], a['name'])}</li>" for a in c["added"]) + "</ul>"
    if c["removed"]: s += "<h3>Removed from HMRC's list</h3><ul>" + "".join(f"<li>{E(a['name'])}</li>" for a in c["removed"]) + "</ul>"
    if c["changed"]:
        s += "<h3>Updated</h3><ul>" + "".join(f"<li>{lk(ch['id'], ch['name'])}: " + "; ".join(f"{E(x['label'])}: {E(x['old'])} → {E(x['new'])}" for x in ch["changes"][:12]) + (f" (+{len(ch['changes'])-12} more)" if len(ch["changes"]) > 12 else "") + "</li>" for ch in c["changed"]) + "</ul>"
    return s
cbody = f"""<h1>What changed on HMRC's MTD software list</h1>
<p class="lede">We re-read HMRC's list of recognised MTD for Income Tax software every night and record what moved: new products, removals, and features switching from <em>In development</em> to <em>Ready now</em>. Nights with no change get no entry.</p>
<p class="mut">Last checked {E(CHECKED)}. Source: <a href="{HMRC_FINDER}">HMRC software finder</a>.</p>
{''.join(change_entry(c) for c in reversed(changes)) or '<p>No entries yet.</p>'}"""
page("changes/", f"What Changed: HMRC MTD Software List Updates (Nightly Log) | {SITE}", f"Dated log of changes to HMRC's recognised MTD for Income Tax software list: products added or removed and features newly ready. Last checked {CHECKED}.", cbody, 1, None, [("Home", ""), ("What changed", "changes/")])

# about
r = "../"
abody = f"""<h1>About {E(SITE)}</h1>
<p class="lede">{E(SITE)} is an independent, searchable copy of HMRC's list of software recognised for Making Tax Digital for Income Tax, with one page per product and a nightly log of changes.</p>
<h2 id="disclaimer">Disclaimer: a software list, not tax advice</h2>
<p>We list software. We do not give tax, accounting or legal advice, and nothing here tells you whether you must use MTD, which product suits your affairs, or how to complete a return. For that, see <a href="{GOV_WHEN}">GOV.UK</a>, HMRC, or a qualified accountant. HMRC says: “All software listed has been through HMRC's recognition process. HMRC does not recommend any product or software provider.” Neither do we. Inclusion and order are not endorsements. Features and availability can change at any time — always confirm with the provider before you buy.</p>
<h2 id="data">Where the data comes from</h2>
<p>Product names, feature statuses, income sources, specifications and provider website links come from HMRC's <a href="{HMRC_FINDER}">Find software that works with Making Tax Digital for Income Tax</a> service, re-read nightly. Deadlines and explanations quote GOV.UK pages, linked where used. Last checked: {E(CHECKED)}. Pricing is not published by HMRC and we don't guess it.</p>
<p>Contains public sector information licensed under the <a href="{OGL}">Open Government Licence v3.0</a>. © Crown copyright. This site is not affiliated with, endorsed by or connected to HMRC or GOV.UK. You can <a href="{r}data/products.csv">download our copy of the data (CSV)</a> or <a href="{r}data/products.json">JSON</a> under the same licence.</p>
<h2 id="method">How pages are built</h2><p>Every list states the HMRC field it filters on. “Tax-return items ready” counts how many of the {len(TR_ITEMS)} other tax-return items HMRC marks <em>Ready now</em> for that product. We sort A–Z rather than ranking, because the data doesn't support a “best”.</p>
<h2 id="affiliate">Affiliate disclosure</h2><p><em>[Placeholder — to be finalised before any affiliate link goes live.]</em> Some links to software providers may become affiliate links, meaning we may earn a commission if you sign up, at no extra cost to you. Affiliate links will be labelled and marked <code>rel="sponsored"</code>. Commission never affects which products are listed, their order, or the HMRC data shown. Currently: <strong>no affiliate links are active</strong>.</p>
<h2 id="contact">Contact and corrections</h2><p>Spotted something out of date? Product data mirrors HMRC; if HMRC's entry is wrong, providers should update it with HMRC. {('Email ' + E(CFG['contact_email'])) if CFG.get('contact_email') else '<em>[Contact address to be added at launch.]</em>'}</p>"""
page("about/", f"About, Disclaimer & Data Sources | {SITE}", "Independent list of HMRC-recognised MTD for Income Tax software. Not tax advice. Data from HMRC under the Open Government Licence v3.0. Affiliate disclosure.", abody, 1, None, [("Home", ""), ("About", "about/")])

# home
r = ""
FAQ = [
 ("When do I need to use Making Tax Digital for Income Tax?",
  f"It depends on your qualifying income from self-employment and property. GOV.UK: over £50,000 in 2024 to 2025 means from 6 April 2026; over £30,000 in 2025 to 2026 means from 6 April 2027; over £20,000 in 2026 to 2027 means from 6 April 2028. Use HMRC's checker on <a href=\"{GOV_WHEN}\">GOV.UK</a> to confirm."),
 ("Is there free MTD for Income Tax software?",
  f"Yes. {len(free)} of the {N} products HMRC currently recognises have a free version, though HMRC notes free products may have limits, such as a limited number of transactions. See <a href=\"guides/free-mtd-software/\">free MTD software</a>."),
 ("Can I keep using spreadsheets?",
  f"Yes, with bridging software that connects your spreadsheet records to HMRC. {len(bridge)} recognised products offer bridging. See <a href=\"guides/mtd-bridging-software-spreadsheets/\">bridging software</a>."),
 ("When are quarterly updates due?",
  f"For both standard and calendar update periods the deadlines are 7 August, 7 November, 7 February and 7 May (<a href=\"{GOV_QTR}\">GOV.UK</a>). The tax return is still due by 31 January after the tax year."),
 ("Which MTD software does HMRC recommend?",
  "None. HMRC says all listed software has passed its recognition process but it does not recommend any product or provider. This site doesn't either; it lists the facts so you can compare."),
]
recent = [c for c in reversed(changes) if c["type"] == "diff"][:3]
recent_html = "".join(f'<li><a href="changes/#d{E(c["date"])}">{E(c["date"])}</a>: {len(c["added"])} added, {len(c["removed"])} removed, {len(c["changed"])} updated</li>' for c in recent) or f"<li>Tracking started {E(changes[0]['date'] if changes else CHECKED_ISO)} with {N} products. Changes will appear here as HMRC updates its list.</li>"
hbody = f"""<h1>Find MTD for Income Tax software: all {N} HMRC-recognised products</h1>
<p class="lede">Making Tax Digital (MTD) for Income Tax means sole traders and landlords over an income threshold must keep digital records and send HMRC quarterly updates from compatible software. This site lists every product HMRC recognises, with filters and a full feature page for each — checked every night.</p>
<p><a class="btn" href="software/">Browse and filter all {N} products</a></p>
<div class="stats"><div class="stat"><b>{N}</b>recognised products</div><div class="stat"><b>{len(free)}</b>with a free version</div><div class="stat"><b>{len(landlord)}</b>for UK property</div><div class="stat"><b>{len(bridge)}</b>bridging (spreadsheets)</div><div class="stat"><b>{len(full)}</b>also file the tax return</div></div>
<h2>Who needs MTD for Income Tax, and when</h2>
<p>You need it if you're a sole trader or landlord registered for Self Assessment, with income from self-employment or property, and your <em>qualifying income</em> is over the threshold (<a href="{GOV_WHEN}">GOV.UK</a>):</p>
<table><thead><tr><th>Qualifying income over</th><th>In tax year</th><th>Use MTD from</th></tr></thead><tbody>
<tr><td>£50,000</td><td>2024 to 2025</td><td>6 April 2026 (already started)</td></tr>
<tr><td>£30,000</td><td>2025 to 2026</td><td>6 April 2027</td></tr>
<tr><td>£20,000</td><td>2026 to 2027</td><td>6 April 2028</td></tr></tbody></table>
<p class="mut">Partnerships will join later; HMRC hasn't set a date. Some people can get an <a href="{GOV_EXEMPT}">exemption</a>, for example if digitally excluded. Source checked {E(CHECKED)}.</p>
<h2>Quarterly update deadlines</h2>
<table><thead><tr><th>Standard period (tax year)</th><th>Calendar period</th><th>Deadline</th></tr></thead><tbody>
<tr><td>6 April – 5 July</td><td>1 April – 30 June</td><td>7 August</td></tr><tr><td>6 April – 5 October</td><td>1 April – 30 September</td><td>7 November</td></tr>
<tr><td>6 April – 5 January</td><td>1 April – 31 December</td><td>7 February</td></tr><tr><td>6 April – 5 April</td><td>1 April – 31 March</td><td>7 May (following tax year)</td></tr></tbody></table>
<p class="mut">Updates are cumulative from the start of the tax year. Source: <a href="{GOV_QTR}">GOV.UK – send quarterly updates</a>.</p>
<h2>Start with your situation</h2><div class="grid">{''.join(f'<div class="card"><h3><a href="guides/{s}/">{E(h)}</a></h3><p>{len(items)} products</p></div>' for s, h, _t, _d, _i, items, _m in GUIDES[:8])}</div>
<h2>Records software or bridging software?</h2>
<p>GOV.UK describes two types: software that <strong>creates digital records</strong> (bank feeds, receipt scanning or manual entry) and usually does everything, and <strong>bridging software</strong> that connects existing records such as spreadsheets to HMRC (<a href="{GOV_CHOOSE}">GOV.UK</a>). You can use more than one product, but only one per submission.</p>
<h2>Latest changes to HMRC's list</h2><ul>{recent_html}</ul><p><a href="changes/">Full change log</a></p>
<h2>Frequently asked questions</h2>{faq_html(FAQ)}"""
page("", f"MTD for Income Tax Software Finder – All {N} HMRC-Recognised Products", f"Compare all {N} HMRC-recognised Making Tax Digital for Income Tax products for sole traders and landlords: free versions, bridging, tax return support. Deadlines from GOV.UK. Updated nightly.", hbody, 0,
     [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE, "url": BASE + "/"}, faq(FAQ)])

# 404, data, robots, sitemap
(OUT / "404.html").write_text(f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Page not found | {E(SITE)}</title><meta name="robots" content="noindex"><link rel="stylesheet" href="/assets/style.css"></head><body><main><div class="wrap"><h1>Page not found</h1><p>The product may have been renamed or removed from HMRC\'s list. <a href="/software/">See all software</a> or <a href="/changes/">what changed</a>.</p></div></main></body></html>')
(OUT / "data").mkdir()
shutil.copy(DATA / "products.json", OUT / "data/products.json")
with open(OUT / "data/products.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["hmrc_product_id", "name", "price", "software_type", "submission_type", "income_sources", "website", "hmrc_url", "hmrc_assist", "mtd_vat", "cis_on_tax_return", "tax_return_items_ready", "compatible_with", "mobile_app", "language", "page"])
    for p in sorted(P, key=lambda x: x["name"].lower()):
        w.writerow([p["id"], p["name"], p["price"], "; ".join(p["software_type"]), "; ".join(p["submission_type"]), "; ".join(p["income_sources"]), p["website"], p["hmrc_url"],
                    feat(p, "HMRC Assist (Submission Feedback)"), feat(p, "Making Tax Digital for VAT"), tr(p, "Construction Industry Scheme"), ready_count(p),
                    "; ".join(spec(p, "Compatible with")), "; ".join(spec(p, "Mobile App")), "; ".join(spec(p, "Language")), f"{BASE}/software/{p['slug']}/"])
(OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
(OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    "".join(f"<url><loc>{E(u)}</loc><lastmod>{d}</lastmod></url>\n" for u, d in sitemap) + "</urlset>\n")
(OUT / ".nojekyll").write_text("")
if "example.invalid" in BASE:
    print("WARNING: config.json base_url is a placeholder; set the real domain before deploying (canonicals/sitemap use it).")
print(f"built {len(sitemap)} indexable pages ({N} products, {len(GUIDES)} guides) into {OUT}")
