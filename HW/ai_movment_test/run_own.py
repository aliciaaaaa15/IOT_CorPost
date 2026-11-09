"""
run_own.py - Mismo pipeline con VUESTRAS grabaciones (Phyphox / Sensor Logger / placa).

Estructura esperada: una carpeta con un CSV por grabación, nombrado
    <clase>_<detalle>_<persona>_<nn>.csv      p. ej. sentado_recto_ana_01.csv
                                              andar_pasillo_luis_02.csv
La CLASE (primer token) decide la etiqueta (ver VALID / INVALID abajo).
La PERSONA (penúltimo token) es el grupo para la validación leave-one-person-out.

Cada CSV debe tener una columna de tiempo (s) y ejes de aceleración (x,y,z) y,
a poder ser, giroscopio (x,y,z). Se detectan por nombre de columna (ver find_cols).
Si hay m/s² se convierte a g automáticamente.

Uso:
    python run_own.py --data ./mis_grabaciones --out ./out_own
"""
import argparse, glob, os, re
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from har_common import (FS_TARGET, FEATURE_NAMES, make_windows, downsample,
                        ThresholdBaseline)
from run_hapt import metrics, loso, plot_cm, export_tree_to_c

# ---- DEFINID AQUÍ las clases ANTES de grabar y no las cambiéis después ----
VALID = {"sentado", "quieto", "depie"}
INVALID = {"andar", "levantarse", "sentarse", "estirar", "girar", "agacharse",
           "gesticular", "inclinarse", "moverse"}   # añadid los fronterizos que decidáis
TRIM_S = 6.0     # segundos recortados al inicio y al final (ponerse/quitarse el móvil)
PURITY = 1.0     # cada grabación tiene una sola etiqueta
FS_INTERNAL = 50  # se interpola a 50 Hz y luego se promedia a 10 Hz


def find_cols(df):
    """Devuelve (t, acc[3], gyro[3] o None) buscando por nombre de columna."""
    cols = list(df.columns)
    low = [c.lower() for c in cols]

    def pick(kind_regex, axis):
        for c, l in zip(cols, low):
            if re.search(kind_regex, l) and re.search(rf"(^|[^a-z]){axis}([^a-z]|$)", l):
                return c
        return None

    t = next((c for c, l in zip(cols, low)
              if re.search(r"time|seconds_elapsed|^t$", l)), None)
    # Sensor Logger: 'seconds_elapsed' (s) preferible a 'time' (ns)
    if "seconds_elapsed" in low:
        t = cols[low.index("seconds_elapsed")]
    acc = [pick(r"acc", a) for a in "xyz"]
    gyr = [pick(r"gyr|rot", a) for a in "xyz"]
    if t is None or None in acc:
        raise ValueError(f"No encuentro tiempo/aceleración en columnas: {cols}")
    return t, acc, (gyr if None not in gyr else None)


def load_recording(path):
    df = pd.read_csv(path).dropna()
    t_col, acc_cols, gyr_cols = find_cols(df)
    t = df[t_col].to_numpy(float)
    if t.max() > 1e6:           # nanosegundos o milisegundos -> s
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
            print(f"[aviso] clase desconocida '{cls}' en {name}; se ignora"); continue
        acc, gyr = load_recording(p)
        k = int(TRIM_S * FS_INTERNAL)
        acc, gyr = acc[k:-k], gyr[k:-k]
        a = downsample(acc, FS_INTERNAL, FS_TARGET)
        g = downsample(gyr, FS_INTERNAL, FS_TARGET)
        X, _ = make_windows(a, g, np.ones(len(a), dtype=int), purity=PURITY)
        if len(X) == 0:
            print(f"[aviso] {name}: demasiado corta"); continue
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
    print(f"Ventanas {len(y)} | quietas {(y==0).sum()} | movimiento {(y==1).sum()} | "
          f"personas {list(persons)}")
    if len(persons) < 3:
        print("[aviso] con <3 personas el leave-one-person-out es poco fiable.")

    pred_b = loso(X, y, groups, lambda: ThresholdBaseline(0))
    mb = metrics(y, pred_b)
    mk = lambda: DecisionTreeClassifier(max_depth=args.depth, class_weight="balanced",
                                        min_samples_leaf=5, random_state=0)
    pred_t = loso(X, y, groups, mk)
    mt = metrics(y, pred_t)
    for nm, m in (("BASELINE", mb), ("ÁRBOL", mt)):
        print(f"{nm:9s} acc {m['acc']:.3f} | mov. detectado {m['sens_mov']:.3f} | "
              f"quietas descartadas {m['quietas_descartadas']:.3f} | cm {m['cm'].tolist()}")

    # Errores concretos: qué grabaciones fallan más (con el árbol)
    print("\nGrabaciones con más errores (árbol):")
    err = pd.DataFrame({"rec": names_f, "err": pred_t != y}).groupby("rec").err.agg(["mean", "size"])
    print(err.sort_values("mean", ascending=False).head(10).to_string())

    final = mk().fit(X, y)
    print(f"\nNodos: {final.tree_.node_count} | hojas {final.get_n_leaves()} | "
          f"prof. {final.get_depth()}")
    for i in np.argsort(final.feature_importances_)[::-1][:4]:
        print(f"  {fnames[i]:<20}{final.feature_importances_[i]:.3f}")
    print(export_text(final, feature_names=fnames))
    plot_cm(mb["cm"], "Baseline", os.path.join(args.out, "confusion_baseline.png"))
    plot_cm(mt["cm"], "Árbol", os.path.join(args.out, "confusion_arbol.png"))
    export_tree_to_c(final, fnames, os.path.join(args.out, "decision_tree.h"))
    print(f"\nGuardado en {args.out}/")


if __name__ == "__main__":
    main()
