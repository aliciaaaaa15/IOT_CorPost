/* CorPost BLE.
 *
 * - GAP: the nRF52 is a peripheral. It advertises as "CorPost" with the service UUID.
 * - GATT: custom service with three characteristics (D3):
 *     Reading (Notify)  device -> app, 24 B packet
 *     Command (Write)   app -> device, opcode + parameter
 *     Time    (Write)   app -> device, uint32 LE with the UTC time
 * - Security: LE Secure Connections with passkey (level 4: AES-CCM encryption and
 *   authenticated against MITM). All characteristics require that level.
 *   Bonding stored in flash and only one phone paired at a time.
 * - Circular reading buffer: readings that cannot be sent are stored and sent as a
 *   burst on reconnection. */
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
 * UUIDs (128 bits, custom). Random base bd5fXXXX-319b-420e-ae78-678d1c7cf46d
 * --------------------------------------------------------------------------- */
#define CORPOST_UUID(n) BT_UUID_128_ENCODE(0xbd5f0000 + (n), 0x319b, 0x420e, 0xae78, 0x678d1c7cf46d)

#define BT_UUID_CORPOST_SERVICE_VAL CORPOST_UUID(1)
static const struct bt_uuid_128 uuid_service = BT_UUID_INIT_128(CORPOST_UUID(1));
static const struct bt_uuid_128 uuid_reading = BT_UUID_INIT_128(CORPOST_UUID(2));
static const struct bt_uuid_128 uuid_command = BT_UUID_INIT_128(CORPOST_UUID(3));
static const struct bt_uuid_128 uuid_time = BT_UUID_INIT_128(CORPOST_UUID(4));

static const struct ble_cmd_handlers *cmd;

/* ---------------------------------------------------------------------------
 * UTC time. The nRF has no real-time clock: the app writes the UTC time on connect and
 * from then on it is tracked with the uptime (kept by the chip's RTC).
 * --------------------------------------------------------------------------- */
static struct k_spinlock time_lock;
static bool time_set;
static uint32_t utc_ref;       /* UTC time received (s) */
static int64_t utc_ref_uptime; /* uptime at that moment (ms) */

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
 * Circular reading buffer (D3: 50 entries, overwrites the oldest one).
 * Only the main thread uses it (ble_submit / ble_flush), so it needs no lock.
 * It stores the uptime and not the UTC time: this way, readings taken before the
 * time is received get their correct timestamp once the app writes it.
 * --------------------------------------------------------------------------- */
struct entry {
	int16_t acc[3];
	int16_t gyr[3];
	float angle;
	uint8_t status;
	int64_t uptime_ms;
};

static struct entry ring[BUFFER_SIZE];
static int ring_head; /* next free position */
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
		printk("  buffer full: the oldest reading is discarded\n");
	} else {
		ring_count++;
	}
	for (int k = 0; k < 3; k++) {
		e->acc[k] = to_i16(r->acc_mean[k]);           /* mg */
		e->gyr[k] = to_i16(r->gyr_mean_dps[k] * 16.0f); /* 1/16 dps (BNO055 LSB) */
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
	/* CRC-16/CCITT-FALSE = crc16_itu_t with seed 0xFFFF ("123456789" -> 0x29B1) */
	return crc16_itu_t(0xFFFF, data, len);
}

/* 24 B packet, little-endian (D3, telemetry packet table) */
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
 * GATT service
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
		printk("BLE command: interval = %u s\n", s);
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
		printk("BLE command: tolerance = %u degrees\n", b[1]);
		cmd->set_tolerance(b[1]);
		break;
	case CMD_RECALIBRATE:
		if (len != 1) {
			return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
		}
		printk("BLE command: recalibrate\n");
		cmd->recalibrate();
		break;
	case CMD_SET_VIBRATION:
		if (len != 2 || b[1] > 1) {
			return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
		}
		printk("BLE command: vibration %s\n", b[1] ? "ON" : "OFF");
		cmd->set_vibration(b[1] != 0);
		break;
	default:
		printk("BLE unknown command 0x%02x\n", b[0]);
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

	printk("BLE UTC time = %u\n", sys_get_le32(buf));
	return len;
}

