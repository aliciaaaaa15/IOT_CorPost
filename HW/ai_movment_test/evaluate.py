"""
evaluate.py - Evalúa cuán exactos son los árboles (y el umbral) sobre VUESTRAS grabaciones.

Qué hace
--------
1. Lee los CSV de `mis_grabaciones/` (mismo formato y mismo preprocesado que run_own.py:
   recorte, 10 Hz, ventanas de 2 s con 50 % de solape).
2. Carga cada `decision_tree.h` y lo ejecuta tal cual (parsea el if/else de C, con
   comparaciones en float32 como en el micro). Así evaluáis EXACTAMENTE lo que irá al firmware.
3. Calcula matriz de confusión, movimiento detectado, quietas descartadas, intervalos de
   confianza (bootstrap por grabación), resultado por persona, por tipo de actividad y
   las grabaciones que más fallan.
4. Si hay >= 3 personas, añade dos modelos "honestos" entrenados con vuestros datos y
   evaluados con leave-one-person-out: umbral propio y árbol propio.

Modelos "externos" vs "en muestra"
----------------------------------
  --models          árboles que NO han visto vuestros datos (p. ej. los entrenados con HAPT).
                    La evaluación es una prueba real de generalización.
  --in-sample-models árboles entrenados con vuestros propios datos (p. ej. out_own/decision_tree.h).
                    Su resultado es OPTIMISTA (han visto estos datos); se marca así en el informe.
                    Para una cifra honesta de "entrenar con mis datos" mirad la fila LOPO.

Uso
---
  python evaluate.py --data ./mis_grabaciones \
      --models out/decision_tree.h out_orientation_free/decision_tree.h \
      --in-sample-models out_own/decision_tree.h --out ./out_eval
"""
import argparse, glob, os, re
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from har_common import FEATURE_NAMES, make_windows, downsample, ThresholdBaseline
from run_own import VALID, INVALID, TRIM_S, PURITY, FS_INTERNAL, load_recording
from run_hapt import metrics, loso

FS_T = 10
AXIS_FEATURES = {"acc_x_std", "acc_y_std", "acc_z_std", "acc_max_axis_range"}


# ------------------------------------------------------------------ datos
def build_windows(data_dir):
    X, y, person, rec, tipo = [], [], [], [], []
    for p in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        name = os.path.splitext(os.path.basename(p))[0]
        toks = name.lower().split("_")
        cls = toks[0]
        if cls in VALID:
            lab = 0
        elif cls in INVALID:
            lab = 1
        else:
            print(f"[aviso] clase desconocida '{cls}' en {name}; se ignora")
            continue
        acc, gyr = load_recording(p)
        k = int(TRIM_S * FS_INTERNAL)
        acc, gyr = acc[k:-k], gyr[k:-k]
        a = downsample(acc, FS_INTERNAL, FS_T)
        g = downsample(gyr, FS_INTERNAL, FS_T)
        Xw, _ = make_windows(a, g, np.ones(len(a), dtype=int), purity=PURITY)
        if len(Xw) == 0:
            print(f"[aviso] {name}: demasiado corta, se ignora")
            continue
        n = len(Xw)
        X.append(Xw)
        y.append(np.full(n, lab))
        person.append(np.full(n, toks[-2] if len(toks) >= 3 else "x"))
        rec.append(np.full(n, name))
        tipo.append(np.full(n, "_".join(toks[:-2]) if len(toks) >= 3 else cls))
    if not X:
        raise SystemExit(f"No hay grabaciones válidas en {data_dir}")
    return (np.vstack(X), np.concatenate(y), np.concatenate(person),
            np.concatenate(rec), np.concatenate(tipo))


