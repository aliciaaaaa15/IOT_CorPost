"""
har_common.py - Funciones compartidas: remuestreo, ventaneo y características.
Se usa tanto con el dataset HAPT como con vuestras grabaciones propias.
"""
import numpy as np

# ---------------- Parámetros del sistema final ----------------
FS_TARGET = 10          # Hz de la medición real del dispositivo
WIN_SAMPLES = 20        # 2 s a 10 Hz
STEP_SAMPLES = 10       # 50 % de solape

FEATURE_NAMES = [
    "acc_mag_std",      # desv. estándar de la magnitud de la aceleración
    "acc_mag_range",    # rango (máx-mín) de la magnitud
    "acc_x_std", "acc_y_std", "acc_z_std",
    "acc_max_axis_range",   # mayor rango de los 3 ejes
    "gyro_mag_std",     # desv. estándar de la magnitud del giroscopio
    "gyro_mag_range",
    "angle_change",     # ángulo (º) entre el vector gravedad de la 1ª y la última muestra
    "angle_max_dev",    # máx. ángulo (º) respecto a la media de la ventana
]


def downsample(x, fs_in, fs_out):
    """Reduce frecuencia promediando bloques (equivale a un filtro paso bajo
    sencillo + decimado). x: (N, C). Requiere fs_in múltiplo de fs_out."""
    k = int(round(fs_in / fs_out))
    n = (len(x) // k) * k
    return x[:n].reshape(-1, k, x.shape[1]).mean(axis=1)


def downsample_labels(lab, fs_in, fs_out):
    """Etiqueta por muestra a fs_out: la etiqueta mayoritaria de cada bloque
    (0 = sin etiquetar)."""
    k = int(round(fs_in / fs_out))
    n = (len(lab) // k) * k
    blocks = lab[:n].reshape(-1, k)
    out = np.zeros(len(blocks), dtype=int)
    for i, b in enumerate(blocks):
        vals, cnt = np.unique(b, return_counts=True)
        out[i] = vals[np.argmax(cnt)]
    return out


def _angle_between(a, b):
    """Ángulo en grados entre vectores 3D (a, b: (3,))."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    c = np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0)
    return float(np.degrees(np.arccos(c)))


def window_features(acc, gyro):
    """acc, gyro: (WIN_SAMPLES, 3). Devuelve vector de len(FEATURE_NAMES).
    Pensado para ser portable a C (solo std, max, min, norma y arccos)."""
    acc_mag = np.linalg.norm(acc, axis=1)
    gyro_mag = np.linalg.norm(gyro, axis=1)
    ptp_axes = acc.max(axis=0) - acc.min(axis=0)

    mean_vec = acc.mean(axis=0)
    angle_change = _angle_between(acc[0], acc[-1])
    angle_max_dev = max(_angle_between(a, mean_vec) for a in acc)

    return np.array([
        acc_mag.std(),
        acc_mag.max() - acc_mag.min(),
        acc[:, 0].std(), acc[:, 1].std(), acc[:, 2].std(),
        ptp_axes.max(),
        gyro_mag.std(),
        gyro_mag.max() - gyro_mag.min(),
        angle_change,
        angle_max_dev,
    ])


def make_windows(acc, gyro, lab, purity=0.8, win=WIN_SAMPLES, step=STEP_SAMPLES):
    """Ventanea una grabación ya a FS_TARGET.
    lab: etiqueta por muestra (0 = sin etiquetar).
    Devuelve X (n, n_feat), y (n,) con la etiqueta mayoritaria.
    Se descartan ventanas con etiqueta 0 o con pureza < purity."""
    X, y = [], []
    for s in range(0, len(acc) - win + 1, step):
        l = lab[s:s + win]
        vals, cnt = np.unique(l, return_counts=True)
        j = np.argmax(cnt)
        if vals[j] == 0 or cnt[j] / win < purity:
            continue
        X.append(window_features(acc[s:s + win], gyro[s:s + win]))
        y.append(vals[j])
    if not X:
        return np.empty((0, len(FEATURE_NAMES))), np.empty(0, dtype=int)
    return np.vstack(X), np.array(y)


# ---------------- Baseline sin IA ----------------
class ThresholdBaseline:
    """Regla simple: 'no válida' si feature > umbral.
    El umbral se elige en entrenamiento maximizando la exactitud balanceada
    (media de sensibilidad a movimiento y especificidad a quieto)."""

    def __init__(self, feature_idx=0):
        self.idx = feature_idx
        self.thr = None

    def fit(self, X, y_invalid):
        v = X[:, self.idx]
        cands = np.unique(np.quantile(v, np.linspace(0.01, 0.99, 400)))
        best, best_t = -1, None
        for t in cands:
            pred = v > t
            sens = pred[y_invalid == 1].mean() if (y_invalid == 1).any() else 0
            spec = (~pred)[y_invalid == 0].mean() if (y_invalid == 0).any() else 0
            bal = (sens + spec) / 2
            if bal > best:
                best, best_t = bal, t
        self.thr = best_t
        return self

    def predict(self, X):
        return (X[:, self.idx] > self.thr).astype(int)
