/* Arduino Modulino Vibro over I2C. */
#pragma once
#include <zephyr/device.h>
#include <stdint.h>

#define VIBRO_ADDR 0x38 /* default 7-bit address */

/* Check that the Modulino responds. 0 if present. */
int vibro_init(const struct device *i2c);

/* One pulse: frequency (Hz), duration (ms), power (0-100). Does not block. */
int vibro_pulse(uint32_t freq, uint32_t ms, uint32_t power);

/* Bad-posture alert: two short pulses (~1 s in total). Blocks for ~0.8 s. */
int vibro_alert(void);
