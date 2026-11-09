/* CorPost - firmware del dispositivo (PoC).
 *
 * Hardware: nRF52-DK (nRF52832) -> Modulino Vibro (0x38) -> BNO055 (0x28/0x29), todo por I2C.
 *
 * Funcionamiento:
 *  1. Arranca BLE (advertising "CorPost", emparejamiento seguro con passkey).
 *  2. Calibración: espera a que el usuario esté quieto y guarda su postura como 0°.
 *     El Vibro da un pulso corto para confirmar. El Botón 1 del DK (o el comando
 *     0x03 por BLE) repite la calibración.
 *  3. Cada intervalo toma una ventana de 2 s (50 muestras a 25 Hz).
 *  4. Filtro de movimiento: si el usuario se mueve, la ventana es INVALID (no vibra).
 *  5. Si no, calcula el ángulo respecto a la referencia: OK o BAD según la tolerancia.
 *  6. Si es BAD, el Vibro da el aviso (dos pulsos), respetando VIB_MIN_INTERVAL_S.
 *  7. La lectura se guarda en el búfer y se envía por BLE (notificación de 24 B)
 *     en cuanto el enlace está listo. Sin conexión, se acumula (hasta 50).
 *
 * Botón 2 del DK: borra el emparejamiento guardado (para emparejar otro móvil).
 *
 * Pendiente: árbol de decisión en lugar del umbral.
 * La salida por RTT es para depurar. */
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

/* Flags y parámetros que cambian las interrupciones o el hilo de Bluetooth */
static volatile bool recalibrate;
static volatile bool clear_bonds;
static volatile uint16_t interval_s = MEASURE_INTERVAL_S;
static volatile bool vibration_on = true;

static struct imu_sample win[WINDOW_SAMPLES];
static bool win_ok[WINDOW_SAMPLES];

/* printk sin soporte de float: imprime con 1 decimal */
static void print_f1(const char *label, float v)
{
	int t = (int)(v * 10.0f + (v >= 0 ? 0.5f : -0.5f));

	printk("%s=%s%d.%d ", label, t < 0 ? "-" : "", abs(t) / 10, abs(t) % 10);
}

/* --- Botones ------------------------------------------------------------- */
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
		printk("Boton no disponible\n");
		return;
	}
	gpio_pin_configure_dt(b, GPIO_INPUT);
	gpio_pin_interrupt_configure_dt(b, GPIO_INT_EDGE_TO_ACTIVE);
	gpio_init_callback(cb, handler, BIT(b->pin));
	gpio_add_callback(b->port, cb);
}

/* --- Comandos BLE (se ejecutan en el hilo de Bluetooth: solo guardan el valor) --- */
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

/* --- Medida --------------------------------------------------------------- */
static void scan(void)
{
	uint8_t dummy;

	printk("Dispositivos I2C:");
	for (uint8_t addr = 0x08; addr < 0x78; addr++) {
		if (i2c_read(i2c, &dummy, 1, addr) == 0) {
			printk(" 0x%02x", addr);
		}
	}
	printk("\n");
}

/* Toma una ventana de WINDOW_SAMPLES a 25 Hz. Las muestras perdidas se marcan en win_ok. */
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

/* Repite ventanas hasta encontrar una quieta y la usa como postura de referencia */
static void calibrate(void)
{
	struct window_result r;

	recalibrate = false;
	printk("Calibrando: quedate quieto en postura correcta...\n");
	while (1) {
		capture_window();
		posture_window_stats(win, win_ok, WINDOW_SAMPLES, &r);
		if (r.n_valid >= MIN_VALID_SAMPLES && r.amag_std_mg <= MOTION_STD_MG) {
			break;
		}
		print_f1("  en movimiento, std_mg", r.amag_std_mg);
		printk("reintentando\n");
	}
	posture_set_reference(r.acc_mean);
	printk("Referencia (mg): ");
	print_f1("x", r.acc_mean[0]);
	print_f1("y", r.acc_mean[1]);
	print_f1("z", r.acc_mean[2]);
	printk("\n");
	vibro_pulse(1000, 150, 60); /* confirmación */
}

/* Tareas que se atienden mientras se espera al siguiente intervalo */
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
		printk("I2C no esta listo\n");
		return 0;
	}

	k_msleep(3000); /* tiempo para conectar RTT y para que arranque el BNO055 */
	printk("*** CorPost firmware (PoC) ***\n");
	scan();

	if (bno055_init(i2c) != 0) {
		printk("ERROR: no se encuentra o no se configura el BNO055\n");
		return 0;
	}
	printk("BNO055 en 0x%02x\n", bno055_addr());

	if (vibro_init(i2c) != 0) {
		printk("AVISO: el Modulino Vibro no responde en 0x%02x (se sigue sin vibracion)\n",
		       VIBRO_ADDR);
	} else {
		printk("Modulino Vibro en 0x%02x\n", VIBRO_ADDR);
	}

	button_setup(&button1, &button1_cb, on_button1);
	button_setup(&button2, &button2_cb, on_button2);

	if (ble_init(&cmd_handlers) != 0) {
		printk("AVISO: BLE no disponible (se sigue sin enviar datos)\n");
	}

	printk("Intervalo %d s, ventana %d muestras a %d Hz, tolerancia %d grados\n",
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
			print_f1("angulo", r.angle_deg);
		}
		print_f1("std_mg", r.amag_std_mg);
		printk("validas=%d/%d\n", r.n_valid, WINDOW_SAMPLES);

		if (r.status == POSTURE_BAD && vibration_on &&
		    now - last_vib >= (int64_t)VIB_MIN_INTERVAL_S * 1000) {
			int err = vibro_alert();

			printk("  -> vibracion%s\n", err ? " (ERROR I2C)" : "");
			last_vib = k_uptime_get();
		}

		/* La lectura va al búfer; se envía ya si el enlace está listo */
		ble_submit(&r, now);
		if (ble_flush() == 0) {
			printk("  BLE: enlace no listo, %d lectura(s) en el bufer\n", ble_pending());
		}

		const struct bno055_stats *st = bno055_get_stats();

		printk("  bus: perdidas=%u reintentos=%u discrepancias=%u\n",
		       st->failed, st->retries, st->mismatches);

		/* Espera hasta el siguiente intervalo. Cada 100 ms atiende el BLE (envía
		 * lo pendiente al reconectar, borra bonds) y el botón puede adelantarla. */
		while (!recalibrate && k_uptime_get() - t0 < (int64_t)interval_s * 1000) {
			service_ble();
			k_msleep(100);
		}
	}
	return 0;
}
