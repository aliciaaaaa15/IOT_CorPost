/* BLE de CorPost.
 *
 * - GAP: el nRF52 es periférico. Se anuncia como "CorPost" con el UUID del servicio.
 * - GATT: servicio propio con tres características (D3):
 *     Reading (Notify)  dispositivo -> app, paquete de 24 B
 *     Command (Write)   app -> dispositivo, opcode + parámetro
 *     Time    (Write)   app -> dispositivo, uint32 LE con la hora UTC
 * - Seguridad: LE Secure Connections con passkey (nivel 4: cifrado AES-CCM y
 *   autenticado contra MITM). Todas las características exigen ese nivel.
 *   Bonding guardado en flash y un solo móvil emparejado a la vez.
 * - Búfer circular de lecturas: si no se pueden enviar, se guardan y se envían en
 *   ráfaga al reconectar. */
#include "ble.h"
#include "config.h"

#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/crc.h>
#include <string.h>
#include <math.h>

/* ---------------------------------------------------------------------------
 * UUIDs (128 bits, propios). Base aleatoria bd5fXXXX-319b-420e-ae78-678d1c7cf46d
 * --------------------------------------------------------------------------- */
#define CORPOST_UUID(n) BT_UUID_128_ENCODE(0xbd5f0000 + (n), 0x319b, 0x420e, 0xae78, 0x678d1c7cf46d)

#define BT_UUID_CORPOST_SERVICE_VAL CORPOST_UUID(1)
static const struct bt_uuid_128 uuid_service = BT_UUID_INIT_128(CORPOST_UUID(1));
static const struct bt_uuid_128 uuid_reading = BT_UUID_INIT_128(CORPOST_UUID(2));
static const struct bt_uuid_128 uuid_command = BT_UUID_INIT_128(CORPOST_UUID(3));
static const struct bt_uuid_128 uuid_time = BT_UUID_INIT_128(CORPOST_UUID(4));

static const struct ble_cmd_handlers *cmd;

/* ---------------------------------------------------------------------------
 * Hora UTC. El nRF no tiene reloj real: la app escribe la hora UTC al conectar y
 * desde ahí se cuenta con el uptime (que lo lleva el RTC del chip).
 * --------------------------------------------------------------------------- */
static struct k_spinlock time_lock;
static bool time_set;
static uint32_t utc_ref;       /* hora UTC recibida (s) */
static int64_t utc_ref_uptime; /* uptime en ese momento (ms) */

static bool uptime_to_utc(int64_t uptime_ms, uint32_t *utc)
{
	bool ok;
	k_spinlock_key_t key = k_spin_lock(&time_lock);

	ok = time_set;
	if (ok) {
		*utc = (uint32_t)((int64_t)utc_ref + (uptime_ms - utc_ref_uptime) / 1000);
	}
	k_spin_unlock(&time_lock, key);
	return ok;
}

/* ---------------------------------------------------------------------------
 * Búfer circular de lecturas (D3: 50 entradas, sobrescribe la más antigua).
 * Solo lo usa el hilo principal (ble_submit / ble_flush), así que no necesita lock.
 * Guarda el uptime y no la hora UTC: así las lecturas tomadas antes de recibir la
 * hora reciben su timestamp correcto cuando la app la escribe.
 * --------------------------------------------------------------------------- */
struct entry {
	int16_t acc[3];
	int16_t gyr[3];
	float angle;
	uint8_t status;
	int64_t uptime_ms;
};

static struct entry ring[BUFFER_SIZE];
static int ring_head; /* siguiente posición libre */
static int ring_count;

static int16_t to_i16(float v)
{
	v = roundf(v);
	if (v > INT16_MAX) {
		return INT16_MAX;
	}
	if (v < INT16_MIN) {
		return INT16_MIN;
	}
	return (int16_t)v;
}

