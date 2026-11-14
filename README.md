# DBATU PYP Fetcher

An automated, intelligent bulk scraper, parser, and downloader for **Dr. Babasaheb Ambedkar Technological University (DBATU)** Previous Year Question Papers (PYPs / PYQs) from the official **Knimbus Digital Library Portal**.

It searches course materials, applies portal and content filters, extracts metadata directly from question paper PDFs, organizes them into semester-wise folders, and renames them following a clean, standardized naming format.

---

## Key Features

- **Automated Bulk Fetching**: Automatically searches and iterates through multi-page results on the Knimbus portal for any number of configured subjects.
- **Semester-Wise Organization**: Automatically parses the semester from DBATU course codes and PDF text, routing papers into structured subfolders (e.g. `Machine_Learning/sem5/`).
- **Standardized Naming Convention**:
  ```text
  {sem}-{year}-{summer|winter}-{R|S}-{CourseCode}[-n].pdf
  ```
  *(e.g., `sem5-2023-winter-R-BTCOC501.pdf` or `sem5-2024-summer-S-BTIT502.pdf`)*
  - `R` = Regular Examination
  - `S` = Supplementary Examination
  - `[-n]` = Automatic collision resolution suffix (only appended if distinct papers share identical metadata)
- **Branch & Discipline Filtering**:
  - **Portal Level**: Restricts results using Knimbus subject facets (e.g., `Computer Engineering`, `Information Technology`).
  - **Deep PDF & Code Level**: Validates DBATU course code prefixes (e.g. accepts `BTCOC`, `BTCSE`, `BTCSD`, `BTIT`, `BTAIC` and discards unrelated branches like Robotics `BTARPE`, Electronics `BTECPC`, or Telecom `BTETOE`).
- **Degree / Programme Filtering**: Supports B.Tech, Diploma, M.Tech, B. Pharmacy, and B. Architecture, or all courses without restrictions.
- **End-Semester Examination Focus**: Automatically detects and discards Mid-Semester Tests (CA/MSE) and Class Tests using dual-layer card and PDF text heuristics.
- **Multi-Vector Download Engine**: Captures PDFs via direct link resolution, network response streams, browser download events, or embedded viewer iframes.
- **Deduplication & Incremental Downloads**: Computes SHA-256 hashes of paper contents and maintains a `manifest.json` so papers are never downloaded twice.
- **Persistent Browser Profile**: Keeps session cookies and authentication in `.browser-profile/`, avoiding repetitive logins.

---

## Directory Structure

```text
dbatu-pyp-fetcher/
├── config.yaml          # Base configuration (central URL, credentials, default output dir, filters)
├── configs/             # Branch / Course / Semester-specific subject configs
│   ├── aiml_sem5.yaml   # AI & ML Semester 5 subjects and branch overrides
│   ├── cse_sem5.yaml    # Computer Science & Engineering Semester 5 subjects
│   └── it_sem5.yaml     # Information Technology Semester 5 subjects
├── pyq_fetch.py         # Main crawler, parser, and download engine
├── requirements.txt     # Python dependencies
├── pyrightconfig.json   # Static analysis / type configuration
├── .gitignore           # Ignores PDFs, caches, and browser profile
└── PYPs/                # Downloaded papers organized by subject & semester
    └── AIML/
        └── Semester-05/
            ├── Machine_Learning/
            │   ├── sem5/
            │   │   ├── sem5-2022-winter-R-BTCOC501.pdf
            │   │   └── sem5-2023-winter-R-BTCOC501.pdf
            │   └── sem6/
            │       └── sem6-2024-summer-R-BTCOC602.pdf
            └── manifest.json
```

---

## Prerequisites & Installation

1. **Python 3.10+** is required.
2. Clone this repository and navigate to the project root:
   ```bash
   git clone https://github.com/Nihar776/academic-aid.git
   cd academic-aid/dbatu-pyp-fetcher
   ```
3. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install Playwright browser binaries (Chromium):
   ```bash
   playwright install chromium
   ```

---

## Configuration Architecture

The project splits configuration into two modular, functional layers:

### 1. Base Configuration (`config.yaml`)
Contains global defaults for the scraper:
- Central default `output_dir`
- Knimbus `base_url` and `credentials`
- Unified `course` degree filter (matches Knimbus `REPOSITORY` facet)
- `since_year`, `filters`, `branches`, and `max_pages`
- Optional default `subjects: []` (if empty, the program will prompt you to select a secondary config)

