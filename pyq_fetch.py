#!/usr/bin/env python3
"""
Bulk-download DBATU previous-year question papers (user-defined course, defaults to B.Tech)
from the Knimbus library.

First run : a Chrome window opens -> log in to the library yourself -> the script continues.
Next runs : your login is remembered in ./.browser-profile
Re-runs are incremental: already-downloaded papers are skipped (manifest.json).

Usage:
    python pyq_fetch.py                         # uses course & subjects in config.yaml (defaults to B.Tech)
    python pyq_fetch.py --course "B.Tech"       # force B.Tech papers only
    python pyq_fetch.py --course "Diploma"      # download Diploma papers
    python pyq_fetch.py --course "M.Tech"       # download M.Tech papers
    python pyq_fetch.py --course "all"          # download all courses without repository filtering
    python pyq_fetch.py --only "Machine Learning" # fetch for a single subject
    python pyq_fetch.py --debug                 # saves screenshot + HTML when something looks off
"""
import argparse, hashlib, io, json, re, sys, time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse, parse_qsl, urlencode, urlunparse

import yaml
from pypdf import PdfReader

ORD = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8
}
ORD_RE = "|".join(sorted(ORD, key=len, reverse=True))
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


# ------------------------------------------------------------------ Course resolution & heuristics
def resolve_course(course_str: str) -> tuple[str, str]:
    """
    Resolves course input string to:
        (knimbus_repository_label, internal_prog_key)
    Example:
        'btech' -> ('B.Tech Question Paper', 'btech')
        'diploma' -> ('Diploma Question Paper', 'diploma')
        'all' -> ('', 'all')
    """
    if not course_str or course_str.strip().lower() in ("all", "*", "any"):
        return ("", "all")
    c = course_str.strip().lower()
    if "b.tech" in c or "btech" in c or "bachelor of tech" in c:
        return ("B.Tech Question Paper", "btech")
    if "diploma" in c:
        return ("Diploma Question Paper", "diploma")
    if "m.tech" in c or "mtech" in c or "master of tech" in c:
        return ("M.Tech Question Paper", "mtech")
    if "pharm" in c:
        return ("B. Pharmacy Question Paper", "pharmacy")
    if "architect" in c:
        return ("B. Architecture Question Paper", "architecture")
    return (course_str.strip(), course_str.strip().lower())


def classify_code_or_title(code: str, title: str) -> str:
    """
    Heuristically identifies degree programme from DBATU course code and title.
    DBATU code patterns:
      - Diploma: 23DCE..., DME..., DEE..., 21D...
      - B.Tech: BT..., BTECH..., UD...PEC...
      - M.Tech: MT..., MTECH..., MCA...
      - Pharmacy: BP...
      - Architecture: AR..., BARCH...
    """
    code = (code or "").upper()
    title = (title or "").lower()

    # Code-based classification
    if re.search(r"^(2\d)?D[A-Z]{2}|DCE|DME|DEE|DCI|DCH|DPE", code):
        return "diploma"
    if re.search(r"^BT|BTECH|UD.*PEC", code):
        return "btech"
    if re.search(r"^MT|MTECH|MCA", code):
        return "mtech"
    if re.search(r"^BP\d|PHARM", code):
        return "pharmacy"
    if re.search(r"^AR|BARCH", code):
        return "architecture"

    # Title-based classification
    if "diploma" in title:
        return "diploma"
    if "m.tech" in title or "master of tech" in title:
        return "mtech"
    if "b.tech" in title or "bachelor of tech" in title:
        return "btech"
    if "pharmacy" in title:
        return "pharmacy"
    if "architecture" in title:
        return "architecture"

    return "unknown"


# ------------------------------------------------------------------ PDF parsing
def pdf_first_pages_text(data: bytes, pages=2) -> str:
    try:
        r = PdfReader(io.BytesIO(data))
        return "\n".join((r.pages[i].extract_text() or "") for i in range(min(pages, len(r.pages))))
    except Exception:
        return ""


