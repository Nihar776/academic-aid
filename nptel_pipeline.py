#!/usr/bin/env python3
"""
=============================================================================
Unified NPTEL & Course Material Manager
=============================================================================
This script merges and unifies:
  1. download_nptel_missing_lecs.py (Video & missing lecture downloads)
  2. download_toc_ppts.py           (TOC lecture PPTs & unit-wise organization)
  3. nptel_material_categorization.py (Consolidating assignments & transcripts)
  + Integrated NPTEL transcript downloader (Full text & VTT transcripts for all 28 lectures)
  + Integrated NPTEL assignment downloader (Weeks 1 to 8)

Key Features:
  - Zero external dependencies: Uses Python 3 standard library only (no requests/playwright needed).
  - Week-wise transcript downloading: Fetches transcripts for all 28 lectures across Weeks 1 to 8.
  - Generates both clean readable text (.txt) and raw timed subtitles (.vtt).
  - Organizes TOC PPTs into DBATU syllabus units.
  - Consolidates assignments and transcripts into central categorized folders.
  - Resume & cache support: Skips existing non-empty files unless --force is specified.
=============================================================================
"""

import argparse
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants & Configurations
# ---------------------------------------------------------------------------

DEFAULT_BASE_DIR = Path(r"C:\Users\alien\nptel_material") if Path(r"C:\Users\alien\nptel_material").exists() else Path("./nptel_material")

# NPTEL Course metadata
NPTEL_SUBJECT_ID = "110104169"
NPTEL_COURSE_CODE = "noc23_mg119"
NPTEL_COURSE_TITLE = "Advanced Algorithmic Trading and Portfolio Management"

# Lecture to Week mapping (8 Weeks, 28 Lectures)
WEEK_MAP = {
    1: (1, 3),
    2: (4, 7),
    3: (8, 11),
    4: (12, 15),
    5: (16, 19),
    6: (20, 23),
    7: (24, 26),
    8: (27, 28),
}

# Lecture titles
LECTURE_TITLES = {
    1: "Fundamentals of R",
    2: "Data Cleaning",
    3: "Data Visualization",
    4: "Introduction to Risk and Return",
    5: "Portfolio Theory and Asset Pricing Models",
    6: "Portfolio Optimization and Mean Variance Framework",
    7: "Advanced Portfolio Optimization: Part 1",
    8: "Advanced Portfolio Optimization: Part 2",
    9: "Capital Asset Pricing Model (CAPM)",
    10: "Single and Multi-Index Models",
    11: "Introduction to Arbitrage Pricing Theory (APT)",
    12: "Portfolio Management Strategies",
    13: "Portfolio Performance Evaluation: One Parameter Measures",
    14: "Portfolio Performance Evaluation: Timing and Selection",
    15: "Introduction to tail-risk measures: VaR and CVaR",
    16: "Initiating with Portfolio Object in R",
    17: "Trend-determining techniques",
    18: "Moving average indicators",
    19: "Momentum indicators",
    20: "R Application for Technical Analysis and Algorithmic Trading - Part 1",
    21: "R Application for Technical Analysis and Algorithmic Trading - Part 2",
    22: "Introduction to Panel Data Modelling",
    23: "Panel data application and implementation with R",
    24: "Techniques for Computing Efficient Frontier",
    25: "Alternative forms of CAPM - Part 1",
    26: "Alternative forms of CAPM - Part 2",
    27: "Volatility modelling",
    28: "Tail Risk Measurement: VaR and CVaR models",
}

# Swayam VTT Subtitle filenames (all 28 lectures available)
VTT_BASE_URL = "https://storage.googleapis.com/swayam-node1-production.appspot.com/assets/vtt/noc24_mg83/"
VTT_FILENAMES = {
    1: "Lec-01.vtt",
    2: "Lec-02.vtt",
    3: "Lec-03.vtt",
    4: "Lec-04.vtt",
    5: "Lec-05.vtt",
    6: "Lec-06.vtt",
    7: "Lec-07.vtt",
    8: "Lec-%2008.vtt",   # Handled for server space in path
    9: "Lec-09.vtt",
    10: "Lec-10.vtt",
    11: "Lec--11.vtt",   # Handled for server double dash in path
    12: "Lec-12.vtt",
    13: "Lec-13.vtt",
    14: "Lec-14.vtt",
    15: "Lec-15.vtt",
    16: "Lec-16.vtt",
    17: "Lec-17.vtt",
    18: "Lec-18.vtt",
    19: "Lec-19.vtt",
    20: "Lec-20.vtt",
    21: "Lec-21.vtt",
    22: "Lec-22.vtt",
    23: "Lec-23.vtt",
    24: "Lec-24.vtt",
    25: "Lec-25.vtt",
    26: "Lec-26.vtt",
    27: "Lec-27.vtt",
    28: "Lec-28.vtt",
}

