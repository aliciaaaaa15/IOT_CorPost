"""
run_hapt.py - Pipeline completo sobre el dataset HAPT.

Uso:
    python run_hapt.py --data ./hapt            # carpeta con RawData/ dentro
Salidas (en ./out):
    dataset_windows.npz, resultados.txt, confusion_*.png, arbol.png,
    importancias.png, decision_tree.h
"""
import argparse, os
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import LeaveOneGroupOut
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from har_common import (FS_TARGET, FEATURE_NAMES, downsample, downsample_labels,
                        make_windows, ThresholdBaseline)

ACT = {1: "andar", 2: "subir_escaleras", 3: "bajar_escaleras", 4: "sentado",
       5: "de_pie", 6: "tumbado", 7: "de_pie->sentado", 8: "sentado->de_pie",
       9: "sentado->tumbado", 10: "tumbado->sentado", 11: "de_pie->tumbado",
       12: "tumbado->de_pie"}

# ---- Decisión de etiquetado (fijadla antes y no la cambiéis a posteriori) ----
VALID_ACTS = {4, 5}                 # sentado, de pie quieto
DROP_ACTS = {6, 9, 10, 11, 12}      # tumbado y transiciones que implican tumbarse:
                                    # no ocurren con un usuario sentado en su mesa
# Movimiento (no válida): 1,2,3 (andar), 7 (de pie->sentado), 8 (sentado->de pie)
FS_RAW = 50
PURITY = 0.8
TRIM_S = 1.0   # segundos que se recortan al inicio/fin de cada segmento etiquetado
               # (el etiquetado por vídeo es impreciso en los bordes)


def build_dataset(root):
    lab_df = pd.read_csv(os.path.join(root, "RawData", "labels.txt"),
                         sep=r"\s+", header=None, names=["exp", "user", "act", "s", "e"])
    Xs, ys, gs, es = [], [], [], []
    for (exp, user), seg in lab_df.groupby(["exp", "user"]):
        f_acc = os.path.join(root, "RawData", f"acc_exp{exp:02d}_user{user:02d}.txt")
        f_gyr = os.path.join(root, "RawData", f"gyro_exp{exp:02d}_user{user:02d}.txt")
        acc = np.loadtxt(f_acc)       # en g, incluye gravedad
        gyr = np.loadtxt(f_gyr)       # rad/s
        n = min(len(acc), len(gyr))
        lab = np.zeros(n, dtype=int)
        for _, r in seg.iterrows():
            if r.act in DROP_ACTS:
                continue
            s = int(r.s) - 1 + int(TRIM_S * FS_RAW)    # labels.txt es 1-indexado
            e = int(r.e) - int(TRIM_S * FS_RAW)
            if r.act in (7, 8):                        # transiciones cortas: no recortar
                s, e = int(r.s) - 1, int(r.e)
            lab[max(s, 0):e] = r.act
        a = downsample(acc[:n], FS_RAW, FS_TARGET)
        g = downsample(gyr[:n], FS_RAW, FS_TARGET)
        l = downsample_labels(lab, FS_RAW, FS_TARGET)
        m = min(len(a), len(g), len(l))
        X, y = make_windows(a[:m], g[:m], l[:m], purity=PURITY)
        Xs.append(X); ys.append(y)
        gs.append(np.full(len(y), user)); es.append(np.full(len(y), exp))
    X = np.vstack(Xs); y = np.concatenate(ys)
    return X, y, np.concatenate(gs), np.concatenate(es)


