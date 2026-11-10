/* Evaluation of a measurement window: motion filter + angle + status. */
#pragma once
#include <stdbool.h>
#include "bno055.h"

/* Same values as the "status" field of the BLE packet (D3, Table II) */
enum posture_status {
	POSTURE_OK = 0,
	POSTURE_BAD = 1,
	POSTURE_INVALID = 2,
};

struct window_result {
	int n_valid;            /* valid samples in the window */
	float acc_mean[3];      /* mg */
	float gyr_mean_dps[3];  /* dps */
	float amag_std_mg;      /* standard deviation of the acceleration magnitude */
	float angle_deg;        /* deviation from the reference (only if not INVALID) */
	enum posture_status status;
};

/* Mean and deviation of a window, without classifying it (used for calibration). */
void posture_window_stats(const struct imu_sample *s, const bool *ok, int n, struct window_result *r);

/* Store the reference posture (0°) from the mean gravity of a window. */
void posture_set_reference(const float acc_mean[3]);

/* Classify the window: INVALID if there is motion or samples are missing;
  otherwise OK/BAD depending on the angle and the tolerance. */
void posture_eval(const struct imu_sample *s, const bool *ok, int n, struct window_result *r);

/* Change the tolerance margin (degrees). It applies from the next window. */
void posture_set_tolerance(float deg);

const char *posture_status_str(enum posture_status st);