# ------------------------------------------------------------------ árbol en C
class CTree:
    """Ejecuta en Python un decision_tree.h generado por export_tree_to_c()."""

    def __init__(self, path):
        txt = open(path, encoding="utf-8").read()
        names = {int(i): n for i, n in re.findall(r"f\[(\d+)\]\s*=\s*(\w+)", txt)}
        if not names:
            raise ValueError(f"{path}: no encuentro el listado 'f[i] = nombre' en los comentarios")
        self.col = {}
        for i, n in names.items():
            if n not in FEATURE_NAMES:
                raise ValueError(f"{path}: característica desconocida '{n}'")
            self.col[i] = FEATURE_NAMES.index(n)
        body = txt[txt.index("{", txt.index("static inline int")) + 1:]
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        self.root, pos = self._parse(lines, 0)
        self.path = path
        self.n_nodes = self._count(self.root)
        self.features = sorted({names[f] for f in self._used(self.root)})

    def _parse(self, lines, pos):
        ln = lines[pos]
        m = re.match(r"return\s+(\d+);", ln)
        if m:
            return ("leaf", int(m.group(1))), pos + 1
        m = re.match(r"if \(f\[(\d+)\]\s*<=\s*([-+0-9.eE]+)f?\)\s*\{", ln)
        if not m:
            raise ValueError(f"Línea no reconocida en el árbol: {ln}")
        left, pos = self._parse(lines, pos + 1)
        if lines[pos] != "} else {":
            raise ValueError("Se esperaba '} else {'")
        right, pos = self._parse(lines, pos + 1)
        if lines[pos] != "}":
            raise ValueError("Se esperaba '}'")
        return ("node", int(m.group(1)), float(m.group(2)), left, right), pos + 1

    def _count(self, n):
        return 1 if n[0] == "leaf" else 1 + self._count(n[3]) + self._count(n[4])

    def _used(self, n):
        return [] if n[0] == "leaf" else [n[1]] + self._used(n[3]) + self._used(n[4])

    def predict(self, X):
        Xf = X.astype(np.float32)
        out = np.zeros(len(X), dtype=int)

        def rec(node, idx):
            if len(idx) == 0:
                return
            if node[0] == "leaf":
                out[idx] = node[1]
                return
            _, fi, thr, l, r = node
            left = Xf[idx, self.col[fi]] <= np.float32(thr)
            rec(l, idx[left])
            rec(r, idx[~left])

        rec(self.root, np.arange(len(X)))
        return out


class FixedThreshold:
    def __init__(self, thr):
        self.thr = thr

    def predict(self, X):
        return (X[:, FEATURE_NAMES.index("acc_mag_std")].astype(np.float32)
                > np.float32(self.thr)).astype(int)


# ------------------------------------------------------------------ métricas
def bootstrap_ci(y, pred, rec, B=1000, seed=0):
    """IC 95 % remuestreando GRABACIONES (las ventanas de una grabación no son independientes)."""
    df = pd.DataFrame({"rec": rec, "tp": (y == 1) & (pred == 1), "fn": (y == 1) & (pred == 0),
                       "tn": (y == 0) & (pred == 0), "fp": (y == 0) & (pred == 1)})
    c = df.groupby("rec")[["tp", "fn", "tn", "fp"]].sum().to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(c), (B, len(c)))
    s = c[idx].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sens = s[:, 0] / (s[:, 0] + s[:, 1])
        disc = s[:, 3] / (s[:, 2] + s[:, 3])
    f = lambda v: (np.nanpercentile(v, 2.5), np.nanpercentile(v, 97.5))
    return f(sens), f(disc)


def per_group(y, pred, groups):
    rows = []
    for g in np.unique(groups):
        k = groups == g
        m = metrics(y[k], pred[k])
        rows.append((g, int(k.sum()), int((y[k] == 1).sum()), int((y[k] == 0).sum()),
                     m["sens_mov"] if (y[k] == 1).any() else np.nan,
                     m["quietas_descartadas"] if (y[k] == 0).any() else np.nan,
                     float((pred[k] != y[k]).mean())))
    return pd.DataFrame(rows, columns=["grupo", "ventanas", "n_mov", "n_quieto",
                                       "mov_detectado", "quietas_descartadas", "error"])