```yaml
output_dir: "./PYPs/"
base_url: "https://dbatulibrary.knimbus.com/portal/v2/default/results/section?sectionId=1ad6bd68-4cc6-4d8b-8550-2203b35075ef&sectionName=QUESTION+PAPERS"

credentials:
  email: "your_email@example.com"
  password: "your_password"

course: "B.Tech Question Paper"
since_year: 2022

filters:
  subject: null                         # None (avoids restrictive portal locks; code-level filter handles branches)
  publication_year: null                # from config.yaml (e.g. [2022, 2023, 2024, 2025, 2026] or null)
  year: null                            # from config.yaml (e.g. [2022, 2023, 2024, 2025, 2026] or null)
  dept: null                            # from config.yaml (e.g. null or ["Computer Engineering"])
  author:                               # supplementary, summer, winter
    - "supplementary"
    - "summer"
    - "winter"

branches:
  - "Computer Engineering"
  - "Computer Science and Engineering"
  - "Information Technology"
  - "Artificial Intelligence and Machine Learning"

max_pages: 15
subjects: []
```

### 2. Secondary Subject Configurations (`configs/*.yaml`)
Contains branch- or semester-specific subjects. **Any setting specified in a secondary config automatically overrides the base config** (for example, overriding `branches` or `output_dir`):

Example (`configs/aiml_sem5.yaml`):
```yaml
output_dir: "./PYPs/AIML/Semester-05/"

branches:
  - "Computer Engineering"
  - "Computer Science and Engineering"
  - "Artificial Intelligence and Machine Learning"

subjects:
  - name: Machine Learning
    search: machine learning
    # output_dir: "D:/Dedicated_ML_Drive" # Optional dedicated address per subject
    keywords: ["machine learning"]
    exclude: ["advanced", "introduction"]
    sem: 5
    codes: []

  - name: AI in Cyber Security
    search: cyber security
    keywords: ["cyber"]
    exclude: []
    sem: 5
    codes: []
```

---

## Usage (The 6 Execution Scenarios)

The program supports 6 distinct execution patterns:

### Case 1: Default Base Config (No Flags)
```bash
python pyq_fetch.py
```
- Uses `config.yaml`.
- If `config.yaml` has subjects, runs them immediately.
- If `config.yaml` has no subjects, displays an interactive list of discovered configs in `configs/` and prompts you to select one or exit.

### Case 2: Custom Base Config Only
```bash
python pyq_fetch.py -c my_base_config.yaml
```
- Uses `my_base_config.yaml` as the base configuration.

### Case 3: Single Secondary Config on Default Base Config
```bash
python pyq_fetch.py -s configs/aiml_sem5.yaml
```
- Uses `config.yaml` as base defaults, merges `configs/aiml_sem5.yaml`, and downloads the AIML subjects with their branch and output folder overrides.

### Case 4: Custom Base Config with Secondary Config
```bash
python pyq_fetch.py -c custom_base.yaml -s configs/aiml_sem5.yaml
```
- Uses `custom_base.yaml` for credentials/settings, and executes the subjects and overrides from `configs/aiml_sem5.yaml`.

### Case 5: Multiple Secondary Configs on Default Base Config
```bash
python pyq_fetch.py -s configs/aiml_sem5.yaml configs/cse_sem5.yaml
```
- Opens the browser once, logs in once, and sequentially downloads and organizes papers for both AIML and CSE in their respective directories.

### Case 6: Multiple Secondary Configs on Custom Base Config
```bash
python pyq_fetch.py -c custom_base.yaml -s configs/aiml_sem5.yaml configs/cse_sem5.yaml configs/it_sem5.yaml
```
- Uses custom credentials/base settings and runs all specified secondary configs in one unified session.

---

## Additional CLI Options

| Flag | Shorthand | Description |
|---|---|---|
| `--config` | `-c` | Path to base configuration file (default: `config.yaml`). |
| `--secondary` | `-s` | One or more secondary subject configuration YAML files. |
| `--only` | | Fetch only specific subject(s) by name, acronym, or comma-separated list (e.g. `--only ML DBMS` or `--only ML,cyber`). |
| `--course` | | Target course/degree override (`B.Tech`, `Diploma`, `M.Tech`, `all`). |
| `--headless` | | Runs browser silently in background mode. |
| `--email` / `--password` | | Override login credentials via CLI. |
| `--debug` | | Saves screenshots and HTML dumps in `debug/` on error. |

---

## Naming & Metadata Rules

Papers are renamed based on the extracted metadata:
- **Semester**: Determined by the 5th/6th character of DBATU course codes (e.g., `BTCOC501` $\to$ `sem5`, `BTIT602` $\to$ `sem6`) or regex matching against the exam header (`FIFTH SEMESTER`).
- **Year & Season**: Extracted from exam dates (e.g., `December 2023` $\to$ `2023-winter`, `May/June 2024` $\to$ `2024-summer`).
- **Exam Type**: Identified as Regular (`R`) or Supplementary (`S`) from title/header tags.
- **Course Code**: Cleaned alphanumeric code (e.g. `BTCOC501`). Slashes in dual codes (`BTETOE505B/BTEXOE505B`) are automatically sanitized to underscores (`BTETOE505B_BTEXOE505B`).

---

## License

MIT License. Designed for academic and educational use by DBATU students and faculty.

