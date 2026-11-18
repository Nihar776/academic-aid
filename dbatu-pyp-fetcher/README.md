# DBATU PYP Fetcher

An automated, intelligent bulk scraper, parser, and downloader for **Dr. Babasaheb Ambedkar Technological University (DBATU)** Previous Year Question Papers (PYPs / PYQs) from the official **Knimbus Digital Library Portal**.

It searches course materials, applies portal and content filters, extracts metadata directly from question paper PDFs, organizes them into semester-wise folders, and renames them following a clean, standardized naming format.

---

## 🤖 Generate Config Files with AI (Quick Start)

> [!TIP]
> **Zero Technical Knowledge Needed**: Copy and paste the prompt below into any AI assistant (**ChatGPT, Gemini, Claude**, etc.) along with your syllabus or subject details. The AI will generate a ready-to-use YAML configuration file and provide a complete, step-by-step walkthrough explaining how to use it.

### Copy-Paste LLM Prompt Template

````text
Act as an expert configuration assistant for the DBATU PYP Fetcher tool.
I want to create a configuration YAML file (secondary config or base config) to bulk-download Previous Year Question Papers (PYPs) from the Knimbus digital library portal for DBATU (Dr. Babasaheb Ambedkar Technological University).

Here are my details:
- Target Degree/Course: [e.g., B.Tech, Diploma, M.Tech (Default: B.Tech)]
- Branch / Department: [e.g., Computer Engineering, AIML, IT, Civil, Mechanical, etc.]
- Semester: [e.g., Semester 3, Semester 5]
- Subjects list or Syllabus snippet:
  [Paste your subject names, syllabus topics, or course codes here]
- Output Directory (Optional): [e.g., "J:/My Drive/SEM-03/AI PYPs" or leave blank for default ./PYPs/]
- Config Type Needed: [Secondary config (configs/<branch>_sem<X>.yaml) OR Base config (config.yaml)]

Please do the following:
1. GENERATE THE CONFIG YAML FILE:
   - Provide the complete, clean, syntax-valid YAML code block.
   - Use forward slashes (/) for folder paths (Windows/Linux safe).
   - Set the appropriate `branches` list matching DBATU branch naming conventions (e.g. "Computer Engineering", "Computer Science and Engineering", "Information Technology", "Artificial Intelligence and Machine Learning").
   - For each subject, structure:
     - `name`: Clean, full subject title.
     - `search`: Broad, effective Knimbus search query (lowercase, 1-3 words).
     - `keywords`: Key phrases that must be present in the paper title.
     - `exclude`: Any conflicting terms to exclude (e.g. avoid "advanced" or "cyber" if not applicable; use [] if none).
     - `sem`: Semester number as an integer.
     - `codes`: Specific DBATU course codes if known, or empty list `[]`.
     - `output_dir`: Include if a dedicated subject folder was requested.

2. EXPLAIN THE ENTIRE END-TO-END PROCESS FOR A BEGINNER:
   - File Placement: Exactly what filename to give it and which directory to save it in (e.g., save secondary configs under `configs/<name>.yaml`).
   - Run Commands: The exact terminal / PowerShell commands to run the scraper:
     * Full batch run: `python pyq_fetch.py -s configs/<file>.yaml`
     * Single subject run: `python pyq_fetch.py -s configs/<file>.yaml --only <subject_name_or_acronym>`
   - First-time Setup & Execution: What to expect when running (Chromium opening, auto-login with credentials or manual login, persistent session caching in `.browser-profile/`).
   - Output & Organization: Where files are saved, the standardized file naming format (`sem-year-season-R/S-Code.pdf`), and how deduplication (`manifest.json`) prevents re-downloading existing papers.
   - Troubleshooting: Quick tips if papers aren't found (adjusting keywords/search terms, checking since_year).
````

---

## Key Features

- **Automated Bulk Fetching**: Automatically searches and iterates through multi-page results on the Knimbus portal for any number of configured subjects.
- **Unified Multi-Filter Modal ("View All")**: Selects multiple filters across categories (Repository, Author, Department, Semester, etc.) simultaneously via the unified portal dialog in a single atomic operation, preserving search queries and parameters automatically.
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
  - **Deep PDF & Code Level**: Validates DBATU course code prefixes (accepts `BTCOC`, `BTCSE`, `BTCSD`, `BTIT`, `BTAIC` and NEP 2024 codes such as `25AFAIMD306A`, discarding unrelated branches like Robotics `BTARPE` or Electronics `BTECPC`).
