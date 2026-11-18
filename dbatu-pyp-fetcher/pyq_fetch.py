#!/usr/bin/env python3
"""
Bulk-download DBATU previous-year question papers (user-defined course, defaults to B.Tech)
from the Knimbus library.

Filename format:
    sem-year-sum/win-R(regular)/S(supplymentary)-Code[-n].pdf
    (-n appears ONLY when more than 1 distinct paper shares the exact same metadata)

Features:
    - Automatically filters to B.Tech Question Papers (excludes Diploma, M.Tech, MCA, etc.)
    - Automatically avoids Mid-Semester / Class Test papers (dual-layer check: card & PDF)
    - Selects B.Tech, Regular, and Supplementary portal filters via fast JS DOM clicks
    - Pre-download semester check from course code to skip unnecessary PDF fetches
    - Multi-vector PDF download engine (direct href, network capture, download events, popup/embeds)
    - Full multi-page pagination with JS DOM clicks and direct URL fallback
    - Incremental downloads with SHA-256 duplicate detection and automatic collision resolution

Usage:
    python pyq_fetch.py                         # uses course & subjects in config.yaml (defaults to B.Tech)
    python pyq_fetch.py --course "B.Tech"       # force B.Tech papers only
    python pyq_fetch.py --course "Diploma"      # download Diploma papers
    python pyq_fetch.py --course "all"          # download all courses without repository filtering
    python pyq_fetch.py --only "Machine Learning" # fetch for a single subject
    python pyq_fetch.py --headless              # run in headless mode
    python pyq_fetch.py --debug                 # saves screenshot + HTML when something looks off
"""
import argparse, copy, hashlib, io, json, os, re, sys, time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse, parse_qsl, urlencode, urlunparse

import yaml  # type: ignore
from playwright.sync_api import sync_playwright  # type: ignore
from pypdf import PdfReader

# Ensure unbuffered real-time stdout output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore

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


def classify_code_or_title(code: str | None, title: str) -> str:
    """
    Identifies degree programme from DBATU course code and title.
    DBATU code patterns:
      - Diploma: 23DCE..., DME..., DEE..., 21D...
      - B.Tech: BT..., BTECH..., [0-9]{2}(UD|AF)..., UD...PEC..., PEC...
      - M.Tech: MT..., MTECH...
      - MCA: MC..., MCA...
      - Pharmacy: BP...
      - Architecture: AR..., BARCH...
    """
    code = (code or "").upper().strip()
    title = (title or "").lower().strip()

    # Code-based classification
    if re.search(r"^(2\d)?D[A-Z]{2}|DCE|DME|DEE|DCI|DCH|DPE", code):
        return "diploma"
    if re.search(r"^BT|BTECH|^\d{2}(UD|AF)|UD.*PEC|^PEC", code):
        return "btech"
    if re.search(r"^MT|MTECH", code):
        return "mtech"
    if re.search(r"^MC", code):
        return "mca"
    if re.search(r"^BP\d|PHARM", code):
        return "pharmacy"
    if re.search(r"^AR|BARCH", code):
        return "architecture"

    # Title-based classification (with positive-evidence guards)
    if re.search(r"\bdiploma\s+(in|of|engineering)\b", title):
        return "diploma"
    if re.search(r"\bm\.?\s?tech\b|master of tech", title):
        return "mtech"
    if re.search(r"\bmca\b|master of computer app", title):
        return "mca"
    if re.search(r"\bb\.?\s?tech\b|bachelor of tech", title):
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


def parse_paper(text: str) -> dict[str, Any]:
    t = re.sub(r"[ \t]+", " ", text)
    low = t.lower()
    info: dict[str, Any] = {"text": low}

    # Mid-Semester paper check in PDF
    is_mid_sem = bool(re.search(r"\b(mid\s*sem|mid\s*semester|class\s*test|ca-?\d|unit\s*test)\b", low))
    low_marks = bool(re.search(r"\bmax(?:imum)?\s*marks\s*[:\-]?\s*(?:20|25|30)\b", low))
    info["is_mid_sem"] = is_mid_sem or low_marks

    # Programme with positive evidence guards
    if re.search(r"\bb\.?\s?tech\b|bachelor of tech|degree in engineering|faculty of engineering", low):
        info["programme"] = "btech"
    elif re.search(r"\bdiploma\s+(in|of|engineering)\b", low) and not re.search(r"\bb\.?\s?tech\b|bachelor of tech", low):
        info["programme"] = "diploma"
    elif re.search(r"\bm\.?\s?tech\b|master of tech", low):
        info["programme"] = "mtech"
    elif re.search(r"\bmca\b|master of computer app", low):
        info["programme"] = "mca"
    elif re.search(r"\bpharm", low):
        info["programme"] = "pharmacy"
    elif re.search(r"\barchitect", low):
        info["programme"] = "architecture"
    else:
        info["programme"] = "unknown"

    # Semester
    m = re.search(rf"semester\s*[:\-]?\s*({ORD_RE})\b", t, re.I) or \
        re.search(rf"\b({ORD_RE})\s+semester\b", t, re.I) or \
        re.search(rf"\bsem\s*[:\-]?\s*({ORD_RE})\b", t, re.I)
    info["sem"] = ORD.get(m.group(1).lower()) if m else None

    # Course code
    m = re.search(r"(?:course|subject|sub|paper)\s*code\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-_]{3,})", t, re.I)
    info["code"] = m.group(1).upper() if m else None

    # Exam season + year from header (e.g. "End Semester Examination Summer 2026")
    m_pair = re.search(r"\b(Summer|Winter|Supplementary)\b[^\d\n]{0,25}\b(20\d\d)\b", t, re.I)
    if m_pair:
        info["season"] = m_pair.group(1).title()
        info["year"] = int(m_pair.group(2))
    else:
        m_season = re.search(r"\b(Summer|Winter|Supplementary)\b", t, re.I)
        info["season"] = m_season.group(1).title() if m_season else None
        m_year = re.search(r"\b(20\d\d)\b", t)
        info["year"] = int(m_year.group(1)) if m_year else None

    # Exam date
    m_date = re.search(r"date\s*[:\-]?\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(20\d\d)", t, re.I)
    if m_date:
        info["date"] = f"{m_date.group(3)}-{int(m_date.group(2)):02d}-{int(m_date.group(1)):02d}"
        info["year"] = info["year"] or int(m_date.group(3))

    return info


