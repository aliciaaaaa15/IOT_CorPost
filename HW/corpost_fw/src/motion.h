/* Motion filter: features of a 2 s window + decision tree (decision_tree.h).
 *
 * C port of window_features() in ai_movment_test/har_common.py, orientation-free mode.
 * Differences with the Python version, needed on the device:
 *  - It converts the BNO055 units to the training units (mg -> g, 1/16 dps -> rad/s).
 *  - It only uses the samples marked as valid (samples lost over I2C are skipped);
 *    angle_change uses the first and the last VALID sample. */
#pragma once
#include <stdbool.h>
#include "bno055.h"

#define MOTION_N_FEATURES 6

/* Order (same as decision_tree.h):
 *   f[0] acc_mag_std (g)      f[1] acc_mag_range (g)
 *   f[2] gyro_mag_std (rad/s) f[3] gyro_mag_range (rad/s)
 *   f[4] angle_change (deg)   f[5] angle_max_dev (deg) */
void motion_features(const struct imu_sample *s, const bool *ok, int n,
		     float f[MOTION_N_FEATURES]);

/* true if the tree classifies the window as motion (NOT valid). */
bool motion_is_moving(const float f[MOTION_N_FEATURES]);
