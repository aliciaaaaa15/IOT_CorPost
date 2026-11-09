/* Autogenerado. Entrada: vector de características en el orden:
 *   f[0] = acc_mag_std
 *   f[1] = acc_mag_range
 *   f[2] = gyro_mag_std
 *   f[3] = gyro_mag_range
 *   f[4] = angle_change
 *   f[5] = angle_max_dev
 * Devuelve 1 = ventana NO válida (movimiento), 0 = válida. */
static inline int window_is_moving(const float *f) {
    if (f[0] <= 0.036539f) {
        if (f[5] <= 19.717456f) {
            return 0;
        } else {
            return 1;
        }
    } else {
        if (f[5] <= 8.217953f) {
            return 1;
        } else {
            return 1;
        }
    }
}