def plot_cms(results, path):
    n = len(results)
    cols = min(n, 3)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 3.4 * rows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, r in zip(axes.ravel(), results):
        ax.axis("on")
        cm = r["m"]["cm"]
        ax.imshow(cm, cmap="Blues")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["válida", "no válida"], fontsize=8)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["quieto", "movim."], fontsize=8)
        ax.set_title(r["label"][:34] + ("\n(en muestra)" if r["in_sample"] else ""), fontsize=8)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./mis_grabaciones")
    ap.add_argument("--models", nargs="*", default=None,
                    help="decision_tree.h que NO han visto vuestros datos")
    ap.add_argument("--in-sample-models", nargs="*", default=[],
                    help="decision_tree.h entrenados con estos mismos datos (resultado optimista)")
    ap.add_argument("--hapt-threshold", type=float, default=0.0424,
                    help="umbral de acc_mag_std (g) aprendido con HAPT; '' para omitir con 0")
    ap.add_argument("--depth", type=int, default=3, help="profundidad del árbol propio (LOPO)")
    ap.add_argument("--orientation-free", action="store_true",
                    help="el árbol propio LOPO no usa características por eje")
    ap.add_argument("--out", default="./out_eval")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    if a.models is None:
        a.models = [p for p in ("out/decision_tree.h", "out_orientation_free/decision_tree.h")
                    if os.path.exists(p)]
    log = open(os.path.join(a.out, "informe.txt"), "w", encoding="utf-8")

    def P(*x):
        s = " ".join(str(v) for v in x)
        print(s)
        log.write(s + "\n")

    X, y, person, rec, tipo = build_windows(a.data)
    persons = np.unique(person)
    P(f"Datos: {len(y)} ventanas | {len(np.unique(rec))} grabaciones | personas: {list(persons)}")
    P(f"  quietas (válida): {(y == 0).sum()} | movimiento (no válida): {(y == 1).sum()}")
    P("  ventanas por tipo:", dict(pd.Series(tipo).value_counts()))
    if len(persons) < 3:
        P("[aviso] con <3 personas no se calculan los modelos LOPO y las cifras son poco fiables.")

    # ---- reunir predicciones de cada modelo
    results = []

    def add(label, pred, in_sample=False, note=""):
        m = metrics(y, pred)
        ci_s, ci_d = bootstrap_ci(y, pred, rec)
        results.append(dict(label=label, pred=pred, m=m, ci_s=ci_s, ci_d=ci_d,
                            in_sample=in_sample, note=note))

    if a.hapt_threshold:
        add(f"Umbral HAPT ({a.hapt_threshold:g} g)", FixedThreshold(a.hapt_threshold).predict(X),
            note="umbral fijo en acc_mag_std, aprendido con HAPT")
    for path, ins in [(p, False) for p in a.models] + [(p, True) for p in a.in_sample_models]:
        try:
            t = CTree(path)
        except Exception as e:
            P(f"[ERROR] {path}: {e}")
            continue
        lab = os.path.basename(os.path.dirname(os.path.abspath(path))) or path
        add(f"Árbol {lab}", t.predict(X), in_sample=ins,
            note=f"{t.n_nodes} nodos, usa: {', '.join(t.features)}")
    if len(persons) >= 3:
        add("Umbral propio (LOPO)", loso(X, y, person, lambda: ThresholdBaseline(0)),
            note="umbral reentrenado dejando una persona fuera")
        cols = [i for i, n in enumerate(FEATURE_NAMES)
                if not (a.orientation_free and n in AXIS_FEATURES)]
        Xs = X[:, cols]
        mk = lambda: DecisionTreeClassifier(max_depth=a.depth, class_weight="balanced",
                                            min_samples_leaf=5, random_state=0)
        add(f"Árbol propio (LOPO, prof. {a.depth}{', sin ejes' if a.orientation_free else ''})",
            loso(Xs, y, person, mk),
            note="árbol reentrenado dejando una persona fuera: la cifra honesta de 'entrenar con mis datos'")

    # ---- informe por modelo
    P("\n" + "=" * 78 + "\nRESUMEN (criterios: mov. detectado >= 90 %, quietas descartadas <= 10 %)\n" + "=" * 78)
    P(f"{'modelo':<44}{'mov.detect.':>12}{'IC95%':>14}{'descart.':>10}{'IC95%':>14}  veredicto")
    for r in results:
        m = r["m"]
        ok = m["sens_mov"] >= 0.90 and m["quietas_descartadas"] <= 0.10
        tag = ("*" if r["in_sample"] else " ")
        P(f"{(r['label'] + tag):<44}{m['sens_mov']:>12.3f}"
          f"{'[%.2f,%.2f]' % r['ci_s']:>14}{m['quietas_descartadas']:>10.3f}"
          f"{'[%.2f,%.2f]' % r['ci_d']:>14}  {'CUMPLE' if ok else 'NO CUMPLE'}")
    P("  * = entrenado con estos mismos datos: cifra optimista, no usar para decidir.")
    P("  IC95 %: bootstrap remuestreando grabaciones (es más fiable que remuestrear ventanas).")

    for r in results:
        m, pred = r["m"], r["pred"]
        P("\n" + "-" * 78 + f"\n{r['label']}" + ("  [EN MUESTRA, optimista]" if r["in_sample"] else ""))
        P("  " + r["note"])
        tn, fp, fn, tp = m["cm"].ravel()
        P(f"  matriz  quieto->válida {tn} | quieto->no válida {fp} | "
          f"movimiento->válida {fn} (¡grave!) | movimiento->no válida {tp}")
        P(f"  exactitud {m['acc']:.3f} | movimiento detectado {m['sens_mov']:.3f} | "
          f"quietas descartadas {m['quietas_descartadas']:.3f}")
        pp = per_group(y, pred, person)
        P("  por persona:")
        for _, row in pp.iterrows():
            P(f"    {row.grupo:<12} mov. detectado {row.mov_detectado:.3f} | "
              f"quietas descartadas {row.quietas_descartadas:.3f} | error {row.error:.3f}")
        rr = per_group(y, pred, rec).sort_values("error", ascending=False)
        worst = rr[rr.error > 0].head(5)
        if len(worst):
            P("  grabaciones con más errores:")
            for _, row in worst.iterrows():
                P(f"    {row.grupo:<40} error {row.error:.2f} ({row.ventanas} ventanas)")
        else:
            P("  ninguna grabación con errores")

    # ---- tabla por tipo
    P("\n" + "=" * 78 + "\nERROR POR TIPO DE ACTIVIDAD (fracción de ventanas mal clasificadas)\n" + "=" * 78)
    tab = pd.DataFrame({"n": pd.Series(tipo).value_counts()})
    tab["clase"] = ["movimiento" if y[tipo == t][0] == 1 else "quieto" for t in tab.index]
    for i, r in enumerate(results):
        tab[f"M{i + 1}"] = [float((r["pred"][tipo == t] != y[tipo == t]).mean()) for t in tab.index]
    tab = tab.sort_values([c for c in tab.columns if c.startswith("M")][-1], ascending=False)
    for i, r in enumerate(results):
        P(f"  M{i + 1} = {r['label']}{' *' if r['in_sample'] else ''}")
    P(tab.to_string(float_format=lambda v: f"{v:.2f}"))

    # ---- archivos
    plot_cms(results, os.path.join(a.out, "confusion_matrices.png"))
    df = pd.DataFrame({"grabacion": rec, "persona": person, "tipo": tipo, "real_movimiento": y})
    for i, r in enumerate(results):
        df[f"M{i + 1}"] = r["pred"]
    df.to_csv(os.path.join(a.out, "predicciones_por_ventana.csv"), index=False)
    tab.to_csv(os.path.join(a.out, "error_por_tipo.csv"))
    P(f"\nGuardado en {a.out}/: informe.txt, confusion_matrices.png, "
      "predicciones_por_ventana.csv, error_por_tipo.csv")
    log.close()


if __name__ == "__main__":
    main()