def parse_paper(text: str) -> dict:
    t = re.sub(r"[ \t]+", " ", text)
    low = t.lower()
    info = {}

    # programme
    if "diploma in" in low or "diploma engineering" in low or "diploma" in low:
        info["programme"] = "diploma"
    elif re.search(r"m\.?\s?tech|master of tech|m\.?\s?e\.?\b|mba|mca", low):
        info["programme"] = "mtech"
    elif re.search(r"b\.?\s?tech|bachelor of tech|degree in engineering|faculty of engineering", low):
        info["programme"] = "btech"
    elif re.search(r"pharm", low):
        info["programme"] = "pharmacy"
    elif re.search(r"architect", low):
        info["programme"] = "architecture"
    else:
        info["programme"] = "unknown"

    # semester
    m = re.search(rf"semester\s*[:\-]?\s*({ORD_RE})\b", t, re.I) or \
        re.search(rf"\b({ORD_RE})\s+semester\b", t, re.I) or \
        re.search(rf"\bsem\s*[:\-]?\s*({ORD_RE})\b", t, re.I)
    info["sem"] = ORD.get(m.group(1).lower()) if m else None

    # course code
    m = re.search(r"(?:course|subject|sub|paper)\s*code\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{3,})", t, re.I)
    info["code"] = m.group(1).upper() if m else None

    # exam season + year, then date
    m = re.search(r"(summer|winter|supplementary)[^\d]{0,15}(20\d\d)", t, re.I)
    info["season"] = m.group(1).title() if m else None
    info["year"] = int(m.group(2)) if m else None
    m = re.search(r"date\s*[:\-]?\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(20\d\d)", t, re.I)
    if m:
        info["date"] = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        info["year"] = info["year"] or int(m.group(3))
    return info