void ble_submit(const struct window_result *r, int64_t uptime_ms)
{
	struct entry *e = &ring[ring_head];

	if (ring_count == BUFFER_SIZE) {
		printk("  bufer lleno: se descarta la lectura mas antigua\n");
	} else {
		ring_count++;
	}
	for (int k = 0; k < 3; k++) {
		e->acc[k] = to_i16(r->acc_mean[k]);           /* mg */
		e->gyr[k] = to_i16(r->gyr_mean_dps[k] * 16.0f); /* 1/16 dps (LSB del BNO055) */
	}
	e->angle = (r->status == POSTURE_INVALID) ? 0.0f : r->angle_deg;
	e->status = (uint8_t)r->status;
	e->uptime_ms = uptime_ms;
	ring_head = (ring_head + 1) % BUFFER_SIZE;
}

int ble_pending(void)
{
	return ring_count;
}

uint16_t ble_crc16(const uint8_t *data, int len)
{
	/* CRC-16/CCITT-FALSE = crc16_itu_t con semilla 0xFFFF ("123456789" -> 0x29B1) */
	return crc16_itu_t(0xFFFF, data, len);
}

/* Paquete de 24 B, little-endian (D3, tabla del paquete de telemetría) */
static void encode(const struct entry *e, uint32_t ts, uint8_t out[BLE_READING_LEN])
{
	uint32_t angle_bits;

	for (int k = 0; k < 3; k++) {
		sys_put_le16((uint16_t)e->acc[k], &out[0 + 2 * k]);
		sys_put_le16((uint16_t)e->gyr[k], &out[6 + 2 * k]);
	}
	memcpy(&angle_bits, &e->angle, 4); /* float32 IEEE-754 */
	sys_put_le32(angle_bits, &out[12]);
	out[16] = e->status & 0x03;
	out[17] = BATTERY_LEVEL;
	sys_put_le32(ts, &out[18]);
	sys_put_le16(ble_crc16(out, 22), &out[22]);
}

/* ---------------------------------------------------------------------------
 * Servicio GATT
 * --------------------------------------------------------------------------- */
static ssize_t write_command(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			     const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
	const uint8_t *b = buf;

	if (offset != 0) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
	}
	if (len < 1 || len > 4) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
	}

	switch (b[0]) {
	case CMD_SET_INTERVAL: {
		if (len != 3) {
			return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
		}
		uint16_t s = sys_get_le16(&b[1]);

		if (s < MEASURE_INTERVAL_MIN_S || s > MEASURE_INTERVAL_MAX_S) {
			return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
		}
		printk("BLE comando: intervalo = %u s\n", s);
		cmd->set_interval(s);
		break;
	}
	case CMD_SET_TOLERANCE:
		if (len != 2) {
			return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
		}
		if (b[1] < TOLERANCE_MIN_DEG || b[1] > TOLERANCE_MAX_DEG) {
			return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
		}
		printk("BLE comando: tolerancia = %u grados\n", b[1]);
		cmd->set_tolerance(b[1]);
		break;
	case CMD_RECALIBRATE:
		if (len != 1) {
			return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
		}
		printk("BLE comando: recalibrar\n");
		cmd->recalibrate();
		break;
	case CMD_SET_VIBRATION:
		if (len != 2 || b[1] > 1) {
			return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
		}
		printk("BLE comando: vibracion %s\n", b[1] ? "ON" : "OFF");
		cmd->set_vibration(b[1] != 0);
		break;
	default:
		printk("BLE comando desconocido 0x%02x\n", b[0]);
		return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
	}
	return len;
}

static ssize_t write_time(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			  const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
	if (offset != 0) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_OFFSET);
	}
	if (len != 4) {
		return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
	}

	k_spinlock_key_t key = k_spin_lock(&time_lock);

	utc_ref = sys_get_le32(buf);
	utc_ref_uptime = k_uptime_get();
	time_set = true;
	k_spin_unlock(&time_lock, key);

	printk("BLE hora UTC = %u\n", sys_get_le32(buf));
	return len;
}

