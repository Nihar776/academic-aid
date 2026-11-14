import os, shutil


BASE_DIR = r"C:\Users\alien\nptel_course"
ASSIGN_DIR = os.path.join(BASE_DIR, "Assignments")
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "Transcripts")

os.makedirs(ASSIGN_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

copied_assign = 0
copied_transcript = 0
skipped = []

for week in range(1, 9):
    week_dir = os.path.join(BASE_DIR, f"Week_{week}")
    if not os.path.isdir(week_dir):
        skipped.append(f"Week_{week} folder missing")
        continue

    # --- Assignments ---
    for fname in os.listdir(week_dir):
        fpath = os.path.join(week_dir, fname)
        if os.path.isfile(fpath) and "assignment" in fname.lower():
            dest = os.path.join(ASSIGN_DIR, fname)
            if os.path.exists(dest):
                print(f"WARNING: {fname} already exists in Assignments, overwriting")
            shutil.copy2(fpath, dest)
            copied_assign += 1

    # --- Transcripts (any file type: pdf, txt, mp4, etc.) ---
    transcript_src = os.path.join(week_dir, "transcript")
    if os.path.isdir(transcript_src):
        for fname in os.listdir(transcript_src):
            fpath = os.path.join(transcript_src, fname)
            if os.path.isfile(fpath):
                dest = os.path.join(TRANSCRIPT_DIR, fname)
                if os.path.exists(dest):
                    print(f"WARNING: {fname} already exists in Transcripts, overwriting")
                shutil.copy2(fpath, dest)
                copied_transcript += 1
    else:
        skipped.append(f"Week_{week}: no transcript folder found")

print(f"\nDone. Copied {copied_assign} assignment file(s), {copied_transcript} transcript file(s).")
if skipped:
    print("Notes:")
    for s in skipped:
        print(f"  - {s}")