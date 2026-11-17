#include "motion.h"
#include "decision_tree.h"

#include <math.h>

#define RAD2DEG     57.29577951f
#define MG_TO_G     0.001f
#define RAW_TO_RADS (3.14159265f / 180.0f / 16.0f) /* BNO055: 1 LSB = 1/16 dps */

static float norm3(const float v[3])
{
	return sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
}

static float angle_deg(const float a[3], const float b[3])
{
	float na = norm3(a), nb = norm3(b);

	if (na < 1e-6f || nb < 1e-6f) {
		return 0.0f;
	}
	float c = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (na * nb);

	c = c > 1.0f ? 1.0f : (c < -1.0f ? -1.0f : c);
	return acosf(c) * RAD2DEG;
}

static void to_units(const struct imu_sample *s, float acc[3], float gyr[3])
{
	for (int k = 0; k < 3; k++) {
		acc[k] = s->acc[k] * MG_TO_G;
		gyr[k] = s->gyr[k] * RAW_TO_RADS;
	}
}

void motion_features(const struct imu_sample *s, const bool *ok, int n,
		     float f[MOTION_N_FEATURES])
{
	float acc[3], gyr[3], mean_vec[3] = {0, 0, 0};
	float sum_a = 0, sum_g = 0, min_a = INFINITY, max_a = -INFINITY;
	float min_g = INFINITY, max_g = -INFINITY;
	int cnt = 0, first = -1, last = -1;

	for (int k = 0; k < MOTION_N_FEATURES; k++) {
		f[k] = 0.0f;
	}

	/* Pass 1: means, minimum/maximum and first/last valid sample */
	for (int i = 0; i < n; i++) {
		if (!ok[i]) {
			continue;
		}
		to_units(&s[i], acc, gyr);
		float ma = norm3(acc), mg = norm3(gyr);

		sum_a += ma;
		sum_g += mg;
		min_a = fminf(min_a, ma);
		max_a = fmaxf(max_a, ma);
		min_g = fminf(min_g, mg);
		max_g = fmaxf(max_g, mg);
		for (int k = 0; k < 3; k++) {
			mean_vec[k] += acc[k];
		}
		if (first < 0) {
			first = i;
		}
		last = i;
		cnt++;
	}
	if (cnt == 0) {
		return;
	}
	float mean_a = sum_a / cnt, mean_g = sum_g / cnt;

	for (int k = 0; k < 3; k++) {
		mean_vec[k] /= cnt;
	}

	/* Pass 2: variances (two passes to avoid losing precision in float)
	 * and maximum angle relative to the mean gravity vector */
	float var_a = 0, var_g = 0, max_dev = 0;

	for (int i = 0; i < n; i++) {
		if (!ok[i]) {
			continue;
		}
		to_units(&s[i], acc, gyr);
		float da = norm3(acc) - mean_a, dg = norm3(gyr) - mean_g;

		var_a += da * da;
		var_g += dg * dg;
		max_dev = fmaxf(max_dev, angle_deg(acc, mean_vec));
	}

	float acc_first[3], acc_last[3];

	to_units(&s[first], acc_first, gyr);
	to_units(&s[last], acc_last, gyr);

	f[0] = sqrtf(var_a / cnt); /* population standard deviation, same as numpy */
	f[1] = max_a - min_a;
	f[2] = sqrtf(var_g / cnt);
	f[3] = max_g - min_g;
	f[4] = angle_deg(acc_first, acc_last);
	f[5] = max_dev;
}

bool motion_is_moving(const float f[MOTION_N_FEATURES])
{
	return window_is_moving(f) != 0;
}
