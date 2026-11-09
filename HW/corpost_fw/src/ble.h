/* BLE de CorPost: servicio GATT propio, seguridad (LE Secure Connections) y
 * búfer circular de lecturas para las desconexiones. */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "posture.h"

/* Tamaño del paquete de lectura (D3): 22 B de datos + 2 B de CRC-16 */
#define BLE_READING_LEN 24

/* Opcodes de la característica Command (D3) */
#define CMD_SET_INTERVAL  0x01 /* + uint16 LE: segundos */
#define CMD_SET_TOLERANCE 0x02 /* + uint8: grados */
#define CMD_RECALIBRATE   0x03 /* sin parámetro */
#define CMD_SET_VIBRATION 0x04 /* + uint8: 0 = off, 1 = on */

/* Acciones que la app puede pedir por la característica Command. Se llaman desde
  el hilo de Bluetooth: deben ser rápidas (solo guardar el valor o poner un flag). */
struct ble_cmd_handlers {
	void (*set_interval)(uint16_t seconds);
	void (*set_tolerance)(uint8_t degrees);
	void (*recalibrate)(void);
	void (*set_vibration)(bool on);
};

/* Arranca Bluetooth, carga los emparejamientos guardados y empieza a anunciarse. */
int ble_init(const struct ble_cmd_handlers *handlers);

/* Guarda una lectura en el búfer circular (se envía cuando el enlace esté listo). */
void ble_submit(const struct window_result *r, int64_t uptime_ms);

/* Envía todas las lecturas pendientes si el enlace está listo:
  conectado + cifrado y autenticado + suscrito + MTU suficiente + hora recibida.
  Devuelve cuántas se han enviado. */
int ble_flush(void);

/* Lecturas pendientes en el búfer */
int ble_pending(void);

/* Borra todos los emparejamientos (bonds) y corta la conexión actual. */
void ble_clear_bonds(void);

/* CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF): el CRC del paquete */
uint16_t ble_crc16(const uint8_t *data, int len);
