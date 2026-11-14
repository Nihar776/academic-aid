#!/usr/bin/env python3
"""
=============================================================================
Unified NPTEL & Course Material Manager
=============================================================================
This script merges and unifies:
  1. download_nptel.py             (Weekly assignments & transcript scraping)
  2. download_nptel_missing_lecs.py (Video & missing lecture downloads)
  3. download_toc_ppts.py           (TOC lecture PPTs & unit-wise organization)
  4. nptel_material_categorization.py (Consolidating assignments & transcripts)

Universal Course Support:
  - Supports ANY NPTEL course by ID or URL (e.g. --course 106106145)
  - Automatically fetches course metadata, syllabus structure, and lesson titles.
  - Automatically handles both Swayam WebVTT subtitles (.vtt & .txt) and Google Drive PDFs (.pdf).
  - Automatically downloads course assignments if available on NPTEL.
  - Defaults to course 110104169 (Algorithmic Trading & Portfolio Management).
  - Zero external dependencies: Uses Python 3 standard library only.
=============================================================================
"""

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Default Constants (Course: 110104169)
# ---------------------------------------------------------------------------

DEFAULT_COURSE_ID = "110104169"
DEFAULT_BASE_DIR = Path(r"C:\Users\alien\nptel_material") if Path(r"C:\Users\alien\nptel_material").exists() else Path("./nptel_material")

# Dedicated fallback mappings for 110104169 (28 lectures, 8 weeks)
WEEK_MAP_DEFAULT = {
    1: (1, 3),
    2: (4, 7),
    3: (8, 11),
    4: (12, 15),
    5: (16, 19),
    6: (20, 23),
    7: (24, 26),
    8: (27, 28),
}

VTT_BASE_URL_DEFAULT = "https://storage.googleapis.com/swayam-node1-production.appspot.com/assets/vtt/noc24_mg83/"
VTT_FILES_DEFAULT = {
    1: "Lec-01.vtt", 2: "Lec-02.vtt", 3: "Lec-03.vtt", 4: "Lec-04.vtt",
    5: "Lec-05.vtt", 6: "Lec-06.vtt", 7: "Lec-07.vtt", 8: "Lec-%2008.vtt",
    9: "Lec-09.vtt", 10: "Lec-10.vtt", 11: "Lec--11.vtt", 12: "Lec-12.vtt",
    13: "Lec-13.vtt", 14: "Lec-14.vtt", 15: "Lec-15.vtt", 16: "Lec-16.vtt",
    17: "Lec-17.vtt", 18: "Lec-18.vtt", 19: "Lec-19.vtt", 20: "Lec-20.vtt",
    21: "Lec-21.vtt", 22: "Lec-22.vtt", 23: "Lec-23.vtt", 24: "Lec-24.vtt",
    25: "Lec-25.vtt", 26: "Lec-26.vtt", 27: "Lec-27.vtt", 28: "Lec-28.vtt",
}

MISSING_VIDEOS_DEFAULT = {
    20: "mod05lec20",
    24: "mod07lec24",
    25: "mod07lec25",
    26: "mod07lec26",
}