static void reading_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	printk("BLE notificaciones de Reading %s\n",
	       value == BT_GATT_CCC_NOTIFY ? "activadas" : "desactivadas");
}

/* Permisos *_AUTHEN: solo con enlace cifrado y autenticado (emparejado con passkey).
 * Los CUD (nombres legibles en nRF Connect) son públicos: no contienen datos. */
BT_GATT_SERVICE_DEFINE(corpost_svc,
	BT_GATT_PRIMARY_SERVICE(&uuid_service),

	/* attrs[1] declaración, attrs[2] valor */
	BT_GATT_CHARACTERISTIC(&uuid_reading.uuid, BT_GATT_CHRC_NOTIFY,
			       BT_GATT_PERM_NONE, NULL, NULL, NULL),
	BT_GATT_CCC(reading_ccc_changed, BT_GATT_PERM_READ_AUTHEN | BT_GATT_PERM_WRITE_AUTHEN),
	BT_GATT_CUD("Reading", BT_GATT_PERM_READ),

	BT_GATT_CHARACTERISTIC(&uuid_command.uuid, BT_GATT_CHRC_WRITE,
			       BT_GATT_PERM_WRITE_AUTHEN, NULL, write_command, NULL),
	BT_GATT_CUD("Command", BT_GATT_PERM_READ),

	BT_GATT_CHARACTERISTIC(&uuid_time.uuid, BT_GATT_CHRC_WRITE,
			       BT_GATT_PERM_WRITE_AUTHEN, NULL, write_time, NULL),
	BT_GATT_CUD("Time", BT_GATT_PERM_READ),
);

#define READING_ATTR (&corpost_svc.attrs[1])

/* ---------------------------------------------------------------------------
 * Advertising: flags + UUID del servicio + nombre (3 + 18 + 9 = 30 de 31 B)
 * --------------------------------------------------------------------------- */
static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL, BT_UUID_CORPOST_SERVICE_VAL),
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static struct k_work adv_work;

static void adv_work_handler(struct k_work *work)
{
	/* Conectable, intervalo 100-150 ms (FAST_2) */
	int err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2, ad, ARRAY_SIZE(ad), NULL, 0);

	if (err) {
		printk("BLE: no se pudo iniciar el advertising (%d)\n", err);
		return;
	}
	printk("BLE: anunciandose como \"%s\"\n", CONFIG_BT_DEVICE_NAME);
}

/* ---------------------------------------------------------------------------
 * Conexión
 * --------------------------------------------------------------------------- */
static K_MUTEX_DEFINE(conn_lock);
static struct bt_conn *cur_conn;

static void print_addr(const char *msg, struct bt_conn *conn)
{
	char addr[BT_ADDR_LE_STR_LEN];

	bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));
	printk("%s %s\n", msg, addr);
}

static void print_params(const char *msg, uint32_t interval_us, uint16_t latency,
			 uint16_t timeout_10ms)
{
	printk("%s intervalo=%u.%02u ms latencia=%u timeout=%u ms\n", msg,
	       interval_us / 1000, (interval_us % 1000) / 10, latency, timeout_10ms * 10);
}

