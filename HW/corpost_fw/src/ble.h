/* CorPost BLE: custom GATT service, security (LE Secure Connections) and a
 * circular reading buffer for disconnections. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "posture.h"

/* Reading packet size (D3): 22 B of data + 2 B of CRC-16 */
#define BLE_READING_LEN 24

/* Opcodes of the Command characteristic (D3) */
#define CMD_SET_INTERVAL  0x01 /* + uint16 LE: seconds */
#define CMD_SET_TOLERANCE 0x02 /* + uint8: degrees */
#define CMD_RECALIBRATE   0x03 /* no parameter */
#define CMD_SET_VIBRATION 0x04 /* + uint8: 0 = off, 1 = on */

/* Actions that the app can request through the Command characteristic. They are called from
  the Bluetooth thread: they must be fast (only store the value or set a flag). */
struct ble_cmd_handlers {
	void (*set_interval)(uint16_t seconds);
	void (*set_tolerance)(uint8_t degrees);
	void (*recalibrate)(void);
	void (*set_vibration)(bool on);
};

/* Start Bluetooth, load the stored pairings and start advertising. */
int ble_init(const struct ble_cmd_handlers *handlers);

/* Store a reading in the circular buffer (it is sent when the link is ready). */
void ble_submit(const struct window_result *r, int64_t uptime_ms);

/* Send all pending readings if the link is ready:
  connected + encrypted and authenticated + subscribed + enough MTU + time received.
  Returns how many have been sent. */
int ble_flush(void);

/* Readings pending in the buffer */
int ble_pending(void);

/* Delete all pairings (bonds) and drop the current connection. */
void ble_clear_bonds(void);

/* CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF): the packet CRC */
uint16_t ble_crc16(const uint8_t *data, int len);
