import asyncio, os, re, requests
from playwright.async_api import async_playwright

COURSE_URL = "https://nptel.ac.in/courses/110104169"
COURSE_CODE = "noc23_mg119"
SUBJECT_ID = "110104169"
OUT_DIR = "nptel_course"

WEEK_MAP = {1:(1,3), 2:(4,7), 3:(8,11), 4:(12,15), 5:(16,19), 6:(20,23), 7:(24,26), 8:(27,28)}

def week_of(lec):
    for w, (a, b) in WEEK_MAP.items():
        if a <= lec <= b:
            return w

def download_assignments():
    base = f"https://archive.nptel.ac.in/content/storage2/courses/downloads_new/{SUBJECT_ID}"
    for week in range(1, 9):
        week_dir = os.path.join(OUT_DIR, f"Week_{week}")
        os.makedirs(week_dir, exist_ok=True)
        url = f"{base}/{COURSE_CODE}_assignment_Week_{week}.png"
        r = requests.get(url)
        if r.ok:
            with open(os.path.join(week_dir, f"assignment_Week_{week}.png"), "wb") as f:
                f.write(r.content)
            print(f"[Assignment] Week {week}: saved")
        else:
            print(f"[Assignment] Week {week}: FAILED ({r.status_code})")

def drive_id_from_url(url):
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None

def download_drive_pdf(file_id, dest_path):
    session = requests.Session()
    url = "https://drive.google.com/uc?export=download"
    r = session.get(url, params={"id": file_id}, stream=True)
    token = None
    for k, v in r.cookies.items():
        if k.startswith("download_warning"):
            token = v
    if token:
        r = session.get(url, params={"id": file_id, "confirm": token}, stream=True)
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(32768):
            if chunk:
                f.write(chunk)

async def scrape_transcripts():
    links = {}
    failed = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(COURSE_URL, wait_until="networkidle")

        print("\n>>> Browser is open. Manually click: Downloads tab -> expand Transcripts section.")
        print(">>> Once you can see 'Lecture 01' in the table, come back here and press Enter.\n")
        input("Press Enter once Transcripts table is visible...")

        section = page.locator(
            "xpath=//div[contains(@class,'assignments') and contains(@class,'download-type')]"
            "[.//h3[normalize-space(text())='Transcripts']]"
        ).first

        for lec in range(1, 29):
            label = f"Lecture {lec:02d}"
            try:
                row = section.locator(
                    f"xpath=.//div[contains(@class,'d-data')]"
                    f"[.//span[contains(@class,'c-name')][normalize-space(text())='{label}']]"
                ).first

                await row.scroll_into_view_if_needed(timeout=5000)
                await page.wait_for_timeout(150)

                option_count = await row.locator("ul.pseudo-options li").count()
                if option_count == 0:
                    raise Exception("no English-Verified option (transcript not available)")

                current_text = await row.locator(".pseudo-input").inner_text()
                if "verified" not in current_text.lower():
                    await row.locator(".pseudo-input").click(timeout=3000)
                    await page.wait_for_timeout(300)
                    await row.locator("ul.pseudo-options li").first.click(timeout=3000)
                    await page.wait_for_timeout(400)

                href = await row.evaluate("""(row) => {
                    const btn = Array.from(row.querySelectorAll('button'))
                        .find(b => b.textContent.trim() === 'Transcripts');
                    const a = btn ? btn.closest('a') : null;
                    return a ? a.getAttribute('href') : null;
                }""")

                if not href:
                    raise Exception("href still empty after selecting language")

                links[lec] = href
                print(f"Lecture {lec} (Week {week_of(lec)}): {href}")

            except Exception as e:
                print(f"Lecture {lec}: SKIPPED ({type(e).__name__}: {e})")
                failed.append(lec)
                continue

        await browser.close()

    if failed:
        print(f"\n{len(failed)} lecture(s) had no usable transcript link: {failed}")

    return links

async def main():
    download_assignments()
    links = await scrape_transcripts()

    for lec, url in links.items():
        file_id = drive_id_from_url(url)
        if not file_id:
            print(f"Lecture {lec}: couldn't parse Drive ID from {url}")
            continue
        week = week_of(lec)
        tdir = os.path.join(OUT_DIR, f"Week_{week}", "transcript")
        os.makedirs(tdir, exist_ok=True)
        dest = os.path.join(tdir, f"Lecture_{lec:02d}.pdf")
        download_drive_pdf(file_id, dest)
        print(f"[Transcript] Lecture {lec}: saved to {dest}")

asyncio.run(main())