static void connected(struct bt_conn *conn, uint8_t err)
{
	struct bt_conn_info info;

	if (err) {
		printk("BLE: conexion fallida 0x%02x %s\n", err, bt_hci_err_to_str(err));
		return;
	}
	print_addr("BLE: conectado a", conn);
	if (bt_conn_get_info(conn, &info) == 0) {
		print_params("BLE: parametros iniciales", info.le.interval_us, info.le.latency,
			     info.le.timeout);
	}

	k_mutex_lock(&conn_lock, K_FOREVER);
	cur_conn = bt_conn_ref(conn);
	k_mutex_unlock(&conn_lock);

	/* Pide seguridad nivel 4 desde el principio: si el móvil ya está emparejado
	 * solo se recifra; si no, empieza el emparejamiento con passkey.
	 * Se usa un int y no el uint8_t 'err' del callback: el error es negativo
	 * (p. ej. -ENOMEM = -12, que en un uint8_t se imprimía como 244). */
	int sec_err = bt_conn_set_security(conn, BT_SECURITY_L4);

	if (sec_err) {
		printk("BLE: error al pedir seguridad (%d)%s\n", sec_err,
		       sec_err == -ENOMEM ? ": no queda hueco para otro bond (CONFIG_BT_MAX_PAIRED)"
					  : "");
	}
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	printk("BLE: desconectado, motivo 0x%02x %s\n", reason, bt_hci_err_to_str(reason));

	k_mutex_lock(&conn_lock, K_FOREVER);
	if (cur_conn == conn) {
		bt_conn_unref(cur_conn);
		cur_conn = NULL;
	}
	k_mutex_unlock(&conn_lock);
}

/* La conexión anterior ya está liberada: se vuelve a anunciar */
static void recycled(void)
{
	k_work_submit(&adv_work);
}

static void le_param_updated(struct bt_conn *conn, uint16_t interval, uint16_t latency,
			     uint16_t timeout)
{
	print_params("BLE: parametros actualizados", interval * 1250U, latency, timeout);
}

static void security_changed(struct bt_conn *conn, bt_security_t level,
			     enum bt_security_err err)
{
	if (err) {
		printk("BLE: fallo de seguridad, nivel %u, error %d %s\n", level, err,
		       bt_security_err_to_str(err));
		return;
	}
	printk("BLE: seguridad nivel %u%s\n", level,
	       level >= BT_SECURITY_L4 ? " (LE Secure Connections, autenticado y cifrado)" : "");
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
	.disconnected = disconnected,
	.recycled = recycled,
	.le_param_updated = le_param_updated,
	.security_changed = security_changed,
};

static void mtu_updated(struct bt_conn *conn, uint16_t tx, uint16_t rx)
{
	printk("BLE: MTU actualizado tx=%u rx=%u\n", tx, rx);
}

static struct bt_gatt_cb gatt_callbacks = {
	.att_mtu_updated = mtu_updated,
};

/* ---------------------------------------------------------------------------
 * Emparejamiento: el nRF "muestra" el passkey (por RTT) y el usuario lo teclea en
 * el móvil. Capacidad de E/S = DisplayOnly -> método Passkey Entry -> protegido
 * contra MITM.
 * --------------------------------------------------------------------------- */
static void auth_passkey_display(struct bt_conn *conn, unsigned int passkey)
{
	printk("\n=============================================\n");
	printk("  CODIGO DE EMPAREJAMIENTO: %06u\n", passkey);
	printk("  Introducelo en el movil\n");
	printk("=============================================\n\n");
}

static void auth_cancel(struct bt_conn *conn)
{
	printk("BLE: emparejamiento cancelado\n");
}

static void pairing_complete(struct bt_conn *conn, bool bonded)
{
	printk("BLE: emparejamiento completado%s\n", bonded ? ", bond guardado en flash" : "");
}

static void pairing_failed(struct bt_conn *conn, enum bt_security_err reason)
{
	printk("BLE: emparejamiento fallido: %d %s\n", reason, bt_security_err_to_str(reason));
	printk("     (si ya hay otro movil emparejado, borra el bond con el Boton 2)\n");
}

static struct bt_conn_auth_cb auth_callbacks = {
	.passkey_display = auth_passkey_display,
	.cancel = auth_cancel,
};

static struct bt_conn_auth_info_cb auth_info_callbacks = {
	.pairing_complete = pairing_complete,
	.pairing_failed = pairing_failed,
};

static void count_bond(const struct bt_bond_info *info, void *user_data)
{
	char addr[BT_ADDR_LE_STR_LEN];

	bt_addr_le_to_str(&info->addr, addr, sizeof(addr));
	printk("  bond: %s\n", addr);
	(*(int *)user_data)++;
}

