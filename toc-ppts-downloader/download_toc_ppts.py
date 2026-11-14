#!/usr/bin/env python3
"""
Downloads Sridhar Iyer's TOC PPTs and organizes them unit-wise (DBATU syllabus).
Run:  python download_toc_ppts.py
Needs only Python 3 (no extra packages). Creates ./TOC_PPTs/ next to the script.

PPTs that cover more than one unit are copied into each relevant folder.
Folders ending in "_check" hold PPTs whose unit fit is a guess (verify after opening).
"""
import shutil
import urllib.request
from pathlib import Path

BASE = "http://iamsridhariyer.com/wp-content/uploads/"

# number -> (path under /wp-content/uploads/, short label)
PPTS = {
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

# folder -> PPT numbers
UNITS = {
    "Unit1_Finite_Automata": [1, 2, 3, 4, 8, 9, 10, 11, 12, 13],
    "Unit2_RegEx_RegGrammar_PumpingLemma": [5, 6, 7, 13, 14, 15, 16, 17],
    "Unit3_CFG": [18, 19],
    "Unit3_CFG_check": [14, 16, 17],  # may also cover derivations/ambiguity
    "Unit4_PDA_and_TM": [20, 21, 22, 23, 24, 25],
    "Unit5_Undecidability_check": [25],  # only possible source; verify contents
}

root = Path("TOC_PPTs")
cache = root / "_all"
cache.mkdir(parents=True, exist_ok=True)


def fname(n):
    return f"PPT{n:02d} - {PPTS[n][1]}.pptx"


def download(n):
    dest = cache / fname(n)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = BASE + PPTS[n][0]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        print(f"downloaded PPT{n:02d}")
        return dest
    except Exception as e:
        print(f"FAILED PPT{n:02d}: {e}\n   try opening manually: {url}")
        return None


for n in sorted(PPTS):
    download(n)

for folder, nums in UNITS.items():
    d = root / folder
    d.mkdir(exist_ok=True)
    for n in nums:
        src = cache / fname(n)
        if src.exists():
            shutil.copy2(src, d / fname(n))

print("\nDone. Open the TOC_PPTs folder. You can delete _all/ afterwards.")
