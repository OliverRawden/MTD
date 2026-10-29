#!/usr/bin/env python3
"""Nightly job: refetch HMRC list -> diff vs last snapshot -> log changes -> rebuild site.

- Only appends a 'what changed' entry when something actually changed.
- The first run records a one-off 'tracking started' baseline entry.
- Never deploys, never sends anything. Exit code 0 = ok, 2 = fetch failed (site left untouched).
Usage: python3 scripts/update.py [--no-fetch]
"""
import json, subprocess, sys, datetime as dt, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SNAP = DATA / "snapshots"
CHANGES = DATA / "changes.json"
FIELDS = ["name", "price", "software_type", "submission_type", "income_sources", "website",
          "features", "quarterly_income_sources", "tax_return_items", "specs"]
LABELS = {"name": "Name", "price": "Price", "software_type": "Type of software", "submission_type": "Submission type",
          "income_sources": "Income sources", "website": "Website", "features": "Feature",
          "quarterly_income_sources": "Quarterly updates", "tax_return_items": "Tax return item", "specs": "Specification"}


def fmt(v):
    return ", ".join(v) if isinstance(v, list) else ("—" if v in (None, "") else str(v))


def diff_product(a, b):
    out = []
    for f in FIELDS:
        va, vb = a.get(f), b.get(f)
        if va == vb:
            continue
        if isinstance(va, dict) or isinstance(vb, dict):
            va, vb = va or {}, vb or {}
            for k in sorted(set(va) | set(vb)):
                if va.get(k) != vb.get(k):
                    out.append({"field": f, "key": k, "label": f"{LABELS[f]}: {k}", "old": fmt(va.get(k)), "new": fmt(vb.get(k))})
        else:
            out.append({"field": f, "key": None, "label": LABELS[f], "old": fmt(va), "new": fmt(vb)})
    return out


def diff(old, new):
    o = {p["id"]: p for p in old["products"]}
    n = {p["id"]: p for p in new["products"]}
    added = [{"id": i, "name": n[i]["name"]} for i in sorted(set(n) - set(o))]
    removed = [{"id": i, "name": o[i]["name"]} for i in sorted(set(o) - set(n))]
    changed = []
    for i in sorted(set(o) & set(n)):
        d = diff_product(o[i], n[i])
        if d:
            changed.append({"id": i, "name": n[i]["name"], "changes": d})
    return {"added": added, "removed": removed, "changed": changed}


def main():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    SNAP.mkdir(parents=True, exist_ok=True)
    cur = DATA / "products.json"
    backup = DATA / "products.prev.json"
    if "--no-fetch" not in sys.argv:
        if cur.exists():
            shutil.copy(cur, backup)
        r = subprocess.run([sys.executable, str(ROOT / "scripts/fetch_hmrc.py")], capture_output=True, text=True)
        if r.returncode != 0:
            print("FETCH FAILED; keeping previous data and site.\n" + r.stderr[-2000:], file=sys.stderr)
            if backup.exists():
                shutil.copy(backup, cur)
            sys.exit(2)
    new = json.loads(cur.read_text())
    if new.get("count", 0) < 20:
        print(f"Sanity check failed: only {new.get('count')} products; not publishing.", file=sys.stderr)
        if backup.exists():
            shutil.copy(backup, cur)
        sys.exit(2)
    changes = json.loads(CHANGES.read_text()) if CHANGES.exists() else []
    snaps = sorted(SNAP.glob("*.json"))
    status = "unchanged"
    if not snaps:
        (SNAP / f"{today}.json").write_text(json.dumps(new, indent=1, ensure_ascii=False))
        changes.append({"date": today, "type": "baseline", "count": new["count"],
                        "note": f"Started tracking HMRC's list: {new['count']} recognised products."})
        status = "baseline"
    else:
        old = json.loads(snaps[-1].read_text())
        d = diff(old, new)
        if d["added"] or d["removed"] or d["changed"]:
            (SNAP / f"{today}.json").write_text(json.dumps(new, indent=1, ensure_ascii=False))
            changes = [c for c in changes if not (c["date"] == today and c["type"] == "diff")]
            changes.append({"date": today, "type": "diff", "count": new["count"], "previous_snapshot": snaps[-1].stem, **d})
            status = f"changed: +{len(d['added'])} -{len(d['removed'])} ~{len(d['changed'])}"
    CHANGES.write_text(json.dumps(changes, indent=1, ensure_ascii=False))
    (DATA / "last_checked.json").write_text(json.dumps({"checked_at": new["fetched_at"], "status": status, "count": new["count"]}, indent=1))
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build.py")], capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    if r.returncode != 0:
        sys.exit(3)
    print(f"{today}: {status}")


if __name__ == "__main__":
    main()