# Theory of Computation (TOC) PPTs by Sridhar Iyer
TOC_BASE = "http://iamsridhariyer.com/wp-content/uploads/"
TOC_PPTS = {
    1:  ("2024/08/Lecture-1-Intro.pptx", "Intro"),
    2:  ("2024/08/Lecture-2-Basics-of-FSM.pptx", "Basics of FSM"),
    3:  ("2024/08/Lecture-3-Basic-Problems-on-FSM.pptx", "Basic Problems on FSM"),
    4:  ("2024/08/Lecture-4-Basics-Problems-on-FSM.pptx", "Basic Problems on FSM 2"),
    5:  ("2024/08/Lecture-5-Regular-languages-and-expressions.pptx", "Regular languages and expressions 1"),
    6:  ("2024/08/Lecture-6-Regular-languages-and-expressions.pptx", "Regular languages and expressions 2"),
    7:  ("2024/08/Lecture-7-Ardens-Theorem-FA-to-RE.pptx", "Ardens Theorem FA to RE"),
    8:  ("2024/08/Lecture-8-DFA-Minimization.pptx", "DFA Minimization"),
    9:  ("2024/08/Lecture-9-DFA-Minimization-and-NFA-to-DFA.pptx", "DFA Minimization and NFA to DFA"),
    10: ("2024/08/Lecture-10-NFA-to-DFA-and-Myhill-Nerode.pptx", "NFA to DFA (skip Myhill-Nerode)"),
    11: ("2024/08/Lecture-11-Moore-and-Mealy-Machines.pptx", "Moore and Mealy Machines"),
    12: ("2024/08/Lecture-12-Moore-Machines-and-Conversions.pptx", "Moore Machines and Conversions"),
    13: ("2024/08/Lecture-13-Moore-Machines-and-Conversions-and-Pumping-Lemma.pptx", "Moore-Mealy Conversions and Pumping Lemma"),
    14: ("2024/11/Lecture-14-Module-3-Regular-Grammars.pptx", "Regular Grammars 1"),
    15: ("2024/11/Lecture-14-Pumping-Lemma.pptx", "Pumping Lemma"),
    16: ("2024/11/Lecture-15-Module-3-Regular-Grammars.pptx", "Regular Grammars 2"),
    17: ("2024/11/Lecture-16-Module-3-Regular-Grammars.pptx", "Regular Grammars 3"),
    18: ("2024/11/Lecture-17-Module-3-Simplification-of-Grammars.pptx", "Simplification of Grammars"),
    19: ("2024/11/Lecture-18-Module-3-Normal-Forms.pptx", "Normal Forms CNF GNF"),
    20: ("2024/11/Lecture-19-Module-4-Push-Down-Automata.pptx", "PDA 1"),
    21: ("2024/11/Lecture-20-Module-4-Push-Down-Automata.pptx", "PDA 2"),
    22: ("2024/11/Lecture-24-Module-4-CFG-to-PDA.pptx", "CFG to PDA (a)"),
    23: ("2024/11/Lecture-25-Module-5-Turing-Machines.pptx", "Turing Machines (intro)"),
    24: ("2024/11/Lecture-25-Module-4-CFG-to-PDA.pptx", "CFG to PDA (b)"),
    25: ("2024/11/Lecture-26-Module-5-Turing-Machines-1.pptx", "Turing Machines (L26-30)"),
}

TOC_UNITS = {
    "Unit1_Finite_Automata": [1, 2, 3, 4, 8, 9, 10, 11, 12, 13],
    "Unit2_RegEx_RegGrammar_PumpingLemma": [5, 6, 7, 13, 14, 15, 16, 17],
    "Unit3_CFG": [18, 19],
    "Unit3_CFG_check": [14, 16, 17],
    "Unit4_PDA_and_TM": [20, 21, 22, 23, 24, 25],
    "Unit5_Undecidability_check": [25],
}


# ---------------------------------------------------------------------------
# Network & Utility Helpers
# ---------------------------------------------------------------------------

def parse_course_id(course_input: str) -> str:
    """Extracts course ID from full URL or returns raw ID."""
    match = re.search(r"(\d{8,10})", str(course_input))
    return match.group(1) if match else str(course_input).strip()


