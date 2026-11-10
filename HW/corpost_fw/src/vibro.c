#include "vibro.h"

#include <zephyr/kernel.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/byteorder.h>

static const struct device *bus;

int vibro_init(const struct device *i2c)
{
	uint8_t dummy;

	bus = i2c;
	return i2c_read(bus, &dummy, 1, VIBRO_ADDR);
}

/* Modulino Vibro format: 3 x uint32 little-endian: frequency, duration, power */
int vibro_pulse(uint32_t freq, uint32_t ms, uint32_t power)
{
	uint8_t buf[12];
	int err = 0;

	sys_put_le32(freq, &buf[0]);
	sys_put_le32(ms, &buf[4]);
	sys_put_le32(power, &buf[8]);

	/* the bus is unreliable with the current cables: retry */
	for (int i = 0; i < 3; i++) {
		err = i2c_write(bus, buf, sizeof(buf), VIBRO_ADDR);
		if (err == 0) {
			break;
		}
	}
	return err;
}

int vibro_alert(void)
{
	int err = vibro_pulse(1000, 300, 80);

	k_msleep(500);
	err |= vibro_pulse(1000, 300, 80);
	k_msleep(300);
	return err;
}