/* Imprime los bonds guardados y devuelve cuántos hay */
static int list_bonds(void)
{
	int bonds = 0;

	bt_foreach_bond(BT_ID_DEFAULT, count_bond, &bonds);
	printk("BLE: %d movil(es) emparejado(s) guardado(s) (maximo %d)\n", bonds,
	       CONFIG_BT_MAX_PAIRED);
	return bonds;
}

/* ---------------------------------------------------------------------------
 * API pública
 * --------------------------------------------------------------------------- */
int ble_init(const struct ble_cmd_handlers *handlers)
{
	int err;

	cmd = handlers;

	err = bt_conn_auth_cb_register(&auth_callbacks);
	err |= bt_conn_auth_info_cb_register(&auth_info_callbacks);
	if (err) {
		printk("BLE: error registrando callbacks de seguridad\n");
		return -EIO;
	}
	bt_gatt_cb_register(&gatt_callbacks);

	err = bt_enable(NULL);
	if (err) {
		printk("BLE: bt_enable fallo (%d)\n", err);
		return err;
	}
	/* Carga de flash los bonds (claves) y suscripciones guardadas */
	settings_load();

	list_bonds();

	k_work_init(&adv_work, adv_work_handler);
	k_work_submit(&adv_work);
	return 0;
}

/* El enlace está listo para enviar lecturas */
static bool link_ready(struct bt_conn *conn)
{
	bool has_time;
	k_spinlock_key_t key = k_spin_lock(&time_lock);

	has_time = time_set;
	k_spin_unlock(&time_lock, key);

	return bt_conn_get_security(conn) >= BT_SECURITY_L4 &&
	       bt_gatt_is_subscribed(conn, READING_ATTR, BT_GATT_CCC_NOTIFY) &&
	       bt_gatt_get_mtu(conn) >= BLE_READING_LEN + 3 && /* 3 B de cabecera ATT */
	       has_time; /* sin hora, el timestamp sería 0 y la app lo deduplicaría */
}

int ble_flush(void)
{
	struct bt_conn *conn = NULL;
	int sent = 0;

	if (ring_count == 0) {
		return 0;
	}

	k_mutex_lock(&conn_lock, K_FOREVER);
	if (cur_conn) {
		conn = bt_conn_ref(cur_conn);
	}
	k_mutex_unlock(&conn_lock);
	if (!conn) {
		return 0;
	}

	while (ring_count > 0 && link_ready(conn)) {
		int tail = (ring_head - ring_count + BUFFER_SIZE) % BUFFER_SIZE;
		uint8_t pkt[BLE_READING_LEN];
		uint32_t ts = 0;

		uptime_to_utc(ring[tail].uptime_ms, &ts);
		encode(&ring[tail], ts, pkt);

		/* Desde el hilo principal, si no hay buffers libres, bt_gatt_notify ESPERA a
		 * que se libere uno (la ráfaga va al ritmo del enlace). Devuelve error si la
		 * conexión se cae: la lectura se queda en el búfer para la próxima vez. */
		if (bt_gatt_notify(conn, READING_ATTR, pkt, sizeof(pkt)) != 0) {
			break;
		}
		ring_count--;
		sent++;
	}
	bt_conn_unref(conn);

	if (sent > 0) {
		printk("  BLE: %d lectura(s) enviada(s), %d pendiente(s)\n", sent, ring_count);
	}
	return sent;
}

void ble_clear_bonds(void)
{
	k_mutex_lock(&conn_lock, K_FOREVER);
	if (cur_conn) {
		bt_conn_disconnect(cur_conn, BT_HCI_ERR_REMOTE_USER_TERM_CONN);
	}
	k_mutex_unlock(&conn_lock);

	int err = bt_unpair(BT_ID_DEFAULT, BT_ADDR_LE_ANY);

	printk("BLE: emparejamientos borrados%s\n", err ? " (ERROR)" : "");
	list_bonds(); /* comprobación: debe salir 0 */
}