- **Degree / Programme Filtering**: Supports B.Tech, Diploma, M.Tech, B. Pharmacy, and B. Architecture, or all courses without restrictions.
- **End-Semester Examination Focus**: Automatically detects and discards Mid-Semester Tests (CA/MSE) and Class Tests using dual-layer card and PDF text heuristics.
- **Resilient Storage Fallback**: Gracefully handles disconnected cloud or external storage paths (e.g. Google Drive), safely falling back to local storage without crashing.
- **Multi-Vector Download Engine**: Captures PDFs via direct link resolution, network response streams, browser download events, or embedded viewer iframes.
- **Deduplication & Incremental Downloads**: Computes SHA-256 hashes of paper contents and maintains a `manifest.json` so papers are never downloaded twice.
- **Persistent Browser Profile**: Keeps session cookies and authentication in `.browser-profile/`, avoiding repetitive logins.

---

## Directory Structure

```text
dbatu-pyp-fetcher/
├── config.yaml          # Base configuration (central URL, credentials, default output dir, filters)
├── configs/             # Branch / Course / Semester-specific subject configs
│   ├── ai_sem3.yaml     # AI Semester 3 (CE & CSE:AIML) subject and output config
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

## Configuration Architecture (OOP Inheritance Model)

The configuration engine follows an **Object-Oriented Programming (OOP) Inheritance Model**:

```text
Level 1: BASE config (Parent Defaults: config.yaml)
   │
   ▼
Level 2: SECONDARY config (Subclass Overrides: configs/*.yaml)
   │
   ▼
Level 3: SUBJECT level (Leaf Instance Overrides: subjects list in YAML)
```

**Priority Hierarchy**:
$$\text{Subject Level (Highest)} > \text{Secondary Config} > \text{Base Config (Lowest)}$$

---

### 1. Base Configuration (`config.yaml`)
Acts as the **parent class** providing global defaults:
- Default `output_dir: "./PYPs/"`
- Knimbus `base_url` and `credentials`
- Default `course: "B.Tech Question Paper"`
- `since_year: 2022`, sidebar `filters`, default `branches`, and `max_pages: 15`
- Optional `subjects: []` (common subjects across all branches, or left empty)

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

---

### 2. Secondary Subject Configurations (`configs/*.yaml`)
Acts as a **subclass** specializing configuration for a particular branch, course, or semester.
Any setting specified here automatically overrides the base defaults for this run.

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

### 3. Subject-Level Configuration (Atomic Leaf Overrides)
Every subject entry is treated as an individual object that can **atomically override any configuration parameter** for itself without affecting any other subject:

```yaml
subjects:
  - name: Specialized Distributed AI
    search: distributed ai
    keywords: ["distributed"]
    sem: 5
    # --- Atomic Subject Overrides ---
    output_dir: "D:/Dedicated_AI_Drive/"       # Dedicated storage folder for this subject
    branches: ["Artificial Intelligence and Machine Learning"] # Overrides branch whitelist
    course: "M.Tech Question Paper"            # Overrides degree target (e.g. elective)
    since_year: 2020                           # Overrides minimum exam year
    max_pages: 5                               # Overrides crawl depth
    filters:                                   # Overrides portal facets
      author: ["winter"]
```

#### Atomic Override Reference Table

| Parameter | Inherited From | Subject Override Syntax | Effect on That Subject |
|---|---|---|---|
| **`output_dir`** | Base or Secondary | `output_dir: "path"` or `address:` | Saves papers to a dedicated custom path instead of the parent folder. |
| **`branches`** | Base or Secondary | `branches: ["IT", "CSE"]` | Checks course code & PDF text against these specific branches only. |
| **`since_year`** | Base or Secondary | `since_year: 2020` | Accepts older or newer exams specifically for this subject. |
| **`course`** | Base or Secondary | `course: "M.Tech Question Paper"` | Scrapes M.Tech or Diploma papers even if parent run is B.Tech. |
| **`filters`** | Base or Secondary | `filters: { author: ["winter"] }` | Overrides portal sidebar filters (e.g. winter/summer/supplementary). |
| **`max_pages`** | Base or Secondary | `max_pages: 5` | Custom crawl pagination depth. |
| **`base_url`** | Base or Secondary | `base_url: "https://..."` | Custom Knimbus section URL. |

---

### 4. Subject Merging & Iteration Rules
When both the **Base** configuration (`config.yaml`) and a **Secondary** configuration (`configs/*.yaml`) define subjects:
1. **All subjects are iterated**: The scraper runs every subject from both files.
2. **Override & Inheritance**: If a subject with the same name exists in both files, the Secondary subject definition overrides and extends the Base subject (inheriting any unmentioned fields).
3. **Preservation**: Unique subjects from Base are preserved; unique subjects from Secondary are appended.

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

