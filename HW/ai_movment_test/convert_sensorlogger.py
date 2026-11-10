"""
convert_sensorlogger.py - Converts Sensor Logger exports (a zip with one CSV per
sensor) into a single CSV per recording that run_own.py understands, and checks its quality.

Usage:
    python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones

--src: folder with the exported .zip files (or with already unzipped folders).
       The zip NAME becomes the recording name, so rename it
       BEFORE converting:  sentado_recto_ana_01.zip
       If the app appends the date to the name (sentado_recto_ana_01-2026-10-08_21-26-20.zip)
       there is no need to remove it: the converter strips it automatically.

Output: <name>.csv with columns time_s, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
        (acc as delivered by the app: m/s² or g; run_own.py detects it and converts).
"""
import argparse, glob, io, os, re, zipfile
import numpy as np
import pandas as pd

# Date/time suffix added by the download: -2026-10-08_21-26-20 (and, if present, whatever follows,
# e.g. " (1)" added by a browser when a download is repeated).
DATE_SUFFIX = re.compile(r"[-_ ]*\d{4}-\d{2}-\d{2}[ _T-]\d{2}[-:.]\d{2}[-:.]\d{2}.*$")


def clean_name(raw):
    """sentado_recto_alicia_01-2026-10-08_21-26-20 -> sentado_recto_alicia_01"""
    return DATE_SUFFIX.sub("", raw).strip()


def _read_sensor(files, keywords, exclude=("uncal", "raw")):
    """Look in files (dict lowercase_name -> bytes/path) for the sensor CSV."""
    for name, src in files.items():
        base = os.path.basename(name)
        if not base.endswith(".csv"):
            continue
        if any(k in base for k in keywords) and not any(e in base for e in exclude):
            return pd.read_csv(src), base
    return None, None


def _axis_cols(df):
    low = {c.lower(): c for c in df.columns}
    t = low.get("seconds_elapsed")
    if t is None:
        raise ValueError(f"No seconds_elapsed column. Columns: {list(df.columns)}")
    return t, [low[a] for a in "xyz"]


def convert_one(src_path, out_dir):
    """Convert one export and return the clean recording name (or None on failure)."""
    raw_name = os.path.splitext(os.path.basename(src_path.rstrip("/\\")))[0]
    name = clean_name(raw_name)
    files = {}
    if os.path.isdir(src_path):
        for p in glob.glob(os.path.join(src_path, "**", "*"), recursive=True):
            files[p.lower()] = p
    else:
        z = zipfile.ZipFile(src_path)
        for n in z.namelist():
            files[n.lower()] = io.BytesIO(z.read(n))

    acc, acc_name = _read_sensor(files, ["totalacceleration"])
    gyr, gyr_name = _read_sensor(files, ["gyroscope"])
    if acc is None:
        print(f"[ERROR] {raw_name}: TotalAcceleration.csv not found. Files: "
              f"{[os.path.basename(k) for k in files][:15]}")
        return None
    ta, ca = _axis_cols(acc)
    t = acc[ta].to_numpy(float)
    A = acc[ca].to_numpy(float)

    if gyr is not None:
        tg, cg = _axis_cols(gyr)
        tgv = gyr[tg].to_numpy(float)
        G = np.column_stack([np.interp(t, tgv, gyr[c].to_numpy(float)) for c in cg])
    else:
        G = np.zeros_like(A)
        print(f"[WARNING] {name}: no gyroscope; the gyroscope features will be 0")

    out = pd.DataFrame(np.column_stack([t, A, G]),
                       columns=["time_s", "acc_x", "acc_y", "acc_z",
                                "gyro_x", "gyro_y", "gyro_z"])
    os.makedirs(out_dir, exist_ok=True)
    out.to_csv(os.path.join(out_dir, name + ".csv"), index=False)

    # ---- Quality checks ----
    dt = np.diff(t)
    fs = 1 / np.median(dt)
    dur = t[-1] - t[0]
    mag = np.linalg.norm(A, axis=1)
    unit = "m/s²" if np.median(mag) > 3 else "g"
    mag_g = mag / 9.80665 if unit == "m/s²" else mag
    msgs = []
    if fs < 40: msgs.append(f"low sampling rate ({fs:.0f} Hz): raise the rate in the app")
    if (dt > 0.1).sum() > 0: msgs.append(f"{(dt > 0.1).sum()} gaps > 0.1 s in the data")
    if np.median(mag_g) < 0.5: msgs.append("the magnitude at rest is not ~1 g: the sensor does NOT include "
                                           "gravity (use the sensor with gravity / total acceleration)")
    if dur < 60: msgs.append(f"short recording ({dur:.0f} s)")
    status = "OK " if not msgs else "REVIEW"
    print(f"[{status}] {name}: {dur:5.0f} s | {fs:5.1f} Hz | acc in {unit} "
          f"(|a| median {np.median(mag_g):.2f} g) | gyro {'yes' if gyr is not None else 'NO'}"
          + ("" if not msgs else " | " + "; ".join(msgs)))
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="./mis_grabaciones")
    a = ap.parse_args()
    items = sorted(glob.glob(os.path.join(a.src, "*.zip")) +
                   [d for d in glob.glob(os.path.join(a.src, "*")) if os.path.isdir(d)])
    if not items:
        print("No .zip files or folders found in", a.src); return
    seen = {}   # clean name -> original export that produced it
    for it in items:
        raw = os.path.splitext(os.path.basename(it.rstrip("/\\")))[0]
        # If two exports give the same clean name (the same recording was made twice),
        # the last one (the most recent date, in alphabetical order) overwrites the previous one.
        clean = clean_name(raw)
        if clean in seen:
            print(f"[WARNING] '{raw}' and '{seen[clean]}' give the same name '{clean}': "
                  f"the last one is kept. Rename one of them to keep both.")
        try:
            if convert_one(it, a.out):
                seen[clean] = raw
        except Exception as e:
            print(f"[ERROR] {it}: {e}")


if __name__ == "__main__":
    main()