def metrics(y_true_inv, y_pred_inv):
    """1 = no válida (movimiento). Devuelve sensibilidad a movimiento,
    tasa de quietas descartadas, exactitud."""
    cm = confusion_matrix(y_true_inv, y_pred_inv, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return dict(cm=cm,
                sens_mov=tp / max(tp + fn, 1),
                quietas_descartadas=fp / max(tn + fp, 1),
                acc=(tp + tn) / cm.sum())


def loso(X, y_inv, groups, make_model, is_baseline=False):
    """Leave-one-person-out. Devuelve predicciones por ventana."""
    pred = np.zeros_like(y_inv)
    for tr, te in LeaveOneGroupOut().split(X, y_inv, groups):
        m = make_model()
        m.fit(X[tr], y_inv[tr])
        pred[te] = m.predict(X[te])
    return pred


def plot_cm(cm, title, path):
    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["válida", "no válida"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["quieto", "movimiento"])
    ax.set_xlabel("predicción"); ax.set_ylabel("real"); ax.set_title(title, fontsize=9)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


def export_tree_to_c(tree, feature_names, path, fn_name="window_is_moving"):
    """Exporta un DecisionTreeClassifier binario a una función C (if/else).
    Devuelve 1 si la ventana es NO válida (movimiento), 0 si es válida."""
    t = tree.tree_
    lines = ["/* Autogenerado. Entrada: vector de características en el orden:"]
    for i, n in enumerate(feature_names):
        lines.append(f" *   f[{i}] = {n}")
    lines.append(" * Devuelve 1 = ventana NO válida (movimiento), 0 = válida. */")
    lines.append(f"static inline int {fn_name}(const float *f) {{")

    def rec(node, ind):
        pad = "    " * ind
        if t.feature[node] < 0:
            cls = int(np.argmax(t.value[node][0]))
            lines.append(f"{pad}return {tree.classes_[cls]};")
        else:
            lines.append(f"{pad}if (f[{t.feature[node]}] <= {t.threshold[node]:.6f}f) {{")
            rec(t.children_left[node], ind + 1)
            lines.append(f"{pad}}} else {{")
            rec(t.children_right[node], ind + 1)
            lines.append(f"{pad}}}")
    rec(0, 1)
    lines.append("}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./hapt")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--orientation-free", action="store_true",
                    help="excluye características por eje (no dependen de cómo esté colocado el sensor)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    log = open(os.path.join(args.out, "resultados.txt"), "w", encoding="utf-8")

    def P(*a):
        s = " ".join(str(x) for x in a)
        print(s); log.write(s + "\n")

    cache = os.path.join(args.out, "dataset_windows.npz")
    if os.path.exists(cache):
        d = np.load(cache); X, y, groups, exps = d["X"], d["y"], d["groups"], d["exps"]
    else:
        X, y, groups, exps = build_dataset(args.data)
        np.savez(cache, X=X, y=y, groups=groups, exps=exps)

    names = list(FEATURE_NAMES)
    if args.orientation_free:
        drop = {"acc_x_std", "acc_y_std", "acc_z_std", "acc_max_axis_range"}
        keep = [i for i, n in enumerate(names) if n not in drop]
        X = X[:, keep]; names = [names[i] for i in keep]
        P("(modo independiente de orientación: " + ", ".join(names) + ")")

    y_inv = (~np.isin(y, list(VALID_ACTS))).astype(int)   # 1 = movimiento
    P(f"Ventanas: {len(y)} | personas: {len(np.unique(groups))}")
    P(f"  válidas (quieto): {(y_inv == 0).sum()} | no válidas (movimiento): {(y_inv == 1).sum()}")
    for a in sorted(np.unique(y)):
        P(f"    {a:>2} {ACT[a]:<18} {int((y == a).sum())}")

    # ---------- Baseline: umbral sobre std de la magnitud ----------
    pred_b = loso(X, y_inv, groups, lambda: ThresholdBaseline(0))
    mb = metrics(y_inv, pred_b)
    thr_all = ThresholdBaseline(0).fit(X, y_inv).thr
    P("\n=== BASELINE: umbral en acc_mag_std (leave-one-person-out) ===")
    P(f"  umbral con todos los datos: {thr_all:.4f} g")
    P(f"  exactitud {mb['acc']:.3f} | movimiento detectado {mb['sens_mov']:.3f} | "
      f"quietas descartadas {mb['quietas_descartadas']:.3f}")
    P("  matriz [[TN FP],[FN TP]]:", mb["cm"].tolist())

    # ---------- Árbol: elegir profundidad con LOSO ----------
    P("\n=== ÁRBOL (leave-one-person-out) ===")
    best_depth, best_score = None, -1
    for depth in (2, 3, 4, 5, 6):
        mk = lambda d=depth: DecisionTreeClassifier(max_depth=d, class_weight="balanced",
                                                    min_samples_leaf=10, random_state=0)
        p = loso(X, y_inv, groups, mk)
        m = metrics(y_inv, p)
        bal = (m["sens_mov"] + 1 - m["quietas_descartadas"]) / 2
        P(f"  depth={depth}: acc {m['acc']:.3f} | mov detectado {m['sens_mov']:.3f} | "
          f"quietas descartadas {m['quietas_descartadas']:.3f}")
        if bal > best_score + 0.002:     # prefiere el más pequeño si empatan
            best_score, best_depth = bal, depth
    P(f"  -> profundidad elegida: {best_depth}")

    mk = lambda: DecisionTreeClassifier(max_depth=best_depth, class_weight="balanced",
                                        min_samples_leaf=10, random_state=0)
    pred_t = loso(X, y_inv, groups, mk)
    mt = metrics(y_inv, pred_t)
    P(f"  exactitud {mt['acc']:.3f} | movimiento detectado {mt['sens_mov']:.3f} | "
      f"quietas descartadas {mt['quietas_descartadas']:.3f}")
    P("  matriz [[TN FP],[FN TP]]:", mt["cm"].tolist())

    # Rendimiento por persona (¿resultado similar con alguien nuevo?)
    rows = []
    for u in np.unique(groups):
        k = groups == u
        m = metrics(y_inv[k], pred_t[k])
        rows.append((u, m["sens_mov"], m["quietas_descartadas"]))
    r = np.array(rows)
    P(f"\n  Por persona: sensibilidad mov. media {r[:,1].mean():.3f} "
      f"(mín {r[:,1].min():.3f}, persona {int(r[r[:,1].argmin(),0])}) | "
      f"quietas descartadas media {r[:,2].mean():.3f} (máx {r[:,2].max():.3f})")

    # Errores por tipo de actividad
    P("\n=== Tasa de error por actividad (árbol vs baseline) ===")
    P(f"  {'actividad':<18}{'n':>6}{'error árbol':>13}{'error baseline':>16}")
    for a in sorted(np.unique(y)):
        k = y == a
        e_t = (pred_t[k] != y_inv[k]).mean(); e_b = (pred_b[k] != y_inv[k]).mean()
        P(f"  {ACT[a]:<18}{int(k.sum()):>6}{e_t:>13.3f}{e_b:>16.3f}")

    # ---------- Modelo final con todos los datos ----------
    final = mk().fit(X, y_inv)
    P("\n=== MODELO FINAL (entrenado con todos los datos) ===")
    P(f"  nodos totales: {final.tree_.node_count} | hojas: {final.get_n_leaves()} | "
      f"profundidad: {final.get_depth()}")
    imp = final.feature_importances_
    order = np.argsort(imp)[::-1]
    P("  importancia de características:")
    for i in order:
        if imp[i] > 0:
            P(f"    {names[i]:<20}{imp[i]:.3f}")
    P("\n" + export_text(final, feature_names=names))

    # ---------- Veredicto frente a los criterios del plan ----------
    P("=== CRITERIOS DE VIABILIDAD ===")
    P(f"  >=90% movimiento detectado:   {mt['sens_mov']:.3f}  -> {'OK' if mt['sens_mov']>=0.90 else 'NO'}")
    P(f"  <=10% quietas descartadas:    {mt['quietas_descartadas']:.3f}  -> "
      f"{'OK' if mt['quietas_descartadas']<=0.10 else 'NO'}")
    P(f"  Mejora sobre baseline (mov. detectado a igual o menos descarte): "
      f"árbol {mt['sens_mov']:.3f}/{mt['quietas_descartadas']:.3f} vs "
      f"umbral {mb['sens_mov']:.3f}/{mb['quietas_descartadas']:.3f}")

    # ---------- Gráficas y exportación ----------
    plot_cm(mb["cm"], "Baseline (umbral)", os.path.join(args.out, "confusion_baseline.png"))
    plot_cm(mt["cm"], f"Árbol (depth={best_depth})", os.path.join(args.out, "confusion_arbol.png"))
    fig, ax = plt.subplots(figsize=(14, 6))
    plot_tree(final, feature_names=names, class_names=["válida", "no válida"],
              filled=True, impurity=False, ax=ax, fontsize=8)
    fig.savefig(os.path.join(args.out, "arbol.png"), dpi=130, bbox_inches="tight"); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.barh([names[i] for i in order[::-1]], imp[order[::-1]])
    ax.set_xlabel("importancia"); fig.tight_layout()
    fig.savefig(os.path.join(args.out, "importancias.png"), dpi=140); plt.close(fig)
    export_tree_to_c(final, names, os.path.join(args.out, "decision_tree.h"))
    P(f"\nArchivos guardados en {args.out}/")
    log.close()


if __name__ == "__main__":
    main()
