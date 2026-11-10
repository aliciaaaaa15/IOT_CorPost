/* CorPost - device firmware (PoC).
 *
 * Hardware: nRF52-DK (nRF52832) -> Modulino Vibro (0x38) -> BNO055 (0x28/0x29), all over I2C.
 *
 * How it works:
 *  1. Start BLE (advertising "CorPost", secure pairing with passkey).
 *  2. Calibration: wait until the user is still and store that posture as 0°.
 *     The Vibro gives a short pulse to confirm. DK Button 1 (or command
 *     0x03 over BLE) repeats the calibration.
 *  3. At every interval, take a 2 s window (50 samples at 25 Hz).
 *  4. Motion filter: if the user is moving, the window is INVALID (no vibration).
 *  5. Otherwise, compute the angle relative to the reference: OK or BAD depending on the tolerance.
 *  6. If BAD, the Vibro gives the alert (two pulses), respecting VIB_MIN_INTERVAL_S.
 *  7. The reading is stored in the buffer and sent over BLE (24 B notification)
 *     as soon as the link is ready. Without a connection, it accumulates (up to 50).
 *
 * DK Button 2: deletes the stored pairing (to pair another phone).
 *
 * Pending: decision tree instead of the threshold.
 * The RTT output is for debugging. */
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/gpio.h>
#include <stdbool.h>
#include <stdlib.h>

#include "config.h"
#include "bno055.h"
#include "vibro.h"
#include "posture.h"
#include "ble.h"

static const struct device *i2c = DEVICE_DT_GET(DT_NODELABEL(arduino_i2c));
static const struct gpio_dt_spec button1 = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static const struct gpio_dt_spec button2 = GPIO_DT_SPEC_GET(DT_ALIAS(sw1), gpios);
static struct gpio_callback button1_cb, button2_cb;

/* Flags and parameters changed by the interrupts or by the Bluetooth thread */
static volatile bool recalibrate;
static volatile bool clear_bonds;
static volatile uint16_t interval_s = MEASURE_INTERVAL_S;
static volatile bool vibration_on = true;

static struct imu_sample win[WINDOW_SAMPLES];
static bool win_ok[WINDOW_SAMPLES];

/* printk without float support: print with 1 decimal */
static void print_f1(const char *label, float v)
{
	int t = (int)(v * 10.0f + (v >= 0 ? 0.5f : -0.5f));

	printk("%s=%s%d.%d ", label, t < 0 ? "-" : "", abs(t) / 10, abs(t) % 10);
}

/* --- Buttons ------------------------------------------------------------- */
static void on_button1(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	recalibrate = true;
}

static void on_button2(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	clear_bonds = true;
}