static void reading_ccc_changed(const struct bt_gatt_attr *attr, uint16_t value)
{
	printk("BLE Reading notifications %s\n",
	       value == BT_GATT_CCC_NOTIFY ? "enabled" : "disabled");
}

/* *_AUTHEN permissions: only with an encrypted and authenticated link (paired with passkey).
 * The CUDs (human-readable names in nRF Connect) are public: they contain no data. */
BT_GATT_SERVICE_DEFINE(corpost_svc,
	BT_GATT_PRIMARY_SERVICE(&uuid_service),

	/* attrs[1] declaration, attrs[2] value */
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
 * Advertising: flags + service UUID + name (3 + 18 + 9 = 30 of 31 B)
 * --------------------------------------------------------------------------- */
static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL, BT_UUID_CORPOST_SERVICE_VAL),
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static struct k_work adv_work;

static void adv_work_handler(struct k_work *work)
{
	/* Connectable, interval 100-150 ms (FAST_2) */
	int err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2, ad, ARRAY_SIZE(ad), NULL, 0);

	if (err) {
		printk("BLE: could not start advertising (%d)\n", err);
		return;
	}
	printk("BLE: advertising as \"%s\"\n", CONFIG_BT_DEVICE_NAME);
}

/* ---------------------------------------------------------------------------
 * Connection
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
	printk("%s interval=%u.%02u ms latency=%u timeout=%u ms\n", msg,
	       interval_us / 1000, (interval_us % 1000) / 10, latency, timeout_10ms * 10);
}

static void connected(struct bt_conn *conn, uint8_t err)
{
	struct bt_conn_info info;

	if (err) {
		printk("BLE: connection failed 0x%02x %s\n", err, bt_hci_err_to_str(err));
		return;
	}
	print_addr("BLE: connected to", conn);
	if (bt_conn_get_info(conn, &info) == 0) {
		print_params("BLE: initial parameters", info.le.interval_us, info.le.latency,
			     info.le.timeout);
	}

	k_mutex_lock(&conn_lock, K_FOREVER);
	cur_conn = bt_conn_ref(conn);
	k_mutex_unlock(&conn_lock);

	/* Request security level 4 from the start: if the phone is already paired it is
	 * only re-encrypted; otherwise, passkey pairing starts.
	 * An int is used rather than the callback's uint8_t 'err': the error is negative
	 * (e.g. -ENOMEM = -12, which would print as 244 as a uint8_t). */
	int sec_err = bt_conn_set_security(conn, BT_SECURITY_L4);

	if (sec_err) {
		printk("BLE: error requesting security (%d)%s\n", sec_err,
		       sec_err == -ENOMEM ? ": no room for another bond (CONFIG_BT_MAX_PAIRED)"
					  : "");
	}
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	printk("BLE: disconnected, reason 0x%02x %s\n", reason, bt_hci_err_to_str(reason));

	k_mutex_lock(&conn_lock, K_FOREVER);
	if (cur_conn == conn) {
		bt_conn_unref(cur_conn);
		cur_conn = NULL;
	}
	k_mutex_unlock(&conn_lock);
}

/* The previous connection is already released: advertise again */
static void recycled(void)
{
	k_work_submit(&adv_work);
}

static void le_param_updated(struct bt_conn *conn, uint16_t interval, uint16_t latency,
			     uint16_t timeout)
{
	print_params("BLE: updated parameters", interval * 1250U, latency, timeout);
}

static void security_changed(struct bt_conn *conn, bt_security_t level,
			     enum bt_security_err err)
{
	if (err) {
		printk("BLE: security failure, level %u, error %d %s\n", level, err,
		       bt_security_err_to_str(err));
		return;
	}
	printk("BLE: security level %u%s\n", level,
	       level >= BT_SECURITY_L4 ? " (LE Secure Connections, authenticated and encrypted)" : "");
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
	printk("BLE: MTU updated tx=%u rx=%u\n", tx, rx);
}

