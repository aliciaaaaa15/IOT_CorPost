/* features.h - Orientation-free features for a window of 20 samples at 10 Hz.
 * Order (matches run_hapt.py --orientation-free / run_own.py --orientation-free):
 *   f[0] acc_mag_std   f[1] acc_mag_range   f[2] gyro_mag_std
 *   f[3] gyro_mag_range f[4] angle_change   f[5] angle_max_dev
 * Units: acceleration in g, gyroscope in rad/s, angles in degrees.
 * IMPORTANT: if the tree is exported in --orientation-free mode, the indices of
 * decision_tree.h are those of this list of 6. */
#pragma once
#include <math.h>
#define WIN_N 20
#define RAD2DEG 57.29577951f

static inline float vnorm(const float *v) { return sqrtf(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]); }

static inline float angle_deg(const float *a, const float *b) {
    float na = vnorm(a), nb = vnorm(b);
    if (na < 1e-6f || nb < 1e-6f) return 0.0f;
    float c = (a[0]*b[0] + a[1]*b[1] + a[2]*b[2]) / (na * nb);
    if (c > 1.0f) c = 1.0f; else if (c < -1.0f) c = -1.0f;
    return acosf(c) * RAD2DEG;
}

static void mag_stats(float m[WIN_N], float *std, float *range) {
    float s = 0, mn = m[0], mx = m[0];
    for (int i = 0; i < WIN_N; i++) { s += m[i]; if (m[i] < mn) mn = m[i]; if (m[i] > mx) mx = m[i]; }
    float mean = s / WIN_N, v = 0;
    for (int i = 0; i < WIN_N; i++) v += (m[i] - mean) * (m[i] - mean);
    *std = sqrtf(v / WIN_N);      /* population standard deviation, same as numpy */
    *range = mx - mn;
}

/* acc[i][3] in g, gyro[i][3] in rad/s. f: output of 6 floats. */
static void compute_features(const float acc[WIN_N][3], const float gyro[WIN_N][3], float f[6]) {
    float am[WIN_N], gm[WIN_N], mean[3] = {0, 0, 0};
    for (int i = 0; i < WIN_N; i++) {
        am[i] = vnorm(acc[i]); gm[i] = vnorm(gyro[i]);
        for (int k = 0; k < 3; k++) mean[k] += acc[i][k] / WIN_N;
    }
    mag_stats(am, &f[0], &f[1]);
    mag_stats(gm, &f[2], &f[3]);
    f[4] = angle_deg(acc[0], acc[WIN_N - 1]);
    float mx = 0;
    for (int i = 0; i < WIN_N; i++) { float a = angle_deg(acc[i], mean); if (a > mx) mx = a; }
    f[5] = mx;
}

/* Uso:
 *   float f[6]; compute_features(acc, gyro, f);
 *   if (window_is_moving(f)) { discard the reading } else { compare the angle with the tolerance }
 */
