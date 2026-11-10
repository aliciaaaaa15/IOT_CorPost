#include "posture.h"
#include "config.h"

#include <math.h>
#include <stdbool.h>

#define RAD2DEG 57.29577951f

static float ref[3] = {0.0f, 0.0f, 1000.0f};
static volatile float tolerance_deg = TOLERANCE_DEG; /* changed by the app over BLE */

void posture_set_tolerance(float deg)
{
	tolerance_deg = deg;
}

static float norm3(const float v[3])
{
	return sqrtf(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
}

static float angle_between(const float a[3], const float b[3])
{
	float na = norm3(a), nb = norm3(b);

	if (na < 1e-3f || nb < 1e-3f) {
		return 0.0f;
	}
	float c = (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / (na * nb);

	c = c > 1.0f ? 1.0f : (c < -1.0f ? -1.0f : c);
	return acosf(c) * RAD2DEG;
}

void posture_window_stats(const struct imu_sample *s, const bool *ok, int n, struct window_result *r)
{
	float sum_mag = 0.0f, sum_mag2 = 0.0f;

	*r = (struct window_result){0};
	for (int i = 0; i < n; i++) {
		if (!ok[i]) {
			continue;
		}
		float a[3] = {s[i].acc[0], s[i].acc[1], s[i].acc[2]};
		float m = norm3(a);

		for (int k = 0; k < 3; k++) {
			r->acc_mean[k] += a[k];
			r->gyr_mean_dps[k] += s[i].gyr[k] / 16.0f;
		}
		sum_mag += m;
		sum_mag2 += m * m;
		r->n_valid++;
	}
	if (r->n_valid == 0) {
		return;
	}
	for (int k = 0; k < 3; k++) {
		r->acc_mean[k] /= r->n_valid;
		r->gyr_mean_dps[k] /= r->n_valid;
	}
	float mean = sum_mag / r->n_valid;
	float var = sum_mag2 / r->n_valid - mean * mean;

	r->amag_std_mg = var > 0.0f ? sqrtf(var) : 0.0f;
}

void posture_set_reference(const float acc_mean[3])
{
	for (int k = 0; k < 3; k++) {
		ref[k] = acc_mean[k];
	}
}

void posture_eval(const struct imu_sample *s, const bool *ok, int n, struct window_result *r)
{
	posture_window_stats(s, ok, n, r);

	/* PROVISIONAL motion filter (threshold). TODO: decision tree. */
	if (r->n_valid < MIN_VALID_SAMPLES || r->amag_std_mg > MOTION_STD_MG) {
		r->status = POSTURE_INVALID;
		return;
	}
	r->angle_deg = angle_between(r->acc_mean, ref);
	r->status = r->angle_deg > tolerance_deg ? POSTURE_BAD : POSTURE_OK;
}

const char *posture_status_str(enum posture_status st)
{
	switch (st) {
	case POSTURE_OK:
		return "OK";
	case POSTURE_BAD:
		return "BAD";
	default:
		return "INVALID";
	}
}
