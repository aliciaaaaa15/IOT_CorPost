"""
run_own.py - Same pipeline with our OWN recordings (Phyphox / Sensor Logger / board).

Expected structure: a folder with one CSV per recording, named
    <class>_<detail>_<person>_<nn>.csv        e.g. sentado_recto_ana_01.csv
                                              andar_pasillo_luis_02.csv
The CLASS (first token) decides the label (see VALID / INVALID below).
The PERSON (second-to-last token) is the group for leave-one-person-out validation.

Each CSV must have a time column (s) and acceleration axes (x,y,z) and,
preferably, gyroscope (x,y,z). They are detected by column name (see find_cols).
If the data is in m/s² it is converted to g automatically.

Usage:
    python run_own.py --data ./mis_grabaciones --out ./out_own
"""
import argparse, glob, os, re
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from har_common import (FS_TARGET, FEATURE_NAMES, make_windows, downsample,
                        ThresholdBaseline)
from run_hapt import metrics, loso, plot_cm, export_tree_to_c

# ---- DEFINE the classes HERE BEFORE recording and do not change them afterwards ----
# (the class names are the Spanish file-name prefixes of the recordings)
VALID = {"sentado", "quieto", "depie"}
INVALID = {"andar", "levantarse", "sentarse", "estirar", "girar", "agacharse",
           "gesticular", "inclinarse", "moverse"}   # add any borderline classes that are decided on
TRIM_S = 6.0     # seconds trimmed at the start and at the end (putting on / taking off the phone)
PURITY = 1.0     # each recording has a single label
FS_INTERNAL = 50  # interpolated to 50 Hz and then averaged down to 10 Hz


def find_cols(df):
    """Return (t, acc[3], gyro[3] or None), searching by column name."""
    cols = list(df.columns)
    low = [c.lower() for c in cols]

    def pick(kind_regex, axis):
        for c, l in zip(cols, low):
            if re.search(kind_regex, l) and re.search(rf"(^|[^a-z]){axis}([^a-z]|$)", l):
                return c
        return None

    t = next((c for c, l in zip(cols, low)
              if re.search(r"time|seconds_elapsed|^t$", l)), None)
    # Sensor Logger: 'seconds_elapsed' (s) is preferable to 'time' (ns)
    if "seconds_elapsed" in low:
        t = cols[low.index("seconds_elapsed")]
    acc = [pick(r"acc", a) for a in "xyz"]
    gyr = [pick(r"gyr|rot", a) for a in "xyz"]
    if t is None or None in acc:
        raise ValueError(f"Cannot find time/acceleration in columns: {cols}")
    return t, acc, (gyr if None not in gyr else None)


def load_recording(path):
    df = pd.read_csv(path).dropna()
    t_col, acc_cols, gyr_cols = find_cols(df)
    t = df[t_col].to_numpy(float)
    if t.max() > 1e6:           # nanoseconds or milliseconds -> s
        t = t / (1e9 if t.max() > 1e12 else 1e3)
    t = t - t[0]
    grid = np.arange(0, t[-1], 1 / FS_INTERNAL)
    interp = lambda cols: np.column_stack([np.interp(grid, t, df[c].to_numpy(float))
                                           for c in cols])
    acc = interp(acc_cols)
    if np.median(np.linalg.norm(acc, axis=1)) > 3:     # m/s² -> g
        acc = acc / 9.80665
    gyr = interp(gyr_cols) if gyr_cols else np.zeros_like(acc)
    return acc, gyr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="./out_own")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--orientation-free", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    Xs, ys, gs, names_f = [], [], [], []
    for p in sorted(glob.glob(os.path.join(args.data, "*.csv"))):
        name = os.path.splitext(os.path.basename(p))[0]
        toks = name.lower().split("_")
        cls, person = toks[0], toks[-2] if len(toks) >= 3 else "x"
        if cls in VALID:   label = 0
        elif cls in INVALID: label = 1
        else:
            print(f"[warning] unknown class '{cls}' in {name}; ignored"); continue
        acc, gyr = load_recording(p)
        k = int(TRIM_S * FS_INTERNAL)
        acc, gyr = acc[k:-k], gyr[k:-k]
        a = downsample(acc, FS_INTERNAL, FS_TARGET)
        g = downsample(gyr, FS_INTERNAL, FS_TARGET)
        X, _ = make_windows(a, g, np.ones(len(a), dtype=int), purity=PURITY)
        if len(X) == 0:
            print(f"[warning] {name}: too short"); continue
        Xs.append(X); ys.append(np.full(len(X), label)); gs.append(np.array([person] * len(X)))
        names_f.append(np.array([name] * len(X)))
    X = np.vstack(Xs); y = np.concatenate(ys); groups = np.concatenate(gs)
    names_f = np.concatenate(names_f)

    fnames = list(FEATURE_NAMES)
    if args.orientation_free:
        drop = {"acc_x_std", "acc_y_std", "acc_z_std", "acc_max_axis_range"}
        keep = [i for i, n in enumerate(fnames) if n not in drop]
        X = X[:, keep]; fnames = [fnames[i] for i in keep]

    persons = np.unique(groups)
    print(f"Windows {len(y)} | still {(y==0).sum()} | motion {(y==1).sum()} | "
          f"people {list(persons)}")
    if len(persons) < 3:
        print("[warning] with <3 people the leave-one-person-out is unreliable.")

    pred_b = loso(X, y, groups, lambda: ThresholdBaseline(0))
    mb = metrics(y, pred_b)
    mk = lambda: DecisionTreeClassifier(max_depth=args.depth, class_weight="balanced",
                                        min_samples_leaf=5, random_state=0)
    pred_t = loso(X, y, groups, mk)
    mt = metrics(y, pred_t)
    for nm, m in (("BASELINE", mb), ("TREE", mt)):
        print(f"{nm:9s} acc {m['acc']:.3f} | motion detected {m['sens_mov']:.3f} | "
              f"still discarded {m['quietas_descartadas']:.3f} | cm {m['cm'].tolist()}")

    # Specific errors: which recordings fail the most (with the tree)
    print("\nRecordings with the most errors (tree):")
    err = pd.DataFrame({"rec": names_f, "err": pred_t != y}).groupby("rec").err.agg(["mean", "size"])
    print(err.sort_values("mean", ascending=False).head(10).to_string())

    final = mk().fit(X, y)
    print(f"\nNodes: {final.tree_.node_count} | leaves {final.get_n_leaves()} | "
          f"depth {final.get_depth()}")
    for i in np.argsort(final.feature_importances_)[::-1][:4]:
        print(f"  {fnames[i]:<20}{final.feature_importances_[i]:.3f}")
    print(export_text(final, feature_names=fnames))
    plot_cm(mb["cm"], "Baseline", os.path.join(args.out, "confusion_baseline.png"))
    plot_cm(mt["cm"], "Tree", os.path.join(args.out, "confusion_arbol.png"))
    export_tree_to_c(final, fnames, os.path.join(args.out, "decision_tree.h"))
    print(f"\nSaved to {args.out}/")


if __name__ == "__main__":
    main()