static struct bt_gatt_cb gatt_callbacks = {
	.att_mtu_updated = mtu_updated,
};

/* ---------------------------------------------------------------------------
 * Pairing: the nRF "displays" the passkey (over RTT) and the user types it on the
 * phone. I/O capability = DisplayOnly -> Passkey Entry method -> protected
 * against MITM.
 * --------------------------------------------------------------------------- */
static void auth_passkey_display(struct bt_conn *conn, unsigned int passkey)
{
	printk("\n=============================================\n");
	printk("  PAIRING CODE: %06u\n", passkey);
	printk("  Enter it on the phone\n");
	printk("=============================================\n\n");
}

static void auth_cancel(struct bt_conn *conn)
{
	printk("BLE: pairing cancelled\n");
}

static void pairing_complete(struct bt_conn *conn, bool bonded)
{
	printk("BLE: pairing complete%s\n", bonded ? ", bond saved to flash" : "");
}

static void pairing_failed(struct bt_conn *conn, enum bt_security_err reason)
{
	printk("BLE: pairing failed: %d %s\n", reason, bt_security_err_to_str(reason));
	printk("     (if another phone is already paired, delete the bond with Button 2)\n");
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

/* Print the stored bonds and return how many there are */
static int list_bonds(void)
{
	int bonds = 0;

	bt_foreach_bond(BT_ID_DEFAULT, count_bond, &bonds);
	printk("BLE: %d paired phone(s) stored (max %d)\n", bonds,
	       CONFIG_BT_MAX_PAIRED);
	return bonds;
}

/* ---------------------------------------------------------------------------
 * Public API
 * --------------------------------------------------------------------------- */
int ble_init(const struct ble_cmd_handlers *handlers)
{
	int err;

	cmd = handlers;

	err = bt_conn_auth_cb_register(&auth_callbacks);
	err |= bt_conn_auth_info_cb_register(&auth_info_callbacks);
	if (err) {
		printk("BLE: error registering security callbacks\n");
		return -EIO;
	}
	bt_gatt_cb_register(&gatt_callbacks);

	err = bt_enable(NULL);
	if (err) {
		printk("BLE: bt_enable failed (%d)\n", err);
		return err;
	}
	/* Load the stored bonds (keys) and subscriptions from flash */
	settings_load();

	list_bonds();

	k_work_init(&adv_work, adv_work_handler);
	k_work_submit(&adv_work);
	return 0;
}

/* The link is ready to send readings */
static bool link_ready(struct bt_conn *conn)
{
	bool has_time;
	k_spinlock_key_t key = k_spin_lock(&time_lock);

	has_time = time_set;
	k_spin_unlock(&time_lock, key);

	return bt_conn_get_security(conn) >= BT_SECURITY_L4 &&
	       bt_gatt_is_subscribed(conn, READING_ATTR, BT_GATT_CCC_NOTIFY) &&
	       bt_gatt_get_mtu(conn) >= BLE_READING_LEN + 3 && /* 3 B of ATT header */
	       has_time; /* without time, the timestamp would be 0 and the app would deduplicate it */
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

		/* From the main thread, if there are no free buffers, bt_gatt_notify WAITS
		 * until one is released (the burst goes at the pace of the link). It returns an
		 * error if the connection drops: the reading stays in the buffer for next time. */
		if (bt_gatt_notify(conn, READING_ATTR, pkt, sizeof(pkt)) != 0) {
			break;
		}
		ring_count--;
		sent++;
	}
	bt_conn_unref(conn);

	if (sent > 0) {
		printk("  BLE: %d reading(s) sent, %d pending\n", sent, ring_count);
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

	printk("BLE: pairings deleted%s\n", err ? " (ERROR)" : "");
	list_bonds(); /* check: must be 0 */
}