# NPTEL Media Base for lecture videos (MP4)
NPTEL_VIDEO_BASE = f"https://media.dev.nptel.ac.in/content/mp4/110/104/{NPTEL_SUBJECT_ID}/MP4"
MISSING_VIDEOS = {
    20: "mod05lec20",
    24: "mod07lec24",
    25: "mod07lec25",
    26: "mod07lec26",
}

# NPTEL Assignment Base
NPTEL_ASSIGNMENT_BASE = f"https://archive.nptel.ac.in/content/storage2/courses/downloads_new/{NPTEL_SUBJECT_ID}"

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
# Helper Functions
# ---------------------------------------------------------------------------

def week_of(lec: int) -> int:
    """Returns the week number (1-8) for a given lecture number (1-28)."""
    for w, (a, b) in WEEK_MAP.items():
        if a <= lec <= b:
            return w
    return 1


def clean_vtt_to_text(vtt_text: str, lec: int) -> str:
    """
    Parses a WebVTT transcript file and converts it into a clean,
    readable plain text transcript with title and formatting.
    """
    title = LECTURE_TITLES.get(lec, f"Lecture {lec:02d}")
    header = f"Lecture {lec:02d}: {title}\n{'=' * (len(title) + 12)}\n\n"

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
        return True  # Already cached

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            with open(dest_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        if dest_path.exists() and dest_path.stat().st_size == 0:
            dest_path.unlink()
        return False


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def download_transcripts_week_wise(base_dir: Path, force: bool = False):
    """
    Downloads transcripts for all 28 lectures, saves them week-wise in
    Week_{week}/transcript/, creating both:
      - Lecture_{lec:02d}.vtt (Raw timed subtitles)
      - Lecture_{lec:02d}.txt (Clean readable transcript notes)
    """
    print("\n" + "=" * 65)
    print("STEP 1: Downloading Transcripts Week-Wise (Lectures 1 to 28)")
    print("=" * 65)

    downloaded = 0
    cached = 0
    failed = []

    for lec in range(1, 29):
        week = week_of(lec)
        week_dir = base_dir / f"Week_{week}" / "transcript"
        week_dir.mkdir(parents=True, exist_ok=True)

        vtt_dest = week_dir / f"Lecture_{lec:02d}.vtt"
        txt_dest = week_dir / f"Lecture_{lec:02d}.txt"
        vtt_file = VTT_FILENAMES.get(lec, f"Lec-{lec:02d}.vtt")
        url = VTT_BASE_URL + vtt_file
        title = LECTURE_TITLES.get(lec, "")

        if not force and vtt_dest.exists() and txt_dest.exists() and vtt_dest.stat().st_size > 0:
            cached += 1
            print(f"  [Week {week}] Lecture {lec:02d}: Cached ({title})")
            continue

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                vtt_content = resp.read().decode("utf-8", errors="ignore")

            # Write .vtt file
            with open(vtt_dest, "w", encoding="utf-8") as f:
                f.write(vtt_content)

            # Write clean .txt file
            txt_content = clean_vtt_to_text(vtt_content, lec)
            with open(txt_dest, "w", encoding="utf-8") as f:
                f.write(txt_content)

            downloaded += 1
            print(f"  [Week {week}] Lecture {lec:02d}: Downloaded ({title})")
        except Exception as e:
            failed.append((lec, str(e)))
            print(f"  [Week {week}] Lecture {lec:02d}: FAILED ({e})")

    print(f"\nTranscripts Summary: {downloaded} downloaded, {cached} cached, {len(failed)} failed.")
    if failed:
        for lec, err in failed:
            print(f"  - Lecture {lec}: {err}")


def download_assignments_week_wise(base_dir: Path, force: bool = False):
    """
    Downloads assignment images for Weeks 1 through 8 directly into
    their respective Week_{week} folders.
    """
    print("\n" + "=" * 65)
    print("STEP 2: Downloading Weekly Assignments (Weeks 1 to 8)")
    print("=" * 65)

    downloaded = 0
    cached = 0
    failed = []

    for week in range(1, 9):
        week_dir = base_dir / f"Week_{week}"
        week_dir.mkdir(parents=True, exist_ok=True)
        dest = week_dir / f"assignment_Week_{week}.png"
        url = f"{NPTEL_ASSIGNMENT_BASE}/{NPTEL_COURSE_CODE}_assignment_Week_{week}.png"

        if not force and dest.exists() and dest.stat().st_size > 0:
            cached += 1
            print(f"  Week {week} Assignment: Cached")
            continue

        if download_file(url, dest, force=force):
            downloaded += 1
            print(f"  Week {week} Assignment: Downloaded successfully")
        else:
            failed.append(week)
            print(f"  Week {week} Assignment: FAILED to download")

    print(f"\nAssignments Summary: {downloaded} downloaded, {cached} cached, {len(failed)} failed.")


def download_missing_lecture_videos(base_dir: Path, force: bool = False):
    """
    Optional: Downloads video media (MP4) for lectures specified in MISSING_VIDEOS.
    Saves to Week_{week}/transcript/Lecture_{lec:02d}.mp4.
    """
    print("\n" + "=" * 65)
    print("STEP 2b: Downloading Missing Lecture Video Media (MP4)")
    print("=" * 65)

    for lec, modlec in MISSING_VIDEOS.items():
        week = week_of(lec)
        tdir = base_dir / f"Week_{week}" / "transcript"
        tdir.mkdir(parents=True, exist_ok=True)
        dest = tdir / f"Lecture_{lec:02d}.mp4"
        url = f"{NPTEL_VIDEO_BASE}/{modlec}.mp4"

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

    # Download all PPTs to cache
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

    # Organize PPTs into unit folders
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
    Consolidates files from all Week_1 to Week_8 folders into central directories:
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
    skipped_weeks = []

    for week in range(1, 9):
        week_dir = base_dir / f"Week_{week}"
        if not week_dir.is_dir():
            skipped_weeks.append(f"Week_{week} directory missing")
            continue

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
        else:
            skipped_weeks.append(f"Week_{week}: no transcript directory found")

    print(f"Categorization Complete:")
    print(f"  - Consolidated Assignments : {copied_assign} file(s) -> {assign_dir}")
    print(f"  - Consolidated Transcripts : {copied_transcript} file(s) -> {transcript_dir}")
    if skipped_weeks:
        print("Notes / Warnings:")
        for s in skipped_weeks:
            print(f"  - {s}")


# ---------------------------------------------------------------------------
# CLI & Execution
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Unified NPTEL Transcript & Course Material Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python nptel_pipeline.py                      # Run complete pipeline
  python nptel_pipeline.py --transcripts        # Download only transcripts week-wise
  python nptel_pipeline.py --assignments        # Download only assignments
  python nptel_pipeline.py --ppts               # Download & organize TOC PPTs
  python nptel_pipeline.py --categorize         # Organize existing materials
  python nptel_pipeline.py --dir D:\\MyCourse   # Specify custom destination directory
        """
    )

    parser.add_argument(
        "-d", "--dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"Target directory for course material (Default: {DEFAULT_BASE_DIR})"
    )
    parser.add_argument(
        "--transcripts",
        action="store_true",
        help="Download all transcripts week-wise (Weeks 1 to 8, Lectures 1 to 28)"
    )
    parser.add_argument(
        "--assignments",
        action="store_true",
        help="Download weekly assignments (Weeks 1 to 8)"
    )
    parser.add_argument(
        "--ppts",
        action="store_true",
        help="Download and unit-organize Theory of Computation (TOC) PPTs"
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
    base_dir = args.dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(" NPTEL COURSE MATERIAL & TRANSCRIPT PIPELINE")
    print(f" Target Directory: {base_dir}")
    print("=" * 65)

    # Determine actions: If no specific flag is given, run full pipeline
    run_all = not (args.transcripts or args.assignments or args.ppts or args.videos or args.categorize)

    if run_all or args.transcripts:
        download_transcripts_week_wise(base_dir, force=args.force)

    if run_all or args.assignments:
        download_assignments_week_wise(base_dir, force=args.force)

    if args.videos:
        download_missing_lecture_videos(base_dir, force=args.force)

    if run_all or args.ppts:
        download_and_organize_toc_ppts(base_dir, force=args.force)

    if run_all or args.categorize:
        categorize_and_consolidate(base_dir)

    print("\n" + "=" * 65)
    print(" [OK] All requested operations completed successfully!")
    print(f" Output Location: {base_dir}")
    print("=" * 65)


if __name__ == "__main__":
    main()
