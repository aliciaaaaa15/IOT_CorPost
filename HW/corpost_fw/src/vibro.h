/* Arduino Modulino Vibro por I2C. */
#pragma once
#include <zephyr/device.h>
#include <stdint.h>

#define VIBRO_ADDR 0x38 /* dirección 7 bits por defecto */

/* Comprueba que el Modulino responde. 0 si está presente. */
int vibro_init(const struct device *i2c);

/* Un pulso: frecuencia (Hz), duración (ms), potencia (0-100). No bloquea. */
int vibro_pulse(uint32_t freq, uint32_t ms, uint32_t power);

/* Aviso de mala postura: dos pulsos cortos (~1 s en total). Bloquea ~0,8 s. */
int vibro_alert(void);