def parse_card(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Extract course code in brackets: e.g. [23DCE3204A], [BTCOC603-Y23], [BTAIC502]
    code_m = re.search(r"\[([A-Z0-9\-]+)\]", text, re.I)
    code = code_m.group(1).upper() if code_m else None

    # Extract clean title
    title_candidates = [
        l for l in lines
        if not re.search(r"^(question paper|read|dr\.?\s*babasaheb|summer|winter|supplementary|\d{4})$", l, re.I)
        and not (l.startswith("[") and l.endswith("]"))
    ]
    title = title_candidates[0] if title_candidates else ""
    title = re.sub(r"\[.*?\]", "", title).strip()

    # Extract year (4-digit)
    year_m = re.search(r"\b(20\d\d)\b", text)
    year = int(year_m.group(1)) if year_m else None

    # Extract exam season
    season_m = re.search(r"\b(Summer|Winter|Supplementary)\b", text, re.I)
    season = season_m.group(1).title() if season_m else None

    # Extract month
    month_m = re.search(rf"\b({MONTHS})\b", text, re.I)
    month = month_m.group(1).title() if month_m else None

    # Identify course program from card text and code
    prog = classify_code_or_title(code, title)

    return {
        "title": title,
        "code": code,
        "year": year,
        "season": season,
        "month": month,
        "prog": prog,
    }


# ------------------------------------------------------------------ helpers
def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def with_search(base_url, term):
    u = urlparse(base_url)
    q = dict(parse_qsl(u.query))
    q.pop("curPage", None)
    q.pop("search_within", None)
    qs = urlencode(q) + "&curPage=1&search_within=" + quote(quote(term))  # Knimbus double-encodes search_within
    return urlunparse(u._replace(query=qs))


def dump(page, name):
    Path("debug").mkdir(exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)
    Path(f"debug/{name}.html").write_text(page.content(), encoding="utf-8")


def wait_for_login(page):
    if "login" in page.url:
        print(">>> Log in to the DBATU library in the opened browser window. Waiting...")
        page.wait_for_function("() => !location.href.includes('login')", timeout=0)
        time.sleep(2)


def apply_repository_filter(page, target_repo_label: str):
    """
    Ensures the repository facet filter (e.g. 'B.Tech Question Paper') is checked in Knimbus sidebar.
    """
    if not target_repo_label:
        return

    try:
        # Check if already applied in top active filter tags
        applied = page.locator(".applied-filters, [class*='applied'], [class*='filter-tag']")
        if applied.count() > 0:
            for idx in range(applied.count()):
                if target_repo_label.lower() in applied.nth(idx).inner_text().lower():
                    return

        # Look for the target option in the left sidebar
        repo_item = page.locator(f"xpath=//label[contains(., '{target_repo_label}')] | //span[contains(., '{target_repo_label}')] | //a[contains(., '{target_repo_label}')]")
        if repo_item.count() == 0:
            # If REPOSITORY accordion is collapsed, expand it
            repo_header = page.locator("xpath=//*[normalize-space(text())='REPOSITORY' or contains(text(), 'REPOSITORY')]")
            if repo_header.count() > 0:
                repo_header.first.click()
                page.wait_for_timeout(600)
                repo_item = page.locator(f"xpath=//label[contains(., '{target_repo_label}')] | //span[contains(., '{target_repo_label}')] | //a[contains(., '{target_repo_label}')]")

        if repo_item.count() > 0:
            target = repo_item.first
            cb = target.locator("input[type='checkbox']")
            if cb.count() > 0 and cb.first.is_checked():
                return  # already selected

            print(f"  [filter] Selecting portal repository: '{target_repo_label}'...")
            target.scroll_into_view_if_needed()
            target.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  [filter] Notice: Could not toggle UI repository filter ({e}). Pre-download card filter will enforce course filtering.")


def go_to_next_page(page, current_pg: int) -> bool:
    """
    Navigates to the next page of results. Knimbus uses '>' for the Next button.
    Falls back to clicking the next page number if available.
    Returns False when on the last page.
    """
    try:
        # 1. Click Next ('>') button
        next_btn = page.locator("xpath=//a[normalize-space(text())='>'] | //button[normalize-space(text())='>'] | //li[not(contains(@class, 'disabled'))]/*[normalize-space(text())='>']")
        if next_btn.count() > 0:
            target = next_btn.first
            if target.is_visible():
                parent_cls = target.locator("xpath=..").get_attribute("class") or ""
                btn_cls = target.get_attribute("class") or ""
                if "disabled" not in parent_cls.lower() and "disabled" not in btn_cls.lower():
                    target.scroll_into_view_if_needed()
                    target.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1500)
                    return True

        # 2. Numbered button fallback for current_pg + 1
        target_num = str(current_pg + 1)
        num_btn = page.locator(f"xpath=//*[self::a or self::button or self::li][normalize-space(text())='{target_num}']")
        if num_btn.count() > 0 and num_btn.first.is_visible():
            num_btn.first.scroll_into_view_if_needed()
            num_btn.first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
            return True
    except Exception as e:
        print(f"  [pagination error]: {e}")
    return False