def parse_card(text: str) -> dict[str, Any]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Extract course code in brackets [] or parentheses ()
    code_m = re.search(r"[\[\(]([A-Za-z0-9\-_/\s]+)[\]\)]", text)
    code = re.sub(r"\s+", "", code_m.group(1)).upper() if code_m else None

    # Fallback: Bare DBATU code pattern if not enclosed in brackets/parentheses
    if not code:
        bare_m = re.search(r"\b(2\dD[A-Za-z0-9\-]+|BT[A-Za-z0-9\-]+|\d{2}(?:UD|AF)[A-Za-z0-9\-]+|UD[A-Za-z0-9\-]+|MCA[A-Za-z0-9\-]+|MT[A-Za-z0-9\-]+|BP[A-Za-z0-9\-]+|AR[A-Za-z0-9\-]+)\b", text, re.I)
        code = bare_m.group(1).upper() if bare_m else None

    # Extract clean title: remove [CODE] or (CODE) from title lines
    skip = re.compile(r"^(question paper|read|dr\.?\s*babasaheb.*|(summer|winter|supplementary)( semester)?|\d{4}|"
                      rf"({MONTHS})\s+\d{{4}})$", re.I)
    title_candidates = [l for l in lines if not skip.match(l)]
    title = title_candidates[0] if title_candidates else ""
    clean_title = re.sub(r"\s*[\[\(].*?[\]\)]\s*$", "", title).strip()

    # Extract year & month
    month_m = re.search(rf"\b({MONTHS})\s+(20\d\d)\b", text, re.I)
    year_m = re.search(r"\b(20\d\d)\b", text)
    year = int(month_m.group(2)) if month_m else (int(year_m.group(1)) if year_m else None)

    # Extract exam season
    season_m = re.search(r"\b(Summer|Winter|Supplementary)\b", text, re.I)
    season = season_m.group(1).title() if season_m else None
    month = month_m.group(1).title() if month_m else None

    # Identify course program from card text and code
    prog = classify_code_or_title(code, clean_title or title)

    # Check for mid-semester indicators on the card
    is_mid_sem = bool(re.search(r"\b(mid\s*sem|mid\s*semester|class\s*test|ca-?\d|unit\s*test)\b", text, re.I))

    # Check for supplementary indicators on the card
    is_suppl = bool(re.search(r"\b(supplementary|supplymentary|suppl|atkt)\b", text, re.I))

    return {
        "title": clean_title or title,
        "full_title": title,
        "code": code,
        "year": year,
        "season": season,
        "month": month,
        "prog": prog,
        "is_mid_sem": is_mid_sem,
        "is_suppl": is_suppl,
        "text": text,
    }


# ------------------------------------------------------------------ helpers & formatting
def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def merge_configs(base: dict, secondary: dict) -> dict:
    """
    Deep-merges a secondary configuration onto a base configuration.
    Any setting defined in secondary (output_dir, branches, since_year, course,
    max_pages, filters, credentials) overrides the base configuration.

    If both base and secondary define subjects:
    - Subjects with the same name are merged (secondary properties override base properties).
    - Base subjects not redefined in secondary are preserved.
    - Secondary subjects not in base are added.
    - All subjects are iterated.
    """
    merged = copy.deepcopy(base)
    for key, val in secondary.items():
        if val is None:
            continue
        if key == "subjects":
            base_subs = copy.deepcopy(merged.get("subjects") or [])
            sec_subs = copy.deepcopy(val or [])
            if not base_subs:
                merged["subjects"] = sec_subs
            elif not sec_subs:
                merged["subjects"] = base_subs
            else:
                merged_subs = []
                sec_map = {s["name"].strip().lower(): s for s in sec_subs if isinstance(s, dict) and s.get("name")}
                used_sec = set()

                for b_sub in base_subs:
                    if isinstance(b_sub, dict) and b_sub.get("name"):
                        b_key = b_sub["name"].strip().lower()
                        if b_key in sec_map:
                            # Secondary overrides base subject attributes
                            m_sub = copy.deepcopy(b_sub)
                            m_sub.update(sec_map[b_key])
                            merged_subs.append(m_sub)
                            used_sec.add(b_key)
                        else:
                            merged_subs.append(b_sub)
                    else:
                        merged_subs.append(b_sub)

                for s_sub in sec_subs:
                    if isinstance(s_sub, dict) and s_sub.get("name"):
                        s_key = s_sub["name"].strip().lower()
                        if s_key not in used_sec:
                            merged_subs.append(s_sub)
                    else:
                        merged_subs.append(s_sub)

                merged["subjects"] = merged_subs
        elif isinstance(val, dict) and key in merged and isinstance(merged[key], dict):
            sub_merged = copy.deepcopy(merged[key])
            sub_merged.update(val)
            merged[key] = sub_merged
        else:
            merged[key] = copy.deepcopy(val)
    return merged


def match_subject(sub: dict, query: str) -> bool:
    """
    Smart fuzzy matcher for subject queries.
    Matches exact names, common acronyms (ML, DBMS, ESDMS, TOC, OS, CG),
    substrings (e.g. 'java', 'cyber', 'distributed'), search terms, and keywords.
    """
    q = query.strip().lower()
    name = (sub.get("name") or "").lower()

    # 1. Exact match
    if q == name:
        return True

    # 2. Known abbreviations / Acronym matching
    known_acronyms = {
        "ml": "machine learning",
        "dbms": "database management systems",
        "esdms": "entrepreneurship skills and digital marketing strategies",
        "toc": "theory of computations",
        "os": "operating systems",
        "cg": "computer graphics",
        "ai": "artificial intelligence",
        "aics": "ai in cyber security",
        "cns": "cryptography and network security",
        "cn": "computer networks",
        "bd": "big data",
        "de": "data engineering",
        "cdais": "cloud and distributed ai systems",
    }
    if known_acronyms.get(q) == name:
        return True

    # Generated acronym from title words (e.g. "ESDMS" -> "Entrepreneurship Skills and Digital Marketing Strategies")
    words = [w for w in re.split(r"[\s\-_]+", name) if w]
    generated_acronym = "".join(w[0] for w in words).lower()
    if q == generated_acronym:
        return True

    # 3. Substring match
    if q in name or (len(q) >= 3 and name in q):
        return True

    # 4. Search term match
    search_term = (sub.get("search") or "").lower()
    if q in search_term or (len(q) >= 3 and search_term in q):
        return True

    # 5. Keywords match
    for kw in sub.get("keywords", []):
        kw_l = kw.lower()
        if q in kw_l or kw_l in q:
            return True

    # 6. Word overlap (handles typos/partial phrases like "could and distributed ai systems")
    q_words = set(re.findall(r"[a-z0-9]+", q)) - {"and", "in", "of", "the", "for", "to"}
    name_words = set(re.findall(r"[a-z0-9]+", name)) - {"and", "in", "of", "the", "for", "to"}
    if q_words and name_words and len(q_words & name_words) >= 2:
        return True

    return False


def with_search(base_url, term, subject_filter=None):
    u = urlparse(base_url)
    q = dict(parse_qsl(u.query))
    q.pop("curPage", None)
    q.pop("search_within", None)
    q.pop("sub_category_name", None)
    qs = urlencode(q) + "&curPage=1&search_within=" + quote(quote(term))  # Knimbus double-encodes search_within
    if subject_filter and str(subject_filter).lower() not in ("none", "null", "false", ""):
        knimbus_subjects = subject_filter if isinstance(subject_filter, list) else [subject_filter]
        qs += "&sub_category_name=" + quote(",".join(sorted(knimbus_subjects)))
    return urlunparse(u._replace(query=qs))


