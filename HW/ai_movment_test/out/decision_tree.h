/* Autogenerado. Entrada: vector de características en el orden:
 *   f[0] = acc_mag_std
 *   f[1] = acc_mag_range
 *   f[2] = acc_x_std
 *   f[3] = acc_y_std
 *   f[4] = acc_z_std
 *   f[5] = acc_max_axis_range
 *   f[6] = gyro_mag_std
 *   f[7] = gyro_mag_range
 *   f[8] = angle_change
 *   f[9] = angle_max_dev
 * Devuelve 1 = ventana NO válida (movimiento), 0 = válida. */
static inline int window_is_moving(const float *f) {
    if (f[2] <= 0.046203f) {
        if (f[3] <= 0.067367f) {
            return 0;
        } else {
            return 0;
        }
    } else {
        if (f[1] <= 0.111970f) {
            return 0;
        } else {
            return 1;
        }
    }
}
