/* Driver mínimo del BNO055 (acelerómetro + giroscopio, sin fusión) por I2C. */
#pragma once
#include <zephyr/device.h>
#include <stdint.h>

struct imu_sample {
	int16_t acc[3]; /* mg, incluye la gravedad */
	int16_t gyr[3]; /* 1 LSB = 1/16 dps */
};

struct bno055_stats {
	uint32_t retries;    /* lecturas I2C repetidas por error de bus */
	uint32_t mismatches; /* dobles lecturas que no coincidían */
	uint32_t failed;     /* muestras perdidas */
};

/* Busca el sensor (0x28/0x29), lo configura y lo deja midiendo. 0 si va bien. */
int bno055_init(const struct device *i2c);

/* Lee una muestra (6 ejes). 0 si va bien, <0 si se ha perdido. */
int bno055_read(struct imu_sample *s);

uint8_t bno055_addr(void);
const struct bno055_stats *bno055_get_stats(void);