def is_allowed_branch(code: str, card_or_pdf_text: str, branches: list[str] | None) -> tuple[bool, str]:
    """
    Checks if a course code or paper text belongs to the allowed branches
    (e.g. Computer Engineering, Computer Science and Engineering, Information Technology).
    Returns (is_allowed, reason).
    """
    if not branches:
        return True, "no branch filter configured"

    c = (code or "").upper().strip()

    # 1. Non-computer / non-IT prefixes in DBATU:
    # BTAR = Automation & Robotics, BTEC = Electronics & Comm, BTET = Electronics & Telecom,
    # BTEX = Electronics, BTVT = VLSI, BTME = Mechanical, BTCE = Civil, BTCH = Chemical, BTEE = Electrical
    if re.search(r"^(BTAR|BTEC|BTET|BTEX|BTVT|BTME|BTCE|BTCH|BTEE)", c):
        return False, f"code prefix '{c[:4]}' is non-CS/IT"

    # 2. Computer / IT prefix in DBATU:
    # BTCOC/BTCOE = Computer Eng, BTCSD/BTCSE = Computer Science, BTIT/BTITOE = IT, BTAIC = AI/Data Science (CSE allied)
    if re.search(r"^(BTCOC|BTCOE|BTCO|BTCSD|BTCSE|BTCS|BTIT|BTITOE|BTAIC|BTAI|\d{2}(?:UD|AF)(?:AIML|AI|CO|CS|IT))", c):
        return True, f"code prefix '{c[:4]}' matches CS/IT"

    # 3. Text analysis from card or PDF header
    low = (card_or_pdf_text or "").lower()
    if any(b in low for b in ("robotics", "automation and robotics", "electronics and telecommunication", "vlsi design", "mechanical engineering", "civil engineering", "chemical engineering")):
        return False, "text indicates non-CS/IT branch"
    if any(b in low for b in ("computer engineering", "computer science", "information technology", "artificial intelligence")):
        return True, "text indicates CS/IT branch"

    return True, "accepted by default"


def dump(page, name):
    Path("debug").mkdir(exist_ok=True)
    page.screenshot(path=f"debug/{name}.png", full_page=True)
    Path(f"debug/{name}.html").write_text(page.content(), encoding="utf-8")


def results_count(page) -> int | None:
    """Reads total results count from 'Showing X for All Documents'."""
    try:
        t = page.locator("text=/Showing\\s+[\\d,]+\\s+for/i").first.inner_text(timeout=2000)
        m = re.search(r"Showing\s+([\d,]+)", t)
        return int(m.group(1).replace(",", "")) if m else None
    except Exception:
        return None


def compute_paper_metadata(c: dict, info: dict, config_sem=None) -> tuple[str, str, str, str, str]:
    """
    Computes (sem, year, season, exam_type, code) to produce:
    sem-year-sum/win-R(regular)/S(supplymentary)-Code
    """
    code = (info.get("code") or c.get("code") or "NOCODE").upper().strip()
    # Sanitize characters not allowed in filenames on Windows/Linux (e.g. slashes in dual codes like BTETOE505B/BTEXOE505B)
    code = re.sub(r'[\\/*?:"<>|]+', "_", code).strip("._- ")
    if not code:
        code = "NOCODE"

    # 1. Semester:
    sem_str = "semNA"
    if code != "NOCODE":
        # In DBATU: BTCOC603 -> 6, BTAIC502 -> 5, 25UD1246PEC507E -> 5, 24AF2372MD303F -> 3
        m = re.findall(r"[A-Za-z]{2,}([1-8])\d{2}", code)
        if m:
            sem_str = f"sem{m[-1]}"
    if sem_str == "semNA" and info.get("sem"):
        sem_str = f"sem{info['sem']}"
    if sem_str == "semNA" and config_sem:
        sem_str = f"sem{config_sem}"

    # 2. Year:
    year = str(info.get("year") or c.get("year") or "yearNA")

    # 3. Season (sum / win):
    combined = f"{c.get('season') or ''} {c.get('month') or ''} {info.get('season') or ''} {c.get('text') or ''} {info.get('text') or ''}".lower()
    if "summer" in combined:
        season = "sum"
    elif "winter" in combined:
        season = "win"
    elif any(m in combined for m in ("may", "june", "july", "august")):
        season = "sum"
    elif any(m in combined for m in ("october", "november", "december", "january", "february", "march", "april", "september")):
        season = "win"
    else:
        season = "win"

    # 4. Exam Type: R for regular, S for supplementary
    if "supplementary" in combined or "supplymentary" in combined or "suppl" in combined or "atkt" in combined or c.get("is_suppl"):
        exam_type = "S"
    else:
        exam_type = "R"

    return sem_str, year, season, exam_type, code


def resolve_destination(folder: Path, base_name: str, file_hash: str) -> tuple[Path, bool]:
    """
    Resolves destination path adhering to:
        sem-year-sum/win-R/S-Code[-n].pdf
        (-n appears ONLY when more than 1 distinct paper shares the exact same metadata).

    Returns (dest_path, is_duplicate).
    - If a file with file_hash is already present, returns (path, True).
    - If base_name.pdf doesn't exist, returns (base_name.pdf, False).
    - If base_name.pdf exists with a DIFFERENT hash, returns base_name-2.pdf, base_name-3.pdf, etc.
    """
    primary = folder / f"{base_name}.pdf"
    if not primary.exists():
        return (primary, False)

    try:
        if hashlib.sha256(primary.read_bytes()).hexdigest() == file_hash:
            return (primary, True)
    except Exception:
        pass

    n = 2
    while True:
        candidate = folder / f"{base_name}-{n}.pdf"
        if not candidate.exists():
            return (candidate, False)
        try:
            if hashlib.sha256(candidate.read_bytes()).hexdigest() == file_hash:
                return (candidate, True)
        except Exception:
            pass
        n += 1


def handle_login(page, cfg, args):
    if "login" not in page.url:
        return

    creds = cfg.get("credentials") or {}
    email = getattr(args, "email", None) or os.getenv("KNIMBUS_EMAIL") or creds.get("email")
    password = getattr(args, "password", None) or os.getenv("KNIMBUS_PASSWORD") or creds.get("password")

    if email and password:
        print(f">>> Auto-logging in with account: {email}...")
        try:
            page.wait_for_selector("input[type='password'], input#password", timeout=10000)
            page.locator("input[type='email'], input#email, input[name='email'], input[placeholder*='Email']").first.fill(email)
            page.locator("input[type='password'], input#password, input[name='password'], input[placeholder*='Password']").first.fill(password)
            page.locator("button:has-text('Continue'), button[type='submit']").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_function("() => !location.href.includes('login')", timeout=10000)
            page.wait_for_timeout(2000)
            if "login" not in page.url:
                print(">>> Login successful!")
                return
        except Exception as e:
            print(f">>> Auto-login notice: {e}")

    # Manual login instructions if auto-login didn't complete
    print(">>> Log in to the DBATU library in the browser window.")
    print("    Waiting for login to complete...")
    try:
        page.wait_for_function("() => !location.href.includes('login')", timeout=0)
        time.sleep(2)
    except Exception as e:
        print(f">>> Login wait interrupted: {e}")