def sanitize_filename(name: str) -> str:
    """Removes invalid filename characters."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def clean_vtt_to_text(vtt_text: str, title: str = "") -> str:
    """
    Parses a WebVTT transcript file and converts it into a clean,
    readable plain text transcript with title and formatting.
    """
    header = f"{title}\n{'=' * max(len(title), 20)}\n\n" if title else ""
    lines = vtt_text.splitlines()
    cleaned_lines = []
    prev_line = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:") or line.startswith("NOTE"):
            continue
        if re.match(r"^\d+$", line):  # Skip cue numbers
            continue
        if "-->" in line:  # Skip timestamps
            continue
        line = re.sub(r"<[^>]+>", "", line)  # Strip inline HTML tags

        # Avoid duplicate consecutive subtitle lines
        if line != prev_line:
            cleaned_lines.append(line)
            prev_line = line

    content = " ".join(cleaned_lines)
    # Break into sentences/paragraphs nicely
    content = re.sub(r"([.?!])\s+", r"\1\n\n", content)
    return header + content


def download_file(url: str, dest_path: Path, force: bool = False, timeout: int = 60) -> bool:
    """
    Downloads a file from url to dest_path using standard urllib.
    Skips download if file already exists and is non-empty (unless force=True).
    """
    if not force and dest_path.exists() and dest_path.stat().st_size > 0:
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            with open(dest_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        return True
    except Exception:
        if dest_path.exists() and dest_path.stat().st_size == 0:
            dest_path.unlink()
        return False


def download_drive_file(file_id: str, dest_path: Path, force: bool = False) -> bool:
    """
    Downloads a file from Google Drive given its file_id.
    Handles Google Drive virus scan warning redirects automatically.
    """
    if not force and dest_path.exists() and dest_path.stat().st_size > 0:
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read()
            # If Google Drive returned an HTML warning page asking to confirm
            if b"download_warning" in content or b"Google Drive - Virus scan warning" in content:
                match = re.search(r'confirm=([0-9A-Za-z_-]+)', content.decode("utf-8", errors="ignore"))
                if match:
                    confirm_url = f"{url}&confirm={match.group(1)}"
                    with urllib.request.urlopen(urllib.request.Request(confirm_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=45) as r2:
                        content = r2.read()
            with open(dest_path, "wb") as f:
                f.write(content)
        return True
    except Exception:
        if dest_path.exists() and dest_path.stat().st_size == 0:
            dest_path.unlink()
        return False


# ---------------------------------------------------------------------------
# Dynamic NPTEL Course Metadata Fetcher
# ---------------------------------------------------------------------------

def fetch_nptel_course_metadata(course_id: str) -> Optional[dict]:
    """
    Queries NPTEL's course endpoint (__data.json) to extract full course details:
      - Course Title, Professor, Institute
      - Week-by-week structure and lesson names
      - Transcript links (Google Cloud Storage VTT or Google Drive ID)
    """
    url = f"https://nptel.ac.in/courses/{course_id}/__data.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        nodes = data.get("nodes", [])
        if len(nodes) < 2 or not isinstance(nodes[1], dict) or "data" not in nodes[1]:
            return None

        items = nodes[1]["data"]

        def resolve(idx):
            if idx is None:
                return None
            if isinstance(idx, int) and 0 <= idx < len(items):
                return items[idx]
            return idx

        course_outline = None
        for item in items:
            if isinstance(item, dict) and "units" in item and "title" in item:
                course_outline = item
                break

        if not course_outline:
            return None

        title = resolve(course_outline.get("title"))
        professor = resolve(course_outline.get("professor"))
        institute = resolve(course_outline.get("instituteName"))
        unit_indices = resolve(course_outline.get("units", []))

        weeks = []
        global_lec_idx = 1

        for w_num, u_idx in enumerate(unit_indices, 1):
            u_data = resolve(u_idx)
            if not isinstance(u_data, dict):
                continue
            week_raw_name = resolve(u_data.get("name", f"Week {w_num}"))
            lesson_indices = resolve(u_data.get("lessons", []))
            lessons = []

            for l_idx in lesson_indices:
                l_data = resolve(l_idx)
                if not isinstance(l_data, dict):
                    continue
                lec_title = resolve(l_data.get("name", f"Lecture {global_lec_idx}"))
                vtt_map_ref = resolve(l_data.get("vtt_url"))

                transcript_ref = None
                if isinstance(vtt_map_ref, dict):
                    eng_ref = vtt_map_ref.get("English")
                    transcript_ref = resolve(eng_ref)
                    # If English is not available, check any other available language
                    if not transcript_ref:
                        for lang, ref in vtt_map_ref.items():
                            val = resolve(ref)
                            if val:
                                transcript_ref = val
                                break

                lessons.append({
                    "num": global_lec_idx,
                    "title": lec_title,
                    "link": transcript_ref
                })
                global_lec_idx += 1

            weeks.append({
                "week_num": w_num,
                "name": week_raw_name,
                "lessons": lessons
            })

        return {
            "course_id": course_id,
            "title": title or f"Course_{course_id}",
            "professor": professor or "Unknown",
            "institute": institute or "NPTEL",
            "weeks": weeks
        }
    except Exception as e:
        return None


def fetch_course_assignments(course_id: str) -> List[dict]:
    """Fetches assignment download records from the NPTEL downloads API."""
    url = f"https://nptel.ac.in/api/downloads/{course_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8")).get("data", {})
            return data.get("assignments", []) or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def download_transcripts_week_wise(base_dir: Path, course_id: str, force: bool = False):
    """
    Downloads transcripts week-wise for the given course.
    Supports:
      - Swayam WebVTT subtitles (.vtt & clean .txt)
      - Google Drive PDF transcripts (.pdf)
      - Dedicated 110104169 fallback for guaranteed 28/28 transcripts
    """
    print("\n" + "=" * 65)
    print(f"STEP 1: Downloading Transcripts Week-Wise (Course {course_id})")
    print("=" * 65)

    meta = fetch_nptel_course_metadata(course_id)
    downloaded = 0
    cached = 0
    failed = []

    # Case A: Current course 110104169 - Use complete Swayam VTT catalogue
    if course_id == DEFAULT_COURSE_ID:
        for lec in range(1, 29):
            week = 1
            for w, (a, b) in WEEK_MAP_DEFAULT.items():
                if a <= lec <= b:
                    week = w
                    break

            week_dir = base_dir / f"Week_{week}" / "transcript"
            week_dir.mkdir(parents=True, exist_ok=True)

            vtt_dest = week_dir / f"Lecture_{lec:02d}.vtt"
            txt_dest = week_dir / f"Lecture_{lec:02d}.txt"
            vtt_file = VTT_FILES_DEFAULT.get(lec, f"Lec-{lec:02d}.vtt")
            url = VTT_BASE_URL_DEFAULT + vtt_file

            if not force and vtt_dest.exists() and txt_dest.exists() and vtt_dest.stat().st_size > 0:
                cached += 1
                print(f"  [Week {week}] Lecture {lec:02d}: Cached")
                continue

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    vtt_content = resp.read().decode("utf-8", errors="ignore")

                with open(vtt_dest, "w", encoding="utf-8") as f:
                    f.write(vtt_content)

                txt_content = clean_vtt_to_text(vtt_content, title=f"Lecture {lec:02d}")
                with open(txt_dest, "w", encoding="utf-8") as f:
                    f.write(txt_content)

                downloaded += 1
                print(f"  [Week {week}] Lecture {lec:02d}: Downloaded (.txt + .vtt)")
            except Exception as e:
                failed.append((lec, str(e)))
                print(f"  [Week {week}] Lecture {lec:02d}: FAILED ({e})")

    # Case B: Any other NPTEL course - Use dynamically fetched outline
    elif meta and meta.get("weeks"):
        for week_info in meta["weeks"]:
            week_num = week_info["week_num"]
            week_dir = base_dir / f"Week_{week_num}" / "transcript"
            week_dir.mkdir(parents=True, exist_ok=True)

            for lesson in week_info["lessons"]:
                lec_num = lesson["num"]
                lec_title = sanitize_filename(lesson["title"])
                link = lesson.get("link")

                if not link:
                    continue

                # Type 1: Google Cloud Storage VTT file
                if str(link).startswith("gs://") or str(link).endswith(".vtt"):
                    vtt_dest = week_dir / f"Lecture_{lec_num:02d}.vtt"
                    txt_dest = week_dir / f"Lecture_{lec_num:02d}.txt"

                    if not force and vtt_dest.exists() and txt_dest.exists() and vtt_dest.stat().st_size > 0:
                        cached += 1
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: Cached")
                        continue

                    http_url = str(link).replace("gs://", "https://storage.googleapis.com/")
                    try:
                        req = urllib.request.Request(http_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            vtt_content = resp.read().decode("utf-8", errors="ignore")

                        with open(vtt_dest, "w", encoding="utf-8") as f:
                            f.write(vtt_content)

                        txt_content = clean_vtt_to_text(vtt_content, title=f"Lecture {lec_num:02d}: {lec_title}")
                        with open(txt_dest, "w", encoding="utf-8") as f:
                            f.write(txt_content)

                        downloaded += 1
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: Downloaded (.txt + .vtt)")
                    except Exception as e:
                        failed.append((lec_num, str(e)))
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: FAILED ({e})")

                # Type 2: Google Drive PDF transcript
                else:
                    drive_id = link
                    # Extract ID if a full drive URL is given
                    m = re.search(r"/d/([a-zA-Z0-9_-]+)", str(link))
                    if m:
                        drive_id = m.group(1)

                    pdf_dest = week_dir / f"Lecture_{lec_num:02d}.pdf"
                    if not force and pdf_dest.exists() and pdf_dest.stat().st_size > 0:
                        cached += 1
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: Cached (.pdf)")
                        continue

                    if download_drive_file(drive_id, pdf_dest, force=force):
                        downloaded += 1
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: Downloaded (.pdf)")
                    else:
                        failed.append((lec_num, "Google Drive fetch failed"))
                        print(f"  [Week {week_num}] Lecture {lec_num:02d}: FAILED (.pdf)")
    else:
        print(f"Warning: Could not fetch syllabus metadata for Course {course_id}.")

    print(f"\nTranscripts Summary: {downloaded} downloaded, {cached} cached, {len(failed)} failed.")


def download_assignments_week_wise(base_dir: Path, course_id: str, force: bool = False):
    """
    Downloads course assignments week-wise directly from NPTEL's downloads repository.
    """
    print("\n" + "=" * 65)
    print(f"STEP 2: Downloading Weekly Assignments (Course {course_id})")
    print("=" * 65)

    downloaded = 0
    cached = 0
    failed = []

    # Check NPTEL downloads API first
    assignments = fetch_course_assignments(course_id)

    if assignments:
        for item in assignments:
            title = sanitize_filename(item.get("title", "assignment"))
            url = item.get("url")
            if not url:
                continue

            # Determine target week from filename
            m = re.search(r"week[_-]?(\d+)", title, re.IGNORECASE)
            week_folder = f"Week_{m.group(1)}" if m else "Assignments"

            dest_dir = base_dir / week_folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / title

            if not force and dest.exists() and dest.stat().st_size > 0:
                cached += 1
                print(f"  {title}: Cached")
                continue

            if download_file(url, dest, force=force):
                downloaded += 1
                print(f"  {title}: Downloaded successfully")
            else:
                failed.append(title)
                print(f"  {title}: FAILED to download")

    # Fallback for Course 110104169
    elif course_id == DEFAULT_COURSE_ID:
        for week in range(1, 9):
            week_dir = base_dir / f"Week_{week}"
            week_dir.mkdir(parents=True, exist_ok=True)
            dest = week_dir / f"assignment_Week_{week}.png"
            url = f"https://archive.nptel.ac.in/content/storage2/courses/downloads_new/110104169/noc23_mg119_assignment_Week_{week}.png"

            if not force and dest.exists() and dest.stat().st_size > 0:
                cached += 1
                print(f"  Week {week} Assignment: Cached")
                continue

            if download_file(url, dest, force=force):
                downloaded += 1
                print(f"  Week {week} Assignment: Downloaded")
            else:
                failed.append(f"Week {week}")
                print(f"  Week {week} Assignment: FAILED")
    else:
        print(f"No assignments found online for Course {course_id}.")

    print(f"\nAssignments Summary: {downloaded} downloaded, {cached} cached, {len(failed)} failed.")


def download_missing_lecture_videos(base_dir: Path, force: bool = False):
    """
    Optional: Downloads video media (MP4) for lectures specified in MISSING_VIDEOS_DEFAULT.
    """
    print("\n" + "=" * 65)
    print("STEP 2b: Downloading Missing Lecture Video Media (MP4)")
    print("=" * 65)

    for lec, modlec in MISSING_VIDEOS_DEFAULT.items():
        week = 1
        for w, (a, b) in WEEK_MAP_DEFAULT.items():
            if a <= lec <= b:
                week = w
                break

        tdir = base_dir / f"Week_{week}" / "transcript"
        tdir.mkdir(parents=True, exist_ok=True)
        dest = tdir / f"Lecture_{lec:02d}.mp4"
        url = f"https://media.dev.nptel.ac.in/content/mp4/110/104/{DEFAULT_COURSE_ID}/MP4/{modlec}.mp4"

        if not force and dest.exists() and dest.stat().st_size > 0:
            print(f"  Lecture {lec:02d} Video: Cached")
            continue

        print(f"  Lecture {lec:02d}: Attempting video download from {url}...")
        if download_file(url, dest, force=force, timeout=120):
            print(f"  Lecture {lec:02d} Video: Saved to {dest.name}")
        else:
            print(f"  Lecture {lec:02d} Video: Unavailable or skipped")


def download_and_organize_toc_ppts(base_dir: Path, force: bool = False):
    """
    Downloads Sridhar Iyer's Theory of Computation (TOC) PPTs (25 slides),
    caches them in TOC_PPTs/_all/, and organizes them into DBATU syllabus unit folders.
    """
    print("\n" + "=" * 65)
    print("STEP 3: Downloading & Organizing TOC PPTs (Sridhar Iyer)")
    print("=" * 65)

    root = base_dir / "TOC_PPTs"
    cache = root / "_all"
    cache.mkdir(parents=True, exist_ok=True)

    def ppt_filename(n: int) -> str:
        return f"PPT{n:02d} - {TOC_PPTS[n][1]}.pptx"

    downloaded = 0
    cached = 0
    failed = []

    for n in sorted(TOC_PPTS):
        dest = cache / ppt_filename(n)
        url = TOC_BASE + TOC_PPTS[n][0]

        if not force and dest.exists() and dest.stat().st_size > 0:
            cached += 1
            continue

        if download_file(url, dest, force=force):
            downloaded += 1
            print(f"  PPT{n:02d}: Downloaded ({TOC_PPTS[n][1]})")
        else:
            failed.append(n)
            print(f"  PPT{n:02d}: FAILED ({url})")

    print(f"\nPPT Download Summary: {downloaded} downloaded, {cached} cached, {len(failed)} failed.")

    organized_count = 0
    for unit_folder, nums in TOC_UNITS.items():
        unit_dir = root / unit_folder
        unit_dir.mkdir(parents=True, exist_ok=True)
        for n in nums:
            src = cache / ppt_filename(n)
            target = unit_dir / ppt_filename(n)
            if src.exists():
                shutil.copy2(src, target)
                organized_count += 1

    print(f"Organized {organized_count} PPT references across {len(TOC_UNITS)} syllabus unit folders.")


def categorize_and_consolidate(base_dir: Path):
    """
    Consolidates files from all Week_* folders into central directories:
      - Assignments/ : All assignment images/documents
      - Transcripts/ : All lecture transcripts (.txt, .vtt, .pdf, .mp4)
    """
    print("\n" + "=" * 65)
    print("STEP 4: Categorizing & Consolidating Course Materials")
    print("=" * 65)

    assign_dir = base_dir / "Assignments"
    transcript_dir = base_dir / "Transcripts"

    assign_dir.mkdir(parents=True, exist_ok=True)
    transcript_dir.mkdir(parents=True, exist_ok=True)

    copied_assign = 0
    copied_transcript = 0
    week_folders = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.lower().startswith("week")])

    for week_dir in week_folders:
        # --- Assignments ---
        for entry in week_dir.iterdir():
            if entry.is_file() and "assignment" in entry.name.lower():
                target = assign_dir / entry.name
                shutil.copy2(entry, target)
                copied_assign += 1

        # --- Transcripts (.txt, .vtt, .pdf, .mp4, etc.) ---
        transcript_src = week_dir / "transcript"
        if transcript_src.is_dir():
            for entry in transcript_src.iterdir():
                if entry.is_file():
                    target = transcript_dir / entry.name
                    shutil.copy2(entry, target)
                    copied_transcript += 1

    print(f"Categorization Complete:")
    print(f"  - Consolidated Assignments : {copied_assign} file(s) -> {assign_dir}")
    print(f"  - Consolidated Transcripts : {copied_transcript} file(s) -> {transcript_dir}")


# ---------------------------------------------------------------------------
# CLI & Execution
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Unified NPTEL Course Material & Transcript Pipeline (Universal Course Support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nptel_pipeline.py                           # Default: downloads course 110104169
  python nptel_pipeline.py -c 106106145              # Download Python DSA course (106106145)
  python nptel_pipeline.py -c https://nptel.ac.in/courses/106105162  # By full NPTEL URL
  python nptel_pipeline.py -c 106106145 -d D:\\PythonCourse          # Specify custom folder
  python nptel_pipeline.py --ppts                    # Download & organize TOC PPTs
  python nptel_pipeline.py --categorize              # Organize existing materials
        """
    )

    parser.add_argument(
        "-c", "--course",
        type=str,
        default=DEFAULT_COURSE_ID,
        help=f"NPTEL Course ID or URL (Default: {DEFAULT_COURSE_ID})"
    )
    parser.add_argument(
        "-d", "--dir",
        type=Path,
        default=None,
        help="Target directory for course material (Default: ./<CourseName> or C:\\Users\\alien\\nptel_material)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run full course pipeline (Transcripts, Assignments, Categorization)"
    )
    parser.add_argument(
        "--transcripts",
        action="store_true",
        help="Download transcripts week-wise only"
    )
    parser.add_argument(
        "--assignments",
        action="store_true",
        help="Download weekly assignments only"
    )
    parser.add_argument(
        "--ppts",
        action="store_true",
        help="Download and unit-organize Theory of Computation (TOC) PPTs (Sridhar Iyer)"
    )
    parser.add_argument(
        "--videos",
        action="store_true",
        help="Attempt to download missing lecture video media (MP4)"
    )
    parser.add_argument(
        "--categorize",
        action="store_true",
        help="Consolidate materials into central Assignments and Transcripts folders"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if files already exist locally"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    course_id = parse_course_id(args.course)

    # Determine destination folder
    if args.dir:
        base_dir = args.dir.resolve()
    elif course_id == DEFAULT_COURSE_ID:
        base_dir = DEFAULT_BASE_DIR.resolve()
    else:
        # Fetch course title for folder name
        meta = fetch_nptel_course_metadata(course_id)
        folder_name = sanitize_filename(meta["title"]) if meta and meta.get("title") else f"nptel_{course_id}"
        base_dir = Path(f"./{folder_name}").resolve()

    base_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(" NPTEL COURSE MATERIAL & TRANSCRIPT PIPELINE")
    print(f" Course ID:        {course_id}")
    print(f" Target Directory: {base_dir}")
    print("=" * 65)

    run_all = args.all or not (args.transcripts or args.assignments or args.ppts or args.videos or args.categorize)

    if run_all or args.transcripts:
        download_transcripts_week_wise(base_dir, course_id=course_id, force=args.force)

    if run_all or args.assignments:
        download_assignments_week_wise(base_dir, course_id=course_id, force=args.force)

    if args.videos:
        download_missing_lecture_videos(base_dir, force=args.force)

    if args.ppts:
        download_and_organize_toc_ppts(base_dir, force=args.force)

    if run_all or args.categorize:
        categorize_and_consolidate(base_dir)

    print("\n" + "=" * 65)
    print(" [OK] Pipeline finished successfully!")
    print(f" Output Location: {base_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
