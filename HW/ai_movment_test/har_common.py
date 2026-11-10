"""
har_common.py - Shared functions: resampling, windowing and features.
Used both with the HAPT dataset and with the project's own recordings.
"""
import numpy as np

# ---------------- Final system parameters ----------------
FS_TARGET = 10          # Hz of the device's actual measurement
WIN_SAMPLES = 20        # 2 s at 10 Hz
STEP_SAMPLES = 10       # 50 % overlap

FEATURE_NAMES = [
    "acc_mag_std",      # standard deviation of the acceleration magnitude
    "acc_mag_range",    # range (max-min) of the magnitude
    "acc_x_std", "acc_y_std", "acc_z_std",
    "acc_max_axis_range",   # largest range of the 3 axes
    "gyro_mag_std",     # standard deviation of the gyroscope magnitude
    "gyro_mag_range",
    "angle_change",     # angle (deg) between the gravity vector of the 1st and the last sample
    "angle_max_dev",    # max. angle (deg) relative to the window mean
]


def downsample(x, fs_in, fs_out):
    """Reduce the sampling rate by averaging blocks (equivalent to a simple
    low-pass filter + decimation). x: (N, C). Requires fs_in to be a multiple of fs_out."""
    k = int(round(fs_in / fs_out))
    n = (len(x) // k) * k
    return x[:n].reshape(-1, k, x.shape[1]).mean(axis=1)


def downsample_labels(lab, fs_in, fs_out):
    """Per-sample label at fs_out: the majority label of each block
    (0 = unlabeled)."""
    k = int(round(fs_in / fs_out))
    n = (len(lab) // k) * k
    blocks = lab[:n].reshape(-1, k)
    out = np.zeros(len(blocks), dtype=int)
    for i, b in enumerate(blocks):
        vals, cnt = np.unique(b, return_counts=True)
        out[i] = vals[np.argmax(cnt)]
    return out


def _angle_between(a, b):
    """Angle in degrees between 3D vectors (a, b: (3,))."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    c = np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0)
    return float(np.degrees(np.arccos(c)))


def window_features(acc, gyro):
    """acc, gyro: (WIN_SAMPLES, 3). Returns a vector of len(FEATURE_NAMES).
    Designed to be portable to C (only std, max, min, norm and arccos)."""
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
    """Split a recording (already at FS_TARGET) into windows.
    lab: per-sample label (0 = unlabeled).
    Returns X (n, n_feat), y (n,) with the majority label.
    Windows with label 0 or with purity < purity are discarded."""
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


# ---------------- Baseline (no machine learning) ----------------
class ThresholdBaseline:
    """Simple rule: 'not valid' if feature > threshold.
    The threshold is chosen during training by maximizing the balanced accuracy
    (mean of the sensitivity to motion and the specificity to still)."""

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