static void button_setup(const struct gpio_dt_spec *b, struct gpio_callback *cb,
			 gpio_callback_handler_t handler)
{
	if (!gpio_is_ready_dt(b)) {
		printk("Button not available\n");
		return;
	}
	gpio_pin_configure_dt(b, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(b, GPIO_INT_EDGE_TO_ACTIVE);
	gpio_init_callback(cb, handler, BIT(b->pin));
	gpio_add_callback(b->port, cb);
}

/* --- BLE commands (they run on the Bluetooth thread: they only store the value) --- */
static void cmd_set_interval(uint16_t s)
{
	interval_s = s;
}

static void cmd_set_tolerance(uint8_t deg)
{
	posture_set_tolerance(deg);
}

static void cmd_recalibrate(void)
{
	recalibrate = true;
}

static void cmd_set_vibration(bool on)
{
	vibration_on = on;
}

static const struct ble_cmd_handlers cmd_handlers = {
	.set_interval = cmd_set_interval,
	.set_tolerance = cmd_set_tolerance,
	.recalibrate = cmd_recalibrate,
	.set_vibration = cmd_set_vibration,
};

/* --- Measurement ---------------------------------------------------------- */
static void scan(void)
{
	uint8_t dummy;

	printk("I2C devices:");
	for (uint8_t addr = 0x08; addr < 0x78; addr++) {
		if (i2c_read(i2c, &dummy, 1, addr) == 0) {
			printk(" 0x%02x", addr);
		}
	}
	printk("\n");
}

/* Take a window of WINDOW_SAMPLES at 25 Hz. Lost samples are marked in win_ok. */
static void capture_window(void)
{
	int64_t next = k_uptime_get();

	for (int i = 0; i < WINDOW_SAMPLES; i++) {
		win_ok[i] = (bno055_read(&win[i]) == 0);
		next += SAMPLE_PERIOD_MS;

		int64_t wait = next - k_uptime_get();

		if (wait > 0) {
			k_msleep(wait);
		}
	}
}

/* Repeat windows until a still one is found and use it as the reference posture */
static void calibrate(void)
{
	struct window_result r;

	recalibrate = false;
	printk("Calibrating: stay still in the correct posture...\n");
	while (1) {
		capture_window();
		posture_window_stats(win, win_ok, WINDOW_SAMPLES, &r);
		if (r.n_valid >= MIN_VALID_SAMPLES && r.amag_std_mg <= MOTION_STD_MG) {
			break;
		}
		print_f1("  moving, std_mg", r.amag_std_mg);
		printk("retrying\n");
	}
	posture_set_reference(r.acc_mean);
	printk("Reference (mg): ");
	print_f1("x", r.acc_mean[0]);
	print_f1("y", r.acc_mean[1]);
	print_f1("z", r.acc_mean[2]);
	printk("\n");
	vibro_pulse(1000, 150, 60); /* confirmation */
}

/* Tasks handled while waiting for the next interval */
static void service_ble(void)
{
	if (clear_bonds) {
		clear_bonds = false;
		ble_clear_bonds();
	}
	ble_flush();
}

int main(void)
{
	if (!device_is_ready(i2c)) {
		printk("I2C is not ready\n");
		return 0;
	}

	k_msleep(3000); /* time to connect RTT and for the BNO055 to start up */
	printk("*** CorPost firmware (PoC) ***\n");
	scan();

	if (bno055_init(i2c) != 0) {
		printk("ERROR: BNO055 not found or could not be configured\n");
		return 0;
	}
	printk("BNO055 at 0x%02x\n", bno055_addr());

	if (vibro_init(i2c) != 0) {
		printk("WARNING: the Modulino Vibro does not respond at 0x%02x (continuing without vibration)\n",
		       VIBRO_ADDR);
	} else {
		printk("Modulino Vibro at 0x%02x\n", VIBRO_ADDR);
	}

	button_setup(&button1, &button1_cb, on_button1);
	button_setup(&button2, &button2_cb, on_button2);

	if (ble_init(&cmd_handlers) != 0) {
		printk("WARNING: BLE not available (continuing without sending data)\n");
	}

	printk("Interval %d s, window %d samples at %d Hz, tolerance %d degrees\n",
	       MEASURE_INTERVAL_S, WINDOW_SAMPLES, 1000 / SAMPLE_PERIOD_MS, (int)TOLERANCE_DEG);

	calibrate();

	int64_t last_vib = -((int64_t)VIB_MIN_INTERVAL_S * 1000) - 1;

	while (1) {
		int64_t t0 = k_uptime_get();

		if (recalibrate) {
			calibrate();
		}

		struct window_result r;

		capture_window();
		posture_eval(win, win_ok, WINDOW_SAMPLES, &r);

		int64_t now = k_uptime_get();

		printk("[%u s] %s ", (uint32_t)(now / 1000), posture_status_str(r.status));
		if (r.status != POSTURE_INVALID) {
			print_f1("angle", r.angle_deg);
		}
		print_f1("std_mg", r.amag_std_mg);
		printk("valid=%d/%d\n", r.n_valid, WINDOW_SAMPLES);

		if (r.status == POSTURE_BAD && vibration_on &&
		    now - last_vib >= (int64_t)VIB_MIN_INTERVAL_S * 1000) {
			int err = vibro_alert();

			printk("  -> vibration%s\n", err ? " (I2C ERROR)" : "");
			last_vib = k_uptime_get();
		}

		/* The reading goes into the buffer; it is sent now if the link is ready */
		ble_submit(&r, now);
		if (ble_flush() == 0) {
			printk("  BLE: link not ready, %d reading(s) in the buffer\n", ble_pending());
		}

		const struct bno055_stats *st = bno055_get_stats();

		printk("  bus: lost=%u retries=%u mismatches=%u\n",
		       st->failed, st->retries, st->mismatches);

		/* Wait until the next interval. Every 100 ms it services BLE (sends
		 * what is pending after reconnecting, deletes bonds) and the button can cut it short. */
		while (!recalibrate && k_uptime_get() - t0 < (int64_t)interval_s * 1000) {
			service_ble();
			k_msleep(100);
		}
	}
	return 0;
}
