import os, requests

OUT_DIR = r"C:\Users\alien\nptel_material"
BASE = "https://media.dev.nptel.ac.in/content/mp4/110/104/110104169/MP4"

WEEK_MAP = {1:(1,3), 2:(4,7), 3:(8,11), 4:(12,15), 5:(16,19), 6:(20,23), 7:(24,26), 8:(27,28)}
def week_of(lec):
    for w, (a, b) in WEEK_MAP.items():
        if a <= lec <= b:
            return w

# lecture -> module number (from the site's actual mp4 filenames)
MISSING = {
    20: "mod05lec20",
    24: "mod07lec24",
    25: "mod07lec25",
    26: "mod07lec26",
}

for lec, modlec in MISSING.items():
    week = week_of(lec)
    tdir = os.path.join(OUT_DIR, f"Week_{week}", "transcript")
    os.makedirs(tdir, exist_ok=True)
    dest = os.path.join(tdir, f"Lecture_{lec:02d}.mp4")

    url = f"{BASE}/{modlec}.mp4"
    print(f"Lecture {lec}: downloading video (transcript unavailable)...")
    r = requests.get(url, stream=True)
    if r.ok:
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 256):
                if chunk:
                    f.write(chunk)
        print(f"Lecture {lec}: saved to {dest}")
    else:
        print(f"Lecture {lec}: FAILED ({r.status_code})")