def apply_portal_filters(page, filters_cfg: dict):
    """
    Applies portal filters according to configuration:
    - repository: "B.Tech Question Paper" [default]
    - subject: None (avoids restrictive portal subject locks; Python code handles branch filtering)
    - publication_year: from config.yaml
    - year: from config.yaml
    - dept: from config.yaml
    - course: from config.yaml
    - author: ["supplementary", "summer", "winter"]

    Prefers the unified "View All" modal dialog to select multiple filters across tabs
    atomically and submits them via 'Apply'. Falls back to the sidebar accordion if the modal
    is unavailable.
    """
    repo = filters_cfg.get("repository") or "B.Tech Question Paper"
    authors = filters_cfg.get("author") or ["supplementary", "summer", "winter"]
    sub = filters_cfg.get("subject")

    before_count = results_count(page)
    print(f"  [filter] Applying portal filters (Repository: '{repo}', Subject: {sub}, Author: {authors})...")

    # 1. Primary Strategy: Unified "View All" modal dialog
    try:
        modal_opened = page.evaluate("""() => {
            const link = document.querySelector("#filterCustomAccordian a[data-bs-target^='#basicModalViewAll'], .filter-block a[data-bs-target^='#basicModalViewAll'], a[data-bs-target^='#basicModalViewAll']");
            if (link) {
                link.click();
                return true;
            }
            return false;
        }""")
        if modal_opened:
            page.wait_for_timeout(1000)

            # Helper to select a tab on the left and check corresponding options on the right
            def select_modal_tab_and_check(tab_name: str, patterns: list[str]):
                tab_found = page.evaluate("""(tabName) => {
                    const m = document.querySelector(".modal.show, .modal[style*='display: block']");
                    if (!m) return false;
                    const tabs = Array.from(m.querySelectorAll(".lSec li, .navSelection li"));
                    const tab = tabs.find(t => t.textContent.trim().toUpperCase().startsWith(tabName.toUpperCase()));
                    if (!tab) return false;
                    (tab.querySelector(".filter-title") || tab).click();
                    return true;
                }""", tab_name)
                if not tab_found:
                    return []
                page.wait_for_timeout(400)

                checked = page.evaluate("""(patterns) => {
                    const m = document.querySelector(".modal.show, .modal[style*='display: block']");
                    if (!m) return [];
                    const labels = Array.from(m.querySelectorAll(".rSec label, .rSec .filter-sub-values"));
                    const checkedList = [];
                    for (const p of patterns) {
                        const pat = new RegExp(p, "i");
                        for (const l of labels) {
                            if (pat.test(l.textContent.trim())) {
                                const cb = l.querySelector("input[type='checkbox']");
                                if (cb) {
                                    if (!cb.checked) {
                                        cb.click();
                                        checkedList.push(l.textContent.trim());
                                    }
                                }
                            }
                        }
                    }
                    return checkedList;
                }""", patterns)
                return checked

            # 1. REPOSITORY
            if repo and repo.lower() not in ("all", "none"):
                repo_pat = "^" + re.escape(repo)
                select_modal_tab_and_check("Repository", [repo_pat])

            # 2. AUTHOR
            if authors and isinstance(authors, list) and len(authors) > 0:
                author_pats = []
                for a in authors:
                    al = str(a).lower()
                    if "suppl" in al:
                        author_pats.append("^Supplementary\\b")
                    elif "summer" in al:
                        author_pats.append("^Summer(\\s+Semester)?\\b")
                    elif "winter" in al:
                        author_pats.append("^Winter(\\s+Semester)?\\b")
                    else:
                        author_pats.append("^" + re.escape(str(a)))
                select_modal_tab_and_check("Author", author_pats)

            # 3. SUBJECT
            if sub and str(sub).lower() not in ("none", "null"):
                sub_list = sub if isinstance(sub, list) else [sub]
                select_modal_tab_and_check("Subject", [re.escape(str(s)) for s in sub_list])

            # 4. PUBLICATION YEAR / YEAR
            pub_year = filters_cfg.get("publication_year")
            if pub_year and str(pub_year).lower() not in ("none", "null"):
                py_list = pub_year if isinstance(pub_year, list) else [pub_year]
                select_modal_tab_and_check("Publication Year", [f"^{y}\\b" for y in py_list])

            yr = filters_cfg.get("year")
            if yr and str(yr).lower() not in ("none", "null"):
                y_list = yr if isinstance(yr, list) else [yr]
                select_modal_tab_and_check("Year", [f"^{y}\\b" for y in y_list])

            # 5. DEPARTMENT / DEPT
            dept = filters_cfg.get("dept") or filters_cfg.get("department")
            if dept and str(dept).lower() not in ("none", "null"):
                d_list = dept if isinstance(dept, list) else [dept]
                select_modal_tab_and_check("Department", [re.escape(str(d)) for d in d_list])

            # 6. SEMESTER
            sem = filters_cfg.get("semester")
            if sem and str(sem).lower() not in ("none", "null"):
                s_list = sem if isinstance(sem, list) else [sem]
                select_modal_tab_and_check("Semester", [re.escape(str(s)) for s in s_list])

            # 7. COURSE
            crs = filters_cfg.get("course")
            if crs and str(crs).lower() not in ("none", "null"):
                c_list = crs if isinstance(crs, list) else [crs]
                select_modal_tab_and_check("Course", [re.escape(str(c)) for c in c_list])

            # Click Apply button inside the modal
            applied = page.evaluate("""() => {
                const m = document.querySelector(".modal.show, .modal[style*='display: block']");
                if (!m) return false;
                const applyBtn = Array.from(m.querySelectorAll("button, .btn, a")).find(b => b.textContent.trim().toLowerCase() === "apply");
                if (applyBtn) {
                    applyBtn.click();
                    return true;
                }
                return false;
            }""")

            if applied:
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2500)

                # Fix Knimbus's Drilldown-to bug:
                # Knimbus's modal converts the search term into 'Drilldown to=...' instead of 'search_within=...'
                cur_url = page.url
                if re.search(r'Drilldown(?:\+|%20|\s)+to=', cur_url, re.I):
                    fixed_url = re.sub(r'Drilldown(?:\+|%20|\s)+to=', 'search_within=', cur_url, flags=re.I)
                    page.goto(fixed_url)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)

                after_count = results_count(page)
                if before_count is not None and after_count is not None:
                    print(f"  [filter] View All modal applied: {after_count} papers available (filtered from {before_count})")
                else:
                    print("  [filter] Filters applied via View All modal.")
                return
    except Exception as e:
        print(f"  [filter] View All modal notice: {e}. Falling back to sidebar.")

    # 2. Fallback Strategy: Sidebar Accordion Checkboxes
    try:
        toggled = page.evaluate("""(filters) => {
            let changed = false;

            // 1. Expand any collapsed filter sections in the sidebar
            const sidebar = document.querySelector("#filterCustomAccordian, .filter-block");
            if (sidebar) {
                const collapsedButtons = Array.from(sidebar.querySelectorAll(".accordion-button.collapsed, button.collapsed"));
                for (const btn of collapsedButtons) {
                    try { btn.click(); } catch(e) {}
                }
            }

            // Helper to find and check checkbox or element
            const checkOption = (labelPattern, sectionHint = null) => {
                const scope = document.querySelector("#filterCustomAccordian, .filter-block") || document;
                let elements = Array.from(scope.querySelectorAll("label.filter-item-box, label, span, li, div"));
                if (sectionHint) {
                    const sec = elements.filter(el => {
                        const t = el.closest(".accordion-item, .panel, .card, [class*='filter'], div")?.textContent || "";
                        return new RegExp(sectionHint, "i").test(t);
                    });
                    if (sec.length > 0) elements = sec;
                }
                for (const el of elements) {
                    if (labelPattern.test(el.textContent.trim())) {
                        const cb = el.querySelector("input[type='checkbox']") || (el.tagName === 'INPUT' ? el : null) || el.closest("label")?.querySelector("input[type='checkbox']");
                        if (cb) {
                            if (!cb.checked) {
                                cb.click();
                                changed = true;
                            }
                            return true;
                        }
                    }
                }
                return false;
            };

            // 1. REPOSITORY (default: "B.Tech Question Paper")
            const repo = filters.repository || "B.Tech Question Paper";
            if (repo && repo.toLowerCase() !== "all" && repo.toLowerCase() !== "none") {
                const applied = Array.from(document.querySelectorAll(".applied-filters, [class*='applied'], [class*='filter-tag']"));
                const alreadyActive = applied.some(a => a.textContent.toLowerCase().includes(repo.toLowerCase()));
                if (!alreadyActive) {
                    checkOption(new RegExp(repo.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), "i"), "REPOSITORY");
                }
            }

            // 2. SUBJECT (None by default - do NOT check any SUBJECT checkbox unless explicitly specified and not None)
            const sub = filters.subject;
            if (sub && String(sub).toLowerCase() !== "none" && String(sub).toLowerCase() !== "null") {
                const subList = Array.isArray(sub) ? sub : [sub];
                for (const s of subList) {
                    checkOption(new RegExp(s, "i"), "SUBJECT");
                }
            }

            // 3. PUBLICATION YEAR (from config.yaml)
            const pubYear = filters.publication_year;
            if (pubYear && String(pubYear).toLowerCase() !== "none" && String(pubYear).toLowerCase() !== "null") {
                const pyList = Array.isArray(pubYear) ? pubYear : [pubYear];
                for (const py of pyList) {
                    checkOption(new RegExp(`^${py}\\\\b`), "PUBLICATION YEAR");
                }
            }

            // 4. YEAR (from config.yaml)
            const yr = filters.year;
            if (yr && String(yr).toLowerCase() !== "none" && String(yr).toLowerCase() !== "null") {
                const yList = Array.isArray(yr) ? yr : [yr];
                for (const y of yList) {
                    checkOption(new RegExp(`^${y}\\\\b`), "YEAR");
                }
            }

            // 5. DEPT (from config.yaml)
            const dept = filters.dept;
            if (dept && String(dept).toLowerCase() !== "none" && String(dept).toLowerCase() !== "null") {
                const dList = Array.isArray(dept) ? dept : [dept];
                for (const d of dList) {
                    checkOption(new RegExp(d, "i"), "DEPT");
                }
            }

            // 6. COURSE (from config.yaml)
            const crs = filters.course;
            if (crs && String(crs).toLowerCase() !== "none" && String(crs).toLowerCase() !== "null") {
                const cList = Array.isArray(crs) ? crs : [crs];
                for (const c of cList) {
                    checkOption(new RegExp(c, "i"), "COURSE");
                }
            }

            // 7. AUTHOR (supplementary, summer, winter)
            const authors = filters.author || ["supplementary", "summer", "winter"];
            if (authors && Array.isArray(authors) && authors.length > 0) {
                for (const a of authors) {
                    const al = String(a).toLowerCase();
                    if (al.includes("suppl")) {
                        checkOption(/^Supplementary\\\\b/i, "AUTHOR");
                    } else if (al.includes("summer")) {
                        checkOption(/^Summer(\\\\s+Semester)?\\\\b/i, "AUTHOR");
                    } else if (al.includes("winter")) {
                        checkOption(/^Winter(\\\\s+Semester)?\\\\b/i, "AUTHOR");
                    }
                }
            }

            return changed;
        }""", filters_cfg)

        if toggled:
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            after_count = results_count(page)
            if before_count is not None and after_count is not None:
                print(f"  [filter] Filter active: {after_count} papers available (filtered from {before_count})")
            else:
                print("  [filter] Filter toggled in portal UI.")
    except Exception as e:
        print(f"  [filter] Note: UI filter toggle ({e}). Code-level inspection will enforce filters.")


