#include "bno055.h"

#include <zephyr/kernel.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/util.h>
#include <errno.h>
#include <stdlib.h>

/* Página 0 */
#define REG_CHIP_ID     0x00 /* debe valer 0xA0 */
#define REG_PAGE_ID     0x07 /* existe en ambas páginas */
#define REG_ACC_DATA    0x08 /* X,Y,Z LSB/MSB */
#define REG_GYR_DATA    0x14
#define REG_UNIT_SEL    0x3B
#define REG_OPR_MODE    0x3D
#define REG_PWR_MODE    0x3E
#define REG_SYS_TRIG    0x3F
/* Página 1 */
#define REG_ACC_CONFIG  0x08 /* bits 1:0 rango, 4:2 ancho de banda */
#define REG_GYR_CONFIG0 0x0A /* bits 2:0 rango, 5:3 ancho de banda */

#define CHIP_ID         0xA0
#define MODE_CONFIG     0x00
#define MODE_ACCGYRO    0x05
#define ACC_CFG         0x05 /* +-4 g, BW 15,63 Hz */
#define GYR_CFG         0x28 /* +-2000 dps, BW 12 Hz */

/* Con el montaje actual (cables largos) las lecturas de >2 bytes seguidos se
  corrompen; las de 2 bytes son fiables. Cada eje se lee en su propia
  transacción, con reintentos y doble lectura de verificación. */
#define READ_RETRIES    3
#define MAX_DIFF        200

static const struct device *bus;
static uint8_t addr;
static struct bno055_stats stats;

static int wr(uint8_t reg, uint8_t val)
{
	uint8_t buf[2] = {reg, val};

	return i2c_write(bus, buf, sizeof(buf), addr);
}

static int read_i16_once(uint8_t reg, int16_t *out)
{
	uint8_t b[2];
	int err = 0;

	for (int i = 0; i < READ_RETRIES; i++) {
		err = i2c_write_read(bus, addr, &reg, 1, b, 2);
		if (err == 0) {
			*out = sys_get_le16(b);
			return 0;
		}
		stats.retries++;
	}
	return err;
}

static int read_i16(uint8_t reg, int16_t *out)
{
	for (int i = 0; i < READ_RETRIES; i++) {
		int16_t a, b;

		if (read_i16_once(reg, &a) || read_i16_once(reg, &b)) {
			return -EIO;
		}
		if (abs(a - b) <= MAX_DIFF) {
			*out = b;
			return 0;
		}
		stats.mismatches++;
	}
	return -EIO;
}

int bno055_init(const struct device *i2c)
{
	static const uint8_t cand[] = {0x28, 0x29};
	int err = 0;

	bus = i2c;
	addr = 0;
	for (int i = 0; i < ARRAY_SIZE(cand); i++) {
		uint8_t id = 0;

		if (i2c_reg_read_byte(bus, cand[i], REG_CHIP_ID, &id) == 0 && id == CHIP_ID) {
			addr = cand[i];
			break;
		}
	}
	if (addr == 0) {
		return -ENODEV;
	}

	err |= wr(REG_OPR_MODE, MODE_CONFIG); /* los ajustes solo se aplican en CONFIG */
	k_msleep(25);
	err |= wr(REG_PWR_MODE, 0x00);        /* normal */
	err |= wr(REG_UNIT_SEL, 0x01);        /* acc en mg, gyro en dps */
	err |= wr(REG_SYS_TRIG, 0x00);        /* reloj interno */
	err |= wr(REG_PAGE_ID, 1);
	err |= wr(REG_ACC_CONFIG, ACC_CFG);
	err |= wr(REG_GYR_CONFIG0, GYR_CFG);
	err |= wr(REG_PAGE_ID, 0);
	err |= wr(REG_OPR_MODE, MODE_ACCGYRO);
	k_msleep(25);

	return err ? -EIO : 0;
}

int bno055_read(struct imu_sample *s)
{
	for (int i = 0; i < 3; i++) {
		if (read_i16(REG_ACC_DATA + 2 * i, &s->acc[i]) ||
		    read_i16(REG_GYR_DATA + 2 * i, &s->gyr[i])) {
			stats.failed++;
			return -EIO;
		}
	}
	return 0;
}

uint8_t bno055_addr(void)
{
	return addr;
}

const struct bno055_stats *bno055_get_stats(void)
{
	return &stats;
}
