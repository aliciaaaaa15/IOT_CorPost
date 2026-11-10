/* Minimal BNO055 driver (accelerometer + gyroscope, no fusion) over I2C. */
#pragma once
#include <zephyr/device.h>
#include <stdint.h>

struct imu_sample {
	int16_t acc[3]; /* mg, includes gravity */
	int16_t gyr[3]; /* 1 LSB = 1/16 dps */
};

struct bno055_stats {
	uint32_t retries;    /* I2C reads repeated because of a bus error */
	uint32_t mismatches; /* double reads that did not match */
	uint32_t failed;     /* lost samples */
};

/* Find the sensor (0x28/0x29), configure it and leave it measuring. 0 on success. */
int bno055_init(const struct device *i2c);

/* Read one sample (6 axes). 0 on success, <0 if it was lost. */
int bno055_read(struct imu_sample *s);

uint8_t bno055_addr(void);
const struct bno055_stats *bno055_get_stats(void);
