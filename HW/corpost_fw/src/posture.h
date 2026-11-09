/* Evaluación de una ventana de medida: filtro de movimiento + ángulo + estado. */
#pragma once
#include <stdbool.h>
#include "bno055.h"

/* Mismos valores que el campo "status" del paquete BLE (D3, Tabla II) */
enum posture_status {
	POSTURE_OK = 0,
	POSTURE_BAD = 1,
	POSTURE_INVALID = 2,
};

struct window_result {
	int n_valid;            /* muestras válidas en la ventana */
	float acc_mean[3];      /* mg */
	float gyr_mean_dps[3];  /* dps */
	float amag_std_mg;      /* desviación estándar del módulo de la aceleración */
	float angle_deg;        /* desviación respecto a la referencia (solo si no es INVALID) */
	enum posture_status status;
};

/* Media y desviación de una ventana, sin clasificar (sirve para calibrar). */
void posture_window_stats(const struct imu_sample *s, const bool *ok, int n, struct window_result *r);

/* Guarda la postura de referencia (0°) a partir de la gravedad media de una ventana. */
void posture_set_reference(const float acc_mean[3]);

/* Clasifica la ventana: INVALID si hay movimiento o faltan muestras;
  si no, OK/BAD según el ángulo y la tolerancia. */
void posture_eval(const struct imu_sample *s, const bool *ok, int n, struct window_result *r);

/* Cambia el margen de tolerancia (grados). Se aplica desde la siguiente ventana. */
void posture_set_tolerance(float deg);

const char *posture_status_str(enum posture_status st);