def go_to_page(page, n: int) -> bool:
    """
    Navigate to page n.
    1. Tries JS click on the direct page number link (immune to sticky footers).
    2. If page n is hidden behind an ellipsis (...), tries JS click on Next ('>').
    3. Direct URL navigation fallback (&curPage=n).
    Returns False if there are no more pages.
    """
    # 1. Try direct page number link
    loc = page.locator(f"xpath=//*[self::a or self::button or self::li][normalize-space(text())='{n}']")
    if loc.count() > 0:
        try:
            target = loc.last
            target.evaluate("el => el.click()")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            return True
        except Exception:
            pass

    # 2. Try Next button ('>')
    next_loc = page.locator("xpath=//a[normalize-space(text())='>'] | //button[normalize-space(text())='>'] | //li[not(contains(@class, 'disabled'))]//*[normalize-space(text())='>'] | //a[@aria-label='Next']")
    if next_loc.count() > 0:
        try:
            target = next_loc.last
            target.evaluate("el => el.click()")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            return True
        except Exception:
            pass

    # 3. Direct URL navigation fallback
    try:
        curr_url = page.url
        u = urlparse(curr_url)
        q = dict(parse_qsl(u.query))
        if q.get("curPage") != str(n):
            q["curPage"] = str(n)
            new_url = urlunparse(u._replace(query=urlencode(q)))
            page.goto(new_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            return True
    except Exception:
        pass

    return False


def fetch_pdf(ctx, page, btn) -> tuple[bytes | None, str, str]:
    """
    Multi-vector PDF retrieval engine:
    1. Direct href on the button (fast path).
    2. Network response listener (application/pdf or .pdf url).
    3. Browser file download event.
    4. Popup tab URL (e.g. AWS S3 redirect).
    5. Embedded viewers (<embed>, <iframe>, <object>, <a href*='.pdf'>).
    Returns (data_bytes, url_or_source, note).
    """
    # 1. Direct href fast path
    href = btn.get_attribute("href")
    if href and (".pdf" in href.lower() or "s3.amazonaws.com" in href.lower()):
        try:
            resp = ctx.request.get(href)
            b = resp.body()
            if b.startswith(b"%PDF"):
                return b, href, "direct-href"
        except Exception:
            pass

    # 2. Setup listeners for network responses & file downloads
    captured, downloads = [], []

    def on_resp(r):
        try:
            ct = (r.headers.get("content-type") or "").lower()
            if "pdf" in ct or r.url.lower().split("?")[0].endswith(".pdf"):
                captured.append(r)
        except Exception:
            pass

    def on_page(pg):
        pg.on("download", lambda d: downloads.append(d))

    ctx.on("response", on_resp)
    ctx.on("page", on_page)
    new_page = None
    try:
        try:
            with ctx.expect_page(timeout=15000) as pi:
                btn.click()
            new_page = pi.value
        except Exception as e:
            return None, "", f"no popup opened ({str(e)[:60]})"

        # Wait up to 6s for network response or download event
        for _ in range(12):
            if captured or downloads:
                break
            page.wait_for_timeout(500)

        for r in captured:
            try:
                b = r.body()
                if b.startswith(b"%PDF"):
                    return b, r.url, "network-response"
            except Exception:
                pass

        for d in downloads:
            try:
                b = open(d.path(), "rb").read()
                if b.startswith(b"%PDF"):
                    return b, d.url, "download-event"
            except Exception:
                pass

        # Check popup URL navigation
        try:
            new_page.wait_for_url(lambda u: u and u != "about:blank", timeout=6000)
        except Exception:
            pass
        url = new_page.url
        candidates = [url] if url and url != "about:blank" else []

        # Check embedded iframe/embed/object
        try:
            for sel in ("embed[src]", "iframe[src]", "object[data]", "a[href*='.pdf']"):
                for el in new_page.locator(sel).all()[:3]:
                    u = el.get_attribute("src") or el.get_attribute("data") or el.get_attribute("href")
                    if u and u.startswith("http"):
                        candidates.append(u)
        except Exception:
            pass

        for u in candidates:
            try:
                resp = ctx.request.get(u)
                b = resp.body()
                if b.startswith(b"%PDF"):
                    return b, u, "page-candidate"
            except Exception:
                pass

        return None, url, "no valid PDF bytes"
    finally:
        ctx.remove_listener("response", on_resp)
        ctx.remove_listener("page", on_page)
        if new_page:
            try:
                new_page.close()
            except Exception:
                pass


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Bulk-download DBATU previous year question papers from Knimbus.")
    ap.add_argument("-c", "--config", default="config.yaml", help="Path to base configuration YAML file (default: config.yaml)")
    ap.add_argument("-s", "--secondary", "--subjects-config", "--branch-config", nargs="+", action="extend",
                    help="Path(s) to secondary branch/subject configuration YAML file(s) (e.g. -s configs/aiml_sem5.yaml configs/cse_sem5.yaml)")
    ap.add_argument("--only", nargs="+", action="extend",
                    help="Run only for specific subject(s). Can pass multiple names, acronyms, or comma-separated (e.g. --only ML DBMS or --only ML,DBMS)")
    ap.add_argument("--course", help="Target course/degree type override (e.g. 'B.Tech', 'Diploma', 'M.Tech', 'Pharmacy', 'all')")
    ap.add_argument("--email", help="Knimbus login email (for automated headless login)")
    ap.add_argument("--password", help="Knimbus login password")
    ap.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    ap.add_argument("--debug", action="store_true", help="Save debug screenshots and HTML dumps")
    args = ap.parse_args()

    base_path = Path(args.config)
    if not base_path.exists():
        print(f"Error: Base configuration file '{base_path}' not found.")
        sys.exit(1)

    base_cfg = yaml.safe_load(open(base_path, encoding="utf-8")) or {}

    # Collect secondary config files from -s / --secondary
    secondary_files = []
    if args.secondary:
        for item in args.secondary:
            for part in item.split(","):
                p = part.strip()
                if p:
                    secondary_files.append(p)

    # Check if secondary config is provided; if not, check base config subjects
    if not secondary_files:
        base_subjects = base_cfg.get("subjects") or []
        if not base_subjects:
            print(f"\n[!] Notice: Base configuration '{base_path}' contains no subjects.")

            # Look for available configs in ./configs/ and ./
            discovered = []
            for d in (Path("configs"), Path(".")):
                if d.exists() and d.is_dir():
                    for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
                        if f.resolve() != base_path.resolve():
                            discovered.append(f)

            if discovered:
                print("    Available subject configuration files:")
                for idx, cf in enumerate(discovered, 1):
                    print(f"      {idx}. {cf.as_posix()}")
                print()
                prompt_msg = "    Enter config file path, selection number, or press Enter to exit: "
            else:
                prompt_msg = "    Enter path to a subject configuration file (or press Enter to exit): "

            try:
                choice = input(prompt_msg).strip()
            except (EOFError, KeyboardInterrupt):
                choice = ""

            if not choice:
                print("No subject configuration provided. Exiting.")
                sys.exit(0)

            if choice.isdigit() and discovered:
                idx = int(choice) - 1
                if 0 <= idx < len(discovered):
                    secondary_files = [str(discovered[idx])]
                else:
                    print(f"Invalid selection number '{choice}'. Exiting.")
                    sys.exit(1)
            else:
                secondary_files = [choice]

    # Build list of execution runs: [(run_label, effective_cfg, cfg_source), ...]
    runs = []
    if secondary_files:
        for sec_str in secondary_files:
            sec_path = Path(sec_str)
            if not sec_path.exists():
                print(f"[!] Warning: Secondary config file '{sec_str}' not found.")
                continue
            sec_cfg = yaml.safe_load(open(sec_path, encoding="utf-8")) or {}
            merged = merge_configs(base_cfg, sec_cfg)
            runs.append((sec_path.stem, merged, sec_str))
    else:
        # Running directly from base config (Case 1 or Case 2)
        runs.append(("base", base_cfg, str(base_path)))

    if not runs:
        print("No valid configurations found to execute. Exiting.")
        sys.exit(1)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            ".browser-profile",
            channel="chrome",
            headless=args.headless,
            viewport={"width": 1366, "height": 800}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        first_base_url = runs[0][1].get("base_url") or "https://dbatulibrary.knimbus.com/portal/v2/default/results/section?sectionId=1ad6bd68-4cc6-4d8b-8550-2203b35075ef&sectionName=QUESTION+PAPERS"
        page.goto(first_base_url)
        page.wait_for_load_state("networkidle")
        handle_login(page, runs[0][1], args)

        total_runs = len(runs)
        for run_idx, (run_label, cfg, cfg_source) in enumerate(runs, 1):
            if total_runs > 1:
                print(f"\n{'='*65}\n RUN {run_idx}/{total_runs}: [{run_label}] (Config: {cfg_source})\n{'='*65}")

            out = Path(cfg.get("output_dir", "./PYPs/")).expanduser()
            try:
                out.mkdir(parents=True, exist_ok=True)
            except (OSError, FileNotFoundError) as e:
                fallback_out = Path("./PYPs/").resolve()
                print(f"[!] Warning: Configured output directory '{out}' is unreachable ({e}).")
                print(f"    Falling back to local directory: {fallback_out}")
                out = fallback_out
                out.mkdir(parents=True, exist_ok=True)
            since = cfg.get("since_year", date.today().year - 4)
            manifest_path = out / "manifest.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"hashes": {}, "keys": {}}

            # Merged course & repository resolution
            cfg_filters = cfg.get("filters", {}) or {}
            raw_course = args.course if args.course is not None else (cfg.get("course") or cfg_filters.get("course") or cfg_filters.get("repository") or "B.Tech Question Paper")
            repo_label, prog_target = resolve_course(raw_course)

            filters_cfg = {
                "repository": repo_label or "B.Tech Question Paper",
                "subject": cfg_filters.get("subject", None),
                "publication_year": cfg_filters.get("publication_year", None),
                "year": cfg_filters.get("year", None),
                "dept": cfg_filters.get("dept", None),
                "course": repo_label or "B.Tech Question Paper",
                "author": cfg_filters.get("author", ["supplementary", "summer", "winter"]),
            }

            # Resolve target subjects (applying --only if passed)
            target_subjects = []
            if args.only:
                raw_queries = []
                for item in args.only:
                    for part in item.split(","):
                        p = part.strip()
                        if p:
                            raw_queries.append(p)

                seen_sub_names = set()
                for q in raw_queries:
                    matched = [s for s in cfg.get("subjects", []) if match_subject(s, q) and s["name"] not in seen_sub_names]
                    if matched:
                        for m in matched:
                            target_subjects.append(m)
                            seen_sub_names.add(m["name"])
                    elif total_runs == 1:
                        print(f"\n[!] Notice: No exact subject matching '--only \"{q}\"' found in {cfg_source}.")
                        print(f"    [+] Creating an ad-hoc subject search for: '{q}'")
                        clean_words = [w.lower() for w in q.split() if len(w) > 2 and w.lower() not in ("with", "from", "and", "the", "for", "in")]
                        target_subjects.append({
                            "name": q.title(),
                            "search": q.lower(),
                            "keywords": clean_words or [q.lower()],
                            "exclude": [],
                            "sem": 5,
                            "codes": []
                        })
                        seen_sub_names.add(q.title())
            else:
                target_subjects = cfg.get("subjects", [])

            print(f"==================================================")
            print(f" DBATU PYQ Fetcher - [{run_label}]")
            print(f" Target Course : '{repo_label or 'ALL'}' (key: {prog_target})")
            print(f" Min Year      : {since}")
            print(f" Output Folder : {out}")
            print(f" Branches      : {cfg.get('branches', [])}")
            print(f" Naming Format : sem-year-sum/win-R/S-Code[-n].pdf")
            if args.only:
                matched_names = [s['name'] for s in target_subjects]
                print(f" Filter (--only): {args.only} -> Matched {len(target_subjects)}: {matched_names}")
            else:
                print(f" Subjects Total: {len(target_subjects)}")
            print(f"==================================================")

            if not target_subjects:
                print(f"  [i] No matching subjects to fetch for [{run_label}].")
                continue

            for sub in target_subjects:

                sem = sub.get("sem")
                if sem is None or str(sem).lower() in ("any", "all", "none"):
                    allowed = None
                elif isinstance(sem, list):
                    allowed = set(sem)
                elif isinstance(sem, int):
                    allowed = {sem - 1, sem, sem + 1}
                else:
                    allowed = None
                kws = [k.lower() for k in sub.get("keywords", [])]
                exc = [e.lower() for e in sub.get("exclude", [])]
                codes = {c.upper() for c in sub.get("codes", [])}

                # Atomic Inheritance resolution for subject:
                # 1. Output folder: dedicated address in subject -> secondary -> base -> default
                sub_addr = sub.get("output_dir") or sub.get("address") or sub.get("folder") or sub.get("path") or sub.get("repo")
                if sub_addr:
                    folder = Path(sub_addr).expanduser()
                else:
                    folder = out / slug(sub["name"])
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                except (OSError, FileNotFoundError) as e:
                    fallback_folder = out / slug(sub["name"])
                    print(f"    [!] Warning: Destination path '{folder}' unreachable ({e}). Falling back to '{fallback_folder}'")
                    folder = fallback_folder
                    folder.mkdir(parents=True, exist_ok=True)

                # 2. Branches: subject -> secondary -> base
                branches = sub.get("branches") or cfg.get("branches", [])

                # 3. Exam since year: subject -> secondary -> base
                sub_since = sub.get("since_year") if sub.get("since_year") is not None else cfg.get("since_year", date.today().year - 4)

                # 4. Course / degree: subject -> secondary -> base (or CLI args.course)
                sub_course_raw = sub.get("course") or (args.course if args.course is not None else (cfg.get("course") or cfg_filters.get("course") or cfg_filters.get("repository") or "B.Tech Question Paper"))
                sub_repo_label, sub_prog_target = resolve_course(sub_course_raw)

                # 5. Max pages: subject -> secondary -> base
                sub_max_pages = sub.get("max_pages") or cfg.get("max_pages", 15)

                # 6. Portal filters: subject -> secondary -> base
                sub_filters_cfg = copy.deepcopy(filters_cfg)
                if "filters" in sub and isinstance(sub["filters"], dict):
                    sub_filters_cfg.update(sub["filters"])
                for fk in ("author", "subject", "publication_year", "year", "dept"):
                    if fk in sub:
                        sub_filters_cfg[fk] = sub[fk]
                if sub_repo_label:
                    sub_filters_cfg["repository"] = sub_repo_label
                    sub_filters_cfg["course"] = sub_repo_label

                # 7. Portal URL: subject -> secondary -> base
                sub_base_url = sub.get("base_url") or cfg.get("base_url", first_base_url)

                sub_manifest_path = folder / "manifest.json"
                if sub_manifest_path.exists():
                    try:
                        sub_manifest = json.loads(sub_manifest_path.read_text())
                    except Exception:
                        sub_manifest = {"hashes": {}, "keys": {}}
                else:
                    sub_manifest = {"hashes": {}, "keys": {}}

                print(f"\n=== Subject: {sub['name']} ===")
                if sub_addr:
                    print(f"    Dedicated Address: {folder}")
                else:
                    print(f"    Target Folder    : {folder}")
                if allowed:
                    print(f"    Allowed Semesters: {sorted(allowed)}")
                if branches:
                    print(f"    Target Branches  : {branches}")
                if sub_prog_target != prog_target:
                    print(f"    Course Override  : {sub_repo_label} ({sub_prog_target})")
                if sub_since != since:
                    print(f"    Since Year Over. : {sub_since}")
                print(f"    Search Query     : '{sub['search']}'")

                search_url = with_search(sub_base_url, sub["search"], sub_filters_cfg.get("subject"))
                page.goto(search_url)
                page.wait_for_load_state("networkidle")
                if "login" in page.url:
                    handle_login(page, cfg, args)
                    page.goto(search_url)
                    page.wait_for_load_state("networkidle")

                # Apply UI portal filters according to detailed config
                apply_portal_filters(page, sub_filters_cfg)

                seen_cards, kept = set(), 0

                for pg in range(1, sub_max_pages + 1):
                    if pg > 1:
                        print(f"\n--- Navigating to page {pg} ---")
                        if not go_to_page(page, pg):
                            print(f"  Reached last page at page {pg - 1}.")
                            break

                    try:
                        page.wait_for_selector("button:has-text('Read')", timeout=12000)
                    except Exception:
                        if args.debug:
                            dump(page, f"{slug(sub['name'])}_p{pg}")
                        print(f"  page {pg}: no results found, stopping.")
                        break

                    read_buttons = page.locator("button:has-text('Read')")
                    n = read_buttons.count()
                    print(f"  page {pg}: found {n} paper cards")

                    for i in range(n):
                        btn = page.locator("button:has-text('Read')").nth(i)
                        card = btn.locator("xpath=ancestor::div[count(.//button[normalize-space()='Read'])=1][last()]")
                        ctext = card.inner_text() if card.count() > 0 else btn.inner_text()

                        c = parse_card(ctext)
                        card_fingerprint = f"{c['title']}|{c['code']}|{c['year']}|{c['season']}"
                        if card_fingerprint in seen_cards:
                            continue
                        seen_cards.add(card_fingerprint)

                        print(f"    [{i+1}/{n}] '{c['full_title']}' {c['season'] or ''} {c['year'] or ''} (prog: {c['prog']})")

                        # 1. Skip Mid-Semester / Class Test papers
                        if c["is_mid_sem"]:
                            print(f"      - Skip: Mid-Semester / Class Test paper")
                            continue

                        # 2. Subject keyword and exclusion check on card title
                        tl = c["title"].lower()
                        if not all(k in tl for k in kws):
                            print(f"      - Skip: title does not match keywords {kws}")
                            continue
                        if any(e in tl for e in exc):
                            print(f"      - Skip: title contains excluded keyword")
                            continue

                        # 3. Year check from card
                        if c["year"] and c["year"] < sub_since:
                            print(f"      - Skip: year {c['year']} < {sub_since}")
                            continue

                        # 4. Course check from card (e.g. Reject Diploma [23DCE...], MCA [MCAC...] when B.Tech is required)
                        if sub_prog_target != "all":
                            if c["prog"] != "unknown" and c["prog"] != sub_prog_target:
                                print(f"      - Skip: non-{sub_prog_target} card (detected: {c['prog']})")
                                continue

                        # 5. Optional course code whitelist check from card
                        if codes and c["code"] and c["code"] not in codes:
                            print(f"      - Skip: code {c['code']} not in whitelist")
                            continue

                        # 6. Pre-download semester check from course code (saves downloading out-of-range papers)
                        if allowed and c["code"]:
                            code_sem_digits = re.findall(r"[A-Za-z]{2,}([1-8])\d{2}", c["code"])
                            if code_sem_digits:
                                card_sem = int(code_sem_digits[-1])
                                if card_sem not in allowed:
                                    print(f"      - Skip: code '{c['code']}' indicates sem {card_sem}, wanted {sorted(allowed)}")
                                    continue

                        # 7. Pre-download branch check from course code and card text
                        if branches:
                            allowed_branch, branch_reason = is_allowed_branch(c["code"], ctext, branches)
                            if not allowed_branch:
                                print(f"      - Skip: {branch_reason} (code: '{c['code']}')")
                                continue

                        # Fetch PDF using multi-vector delivery engine
                        data, url, note = fetch_pdf(ctx, page, btn)
                        if not data:
                            print(f"    ! Could not fetch PDF for '{c['title']}': {note} ({url[:70]})")
                            continue

                        h = hashlib.sha256(data).hexdigest()
                        if h in sub_manifest.get("hashes", {}) and sub_manifest["hashes"][h] != "skipped":
                            saved_path = Path(sub_manifest["hashes"][h])
                            if saved_path.exists():
                                print(f"      = Already downloaded: {saved_path.name}")
                                continue
                        if h in manifest.get("hashes", {}) and manifest["hashes"][h] != "skipped":
                            saved_path = Path(manifest["hashes"][h])
                            if saved_path.exists():
                                print(f"      = Already downloaded: {saved_path.name}")
                                continue

                        # Inspect PDF body
                        text = pdf_first_pages_text(data)
                        info = parse_paper(text)

                        # 1. Mid-Semester verification from PDF
                        if info["is_mid_sem"]:
                            print(f"      - Skip PDF: Mid-Semester examination detected")
                            sub_manifest["hashes"][h] = "skipped"
                            manifest["hashes"][h] = "skipped"
                            continue

                        # 2. Course verification
                        verdict = "keep"
                        code = (info.get("code") or c.get("code") or "NOCODE").upper().strip()
                        code = re.sub(r'[\\/*?:"<>|]+', "_", code).strip("._- ") or "NOCODE"

                        if sub_prog_target != "all":
                            # If course code starts with BT, BTECH, or NEP patterns, it is guaranteed B.Tech
                            if re.search(r"^BT|BTECH|^\d{2}(UD|AF)|UD.*PEC|^PEC", code):
                                pass
                            elif info["programme"] not in (sub_prog_target, "unknown"):
                                print(f"      - Skip PDF: programme '{info['programme']}' does not match target '{sub_prog_target}'")
                                verdict = "skip"
                            elif c["prog"] not in (sub_prog_target, "unknown"):
                                print(f"      - Skip PDF: card prog '{c['prog']}' does not match target '{sub_prog_target}'")
                                verdict = "skip"

                        # 3. Year verification
                        paper_year = info.get("year") or c.get("year")
                        if verdict == "keep" and paper_year and int(paper_year) < sub_since:
                            print(f"      - Skip PDF: year {paper_year} < {sub_since}")
                            verdict = "skip"

                        # 4. Course code whitelist verification
                        if verdict == "keep" and codes and code not in codes:
                            print(f"      - Skip PDF: code '{code}' not in whitelist {codes}")
                            verdict = "skip"

                        # 5. Semester verification
                        sem_str, year_str, season_str, exam_type_str, code_str = compute_paper_metadata(c, info, sub.get("sem"))
                        sem_num = int(sem_str.replace("sem", "")) if sem_str.startswith("sem") and sem_str[3:].isdigit() else None
                        if verdict == "keep" and allowed and sem_num is not None and sem_num not in allowed:
                            print(f"      - Skip PDF: semester {sem_num} not in allowed {allowed}")
                            verdict = "skip"

                        # 6. Branch verification from PDF text and verified code
                        if verdict == "keep" and branches:
                            allowed_branch, branch_reason = is_allowed_branch(code, text, branches)
                            if not allowed_branch:
                                print(f"      - Skip PDF: {branch_reason} (code: '{code}')")
                                verdict = "skip"

                        if verdict == "skip":
                            sub_manifest["hashes"][h] = "skipped"
                            manifest["hashes"][h] = "skipped"
                            continue

                        # Compute requested naming format: sem-year-sum/win-R/S-Code[-n].pdf
                        base_name = f"{sem_str}-{year_str}-{season_str}-{exam_type_str}-{code_str}"
                        base_name = re.sub(r'[\\/*?:"<>|]+', "_", base_name).strip("._- ")
                        
                        # Save into semester-wise subfolder (e.g. Dedicated/sem5/ or Machine_Learning/sem5/)
                        target_folder = folder / sem_str
                        target_folder.mkdir(parents=True, exist_ok=True)
                        dest, is_dup = resolve_destination(target_folder, base_name, h)

                        if is_dup:
                            sub_manifest["hashes"][h] = str(dest)
                            manifest["hashes"][h] = str(dest)
                            print(f"      = Duplicate paper content already saved: {dest.name}")
                            continue

                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
                        sub_manifest["hashes"][h] = str(dest)
                        manifest["hashes"][h] = str(dest)
                        kept += 1
                        print(f"    + [SAVED ] {sem_str}/{dest.name}")
                        sub_manifest_path.write_text(json.dumps(sub_manifest, indent=2))
                        manifest_path.write_text(json.dumps(manifest, indent=2))

                sub_manifest_path.write_text(json.dumps(sub_manifest, indent=2))
                print(f"  -> Total saved for '{sub['name']}': {kept} paper(s)")

            manifest_path.write_text(json.dumps(manifest, indent=2))

        ctx.close()

    print("\nCompleted bulk fetch.")


if __name__ == "__main__":
    main()
