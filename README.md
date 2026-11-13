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
├── config.yaml          # Subjects, target branches, semester, and credentials
├── pyq_fetch.py         # Main crawler, parser, and download engine
├── requirements.txt     # Python dependencies
├── pyrightconfig.json   # Static analysis / type configuration
├── .gitignore           # Ignores PDFs, caches, and browser profile
└── PYPs/                # Downloaded papers organized by subject & semester
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

## Configuration (`config.yaml`)

Configure your target directory, credentials, branches, and subjects in `config.yaml`:

```yaml
# Destination folder for downloaded papers
output_dir: "./PYPs/Semester-05/"

# Knimbus Question Papers section URL
base_url: "https://dbatulibrary.knimbus.com/portal/v2/default/results/section?sectionId=1ad6bd68-4cc6-4d8b-8550-2203b35075ef&sectionName=QUESTION+PAPERS"

# Optional credentials for automated login (leave blank to log in manually in browser)
credentials:
  email: "your_email@example.com"
  password: "your_password"

# Degree filter: "B.Tech Question Paper", "Diploma Question Paper", "M.Tech Question Paper", or "all"
course: "B.Tech Question Paper"

# Filter out older question papers (>= since_year)
since_year: 2022

# Target branches to download (leave [] for all branches)
branches:
  - "Computer Engineering"
  - "Computer Science and Engineering"
  - "Information Technology"

# Max result pages to crawl per subject
max_pages: 15

# List of subjects to search and fetch
subjects:
  - name: Machine Learning
    search: machine learning
    keywords: ["machine learning"]
    exclude: ["advanced", "introduction"]
    sem: 5
    codes: []

  - name: Theory of Computations
    search: theory of computation
    keywords: ["theory of computation"]
    exclude: []
    sem: 5
    codes: []

  - name: Operating Systems
    search: operating systems
    keywords: ["operating system"]
    exclude: ["advanced"]
    sem: 5
    codes: []
```

### Subject Configuration Options:
- `name`: Human-readable subject name (used for folder naming).
- `search`: Keyword string typed into Knimbus "Search within results".
- `keywords`: Keywords that **must** appear in the card title.
- `exclude`: Discard paper if **any** of these terms appear in the title (e.g. `advanced`).
- `sem`: Target semester (`5`, `[5, 6]`, or `null` for any semester).
- `codes`: Optional whitelist of DBATU course codes (e.g. `["BTCOC501"]`). Leave empty `[]` to accept all matched codes.

---

## Usage

### 1. Default Run (Interactive Browser)
Uses `config.yaml` to crawl and download all configured subjects:
```bash
python pyq_fetch.py
```
*(On the first run, if credentials are not in `config.yaml`, log in to Knimbus in the opened browser window. Playwright will store your session in `.browser-profile/` for future runs).*

### 2. Run in Headless Mode
Runs silently in the background without opening a visible browser window:
```bash
python pyq_fetch.py --headless
```

### 3. Fetch for a Single Subject
Fetch papers for only one subject from `config.yaml`:
```bash
python pyq_fetch.py --only "Machine Learning"
```

### 4. Override Degree / Course Filter
Download Diploma or M.Tech papers on the fly:
```bash
python pyq_fetch.py --course "Diploma"
python pyq_fetch.py --course "all"
```

### 5. Debug Mode
Saves screenshots and HTML dumps in `debug/` if an error occurs during scraping:
```bash
python pyq_fetch.py --debug
```

---

## CLI Options

| Flag | Default | Description |
|---|---|---|
| `--config` | `config.yaml` | Path to custom YAML configuration file. |
| `--only` | `None` | Restricts execution to a single subject name. |
| `--course` | From config | Target course/degree (`B.Tech`, `Diploma`, `M.Tech`, `Pharmacy`, `all`). |
| `--email` | From config | Knimbus login email for automated headless sign-in. |
| `--password` | From config | Knimbus login password for automated headless sign-in. |
| `--headless` | `False` | Runs Chromium in headless background mode. |
| `--debug` | `False` | Captures screenshots and page HTML when errors occur. |

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

