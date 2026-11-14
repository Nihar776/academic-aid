# NPTEL Course Material & Transcript Pipeline

A fast, dependency-free command-line tool to download, format, and organize transcripts, assignments, and course materials for **any NPTEL / Swayam course**.

---

## Highlights

- **Universal Course Support**: Works for **any** NPTEL course using either a Course ID (e.g. `106106145`) or full course URL.
- **Zero External Dependencies**: Uses only standard Python 3 libraries (`urllib`, `shutil`, `json`, `re`, `argparse`). No need to install `requests`, `playwright`, or browser binaries.
- **Dual Transcript Formats**:
  - **`.txt`**: Clean, readable lecture notes with title headers, formatted paragraphs, and timestamps stripped.
  - **`.vtt`**: Raw captioned WebVTT files with exact timestamps.
  - **`.pdf`**: Direct Google Drive transcript downloads for courses providing PDF transcripts.
- **Weekly Assignments**: Automatically downloads weekly assignment documents/images.
- **Automatic Organization & Categorization**:
  - Organizes materials week-wise (`Week_1`, `Week_2`, ...).
  - Consolidates all assignments into a central `Assignments/` directory.
  - Consolidates all transcripts into a central `Transcripts/` directory.
- **Smart Caching**: Skips existing non-empty files so re-running or updating is instantaneous.
- **Supplementary TOC PPT Support**: Built-in downloader for Sridhar Iyer's Theory of Computation PPTs organized by DBATU syllabus units (`--ppts`).

---

## Requirements

- **Python 3.8+**
- No external packages needed (`pip install` is **not** required).

---

## Quick Start

### 1. Default Course
By default (without arguments), the script downloads and categorizes materials for **Course `110104169`** (*Advanced Algorithmic Trading and Portfolio Management*):
```bash
python nptel_pipeline.py
```

### 2. Any Other NPTEL Course
Download materials for any course using its NPTEL Course ID or URL:
```bash
# By Course ID (e.g., Programming, Data Structures and Algorithms using Python)
python nptel_pipeline.py -c 106106145

# By Full Course URL
python nptel_pipeline.py -c https://nptel.ac.in/courses/106105162
```

### 3. Custom Output Directory
Specify where you want the course folder saved:
```bash
python nptel_pipeline.py -c 106106145 -d ./python_dsa_course
```

---

## CLI Options

| Option | Flag | Description |
| :--- | :--- | :--- |
| `--course` | `-c` | NPTEL Course ID (e.g. `106106145`) or full NPTEL course URL. *(Default: `110104169`)* |
| `--dir` | `-d` | Destination directory. *(Default: `./<CourseTitle>` or `C:\Users\alien\nptel_material`)* |
| `--all` | | Runs the complete pipeline (Transcripts, Assignments, and Categorization). This is the default if no specific action flag is passed. |
| `--transcripts` | | Download transcripts week-wise only. |
| `--assignments` | | Download course assignments week-wise only. |
| `--ppts` | | Download and unit-organize Sridhar Iyer's Theory of Computation (TOC) PPTs. |
| `--categorize` | | Consolidate files from week folders into central `Assignments/` and `Transcripts/` folders. |
| `--videos` | | Attempt video media (MP4) download for missing lecture fallbacks. |
| `--force` | | Force re-download even if files already exist locally. |

---

## Directory Structure

Running the pipeline produces an organized hierarchy:

```text
nptel_material/
├── Week_1/
│   ├── assignment_Week_1.png
│   └── transcript/
│       ├── Lecture_01.txt       <-- Clean, readable text notes
│       ├── Lecture_01.vtt       <-- Raw captioned subtitles
│       ├── Lecture_02.txt
│       └── ...
├── Week_2/
│   ├── assignment_Week_2.png
│   └── transcript/
│       └── ...
├── Assignments/                 <-- Consolidated assignments
│   ├── assignment_Week_1.png
│   └── ...
├── Transcripts/                 <-- Consolidated transcripts (.txt, .vtt, .pdf)
│   ├── Lecture_01.txt
│   ├── Lecture_01.vtt
│   └── ...
└── TOC_PPTs/                    <-- Optional with --ppts
    ├── Unit1_Finite_Automata/
    ├── Unit2_RegEx_RegGrammar_PumpingLemma/
    ├── Unit3_CFG/
    ├── Unit4_PDA_and_TM/
    └── _all/
```

---

## Legacy Scripts Consolidated

This unified script replaces and deprecates:
- `download_nptel.py`: Replaced with native NPTEL API queries (no Playwright needed).
- `download_nptel_missing_lecs.py`: Integrated into the unified transcript downloader and `--videos` fallback.
- `nptel_material_categorization.py`: Built into Step 4 consolidation.
- `download_toc_ppts.py`: Integrated into `--ppts`.