def get_pdf_url(context, page, read_btn):
    """
    Extracts the direct PDF URL from clicking the Read button / opening popup tab.
    """
    # 1. Check if button has direct href
    href = read_btn.get_attribute("href")
    if href and (".pdf" in href.lower() or "s3.amazonaws.com" in href.lower()):
        return href

    # 2. Handle popup tab
    try:
        with context.expect_page(timeout=15000) as pi:
            read_btn.click()
        new = pi.value
        try:
            new.wait_for_url(lambda u: u and u != "about:blank", timeout=15000)
        except Exception:
            pass
        url = new.url
        new.close()
        return url if url != "about:blank" else None
    except Exception as e:
        print(f"    ! popup error: {e}")
        return None


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Bulk-download DBATU previous year question papers from Knimbus.")
    ap.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    ap.add_argument("--only", help="Run only for a specific subject name")
    ap.add_argument("--course", help="Target course/degree type (e.g. 'B.Tech', 'Diploma', 'M.Tech', 'Pharmacy', 'all')")
    ap.add_argument("--debug", action="store_true", help="Save debug screenshots and HTML dumps")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    out = Path(cfg["output_dir"]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    since = cfg.get("since_year", date.today().year - 4)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"hashes": {}, "keys": {}}

    # Determine course type (CLI argument overrides config.yaml, defaults to 'B.Tech Question Paper')
    raw_course = args.course if args.course is not None else cfg.get("course", "B.Tech Question Paper")
    repo_label, prog_target = resolve_course(raw_course)

    print(f"==================================================")
    print(f" DBATU PYQ Fetcher")
    print(f" Target Course : '{repo_label or 'ALL'}' (key: {prog_target})")
    print(f" Min Year      : {since}")
    print(f" Output Folder : {out}")
    print(f"==================================================")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            ".browser-profile",
            channel="chrome",
            headless=False,
            viewport={"width": 1366, "height": 800}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(cfg["base_url"])
        page.wait_for_load_state("networkidle")
        wait_for_login(page)

        for sub in cfg["subjects"]:
            if args.only and args.only.lower() != sub["name"].lower():
                continue

            sem = sub.get("sem")
            allowed = {sem - 1, sem, sem + 1} if isinstance(sem, int) else None
            kws = [k.lower() for k in sub.get("keywords", [])]
            exc = [e.lower() for e in sub.get("exclude", [])]
            codes = {c.upper() for c in sub.get("codes", [])}
            folder = out / slug(sub["name"])
            folder.mkdir(exist_ok=True)
            (out / "_review").mkdir(exist_ok=True)

            print(f"\n=== Subject: {sub['name']} ===")
            if allowed:
                print(f"    Semesters: {sorted(allowed)} | Search: '{sub['search']}'")

            page.goto(with_search(cfg["base_url"], sub["search"]))
            page.wait_for_load_state("networkidle")
            if "login" in page.url:
                wait_for_login(page)
                page.goto(with_search(cfg["base_url"], sub["search"]))
                page.wait_for_load_state("networkidle")

            # Apply UI repository filter (e.g. 'B.Tech Question Paper')
            if repo_label:
                apply_repository_filter(page, repo_label)

            seen_cards, kept = set(), 0
            max_pages = cfg.get("max_pages", 15)

            for pg in range(1, max_pages + 1):
                if pg > 1:
                    has_next = go_to_next_page(page, pg - 1)
                    if not has_next:
                        print(f"  Reached last page at page {pg - 1}.")
                        break

                try:
                    page.wait_for_selector("button:has-text('Read')", timeout=12000)
                except Exception:
                    if args.debug:
                        dump(page, f"{slug(sub['name'])}_p{pg}")
                    print(f"  page {pg}: no results found, stopping.")
                    break

                # Re-verify repository filter state on subsequent pages if needed
                if repo_label and pg == 1:
                    apply_repository_filter(page, repo_label)

                read_buttons = page.locator("button:has-text('Read')")
                n = read_buttons.count()
                print(f"  page {pg}: found {n} paper cards")

                for i in range(n):
                    btn = page.locator("button:has-text('Read')").nth(i)
                    # Find closest parent card container
                    card = btn.locator("xpath=ancestor::*[contains(@class, 'card') or contains(@class, 'item') or count(.//button[normalize-space()='Read'])=1][1]")
                    ctext = card.inner_text() if card.count() > 0 else btn.inner_text()

                    c = parse_card(ctext)
                    card_fingerprint = f"{c['title']}|{c['code']}|{c['year']}|{c['season']}"
                    if card_fingerprint in seen_cards:
                        continue
                    seen_cards.add(card_fingerprint)

                    # 1. Subject keyword and exclusion check on card title
                    tl = c["title"].lower()
                    if not all(k in tl for k in kws) or any(e in tl for e in exc):
                        continue

                    # 2. Year check from card
                    if c["year"] and c["year"] < since:
                        continue

                    # 3. Course check from card (e.g. Reject Diploma [23DCE...] when B.Tech is required)
                    if prog_target != "all":
                        if c["prog"] != "unknown" and c["prog"] != prog_target:
                            print(f"    - Skip non-{prog_target} card: '{c['title']}' [{c['code']}]")
                            continue

                    # 4. Optional course code whitelist check from card
                    if codes and c["code"] and c["code"] not in codes:
                        continue

                    # Fetch PDF URL
                    try:
                        url = get_pdf_url(ctx, page, btn)
                        if not url:
                            print(f"    ! Could not get PDF URL for '{c['title']}'")
                            continue
                        resp = ctx.request.get(url)
                        data = resp.body()
                    except Exception as e:
                        print(f"    ! Fetch error '{c['title']}': {e}")
                        continue

                    if not data.startswith(b"%PDF"):
                        print(f"    ! Response is not a valid PDF: '{c['title']}'")
                        continue

                    h = hashlib.sha256(data).hexdigest()
                    if h in manifest["hashes"]:
                        continue

                    # Inspect PDF body
                    text = pdf_first_pages_text(data)
                    info = parse_paper(text)
                    low = text.lower()

                    year = info["year"] or c["year"] or "NA"
                    code = info["code"] or c["code"] or "NOCODE"
                    season = info["season"] or c["season"] or c["month"] or "NA"
                    sem_num = info["sem"]
                    base = f"{year}_{season}_{code}_sem{sem_num or 'NA'}"

                    verdict = "keep"

                    # Course verification from PDF text
                    if prog_target != "all":
                        # If the PDF explicitly declares another programme (e.g. Diploma paper), skip it
                        if info["programme"] not in (prog_target, "unknown"):
                            print(f"    - Skip: PDF indicates programme is '{info['programme']}' (expected '{prog_target}')")
                            verdict = "skip"
                        elif c["prog"] not in (prog_target, "unknown"):
                            verdict = "skip"

                    # Subject keyword verification from text (only if text layer is present)
                    if text.strip() and verdict == "keep":
                        if not all(k in low for k in kws) or any(e in low for e in exc):
                            verdict = "skip"

                    # Year verification
                    if year != "NA" and int(year) < since:
                        verdict = "skip"

                    # Course code whitelist verification
                    if codes and code not in codes:
                        verdict = "skip"

                    # Semester verification (if semester could be extracted)
                    if allowed and sem_num is not None and sem_num not in allowed:
                        verdict = "skip"

                    # If PDF is scanned (no text layer), but card matched all criteria and course filter, KEEP it!
                    if not text.strip() and verdict == "keep":
                        verdict = "keep"  # Scanned paper from matched course/subject

                    # Ambiguous classification check
                    if prog_target != "all" and info["programme"] == "unknown" and c["prog"] == "unknown" and not repo_label:
                        verdict = "review"

                    if verdict == "skip":
                        manifest["hashes"][h] = "skipped"
                        continue

                    key = f"{code}|{info.get('date') or base}"
                    if key in manifest["keys"]:
                        manifest["hashes"][h] = "duplicate"
                        print(f"    = Duplicate paper: {base}")
                        continue

                    dest = (folder if verdict == "keep" else out / "_review") / f"{slug(sub['name'])}_{base}.pdf"
                    dest.write_bytes(data)
                    manifest["hashes"][h] = str(dest)
                    manifest["keys"][key] = str(dest)
                    kept += (verdict == "keep")
                    print(f"    + [{verdict.upper():6}] {dest.name}")
                    manifest_path.write_text(json.dumps(manifest, indent=2))

            print(f"  -> Total saved for '{sub['name']}': {kept} paper(s)")

        manifest_path.write_text(json.dumps(manifest, indent=2))
        ctx.close()

    print("\nCompleted bulk fetch.")


if __name__ == "__main__":
    main()
