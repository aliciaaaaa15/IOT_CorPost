/* Parámetros del firmware de CorPost (PoC).
  Los valores de desarrollo se pueden ajustar según lo que se quiera probar;
  los valores definitivos se decidirán tras las pruebas. */
#pragma once

/* Muestreo: ventana de 2 s a 25 Hz (50 muestras), como en el D3 */
#define SAMPLE_PERIOD_MS     40
#define WINDOW_SAMPLES       50
#define MIN_VALID_SAMPLES    40   /* si se pierden más muestras por I2C, la ventana es INVALID */

/* Intervalo entre mediciones. Desarrollo: 15 s (D3: 1, 3 o 5 min).
  Es el valor inicial: la app lo puede cambiar con el comando 0x01. */
#define MEASURE_INTERVAL_S     15
#define MEASURE_INTERVAL_MIN_S 5    /* límites que acepta el comando 0x01 */
#define MEASURE_INTERVAL_MAX_S 3600

/* Margen de tolerancia: desviación respecto a la postura de referencia a partir
  de la cual la postura es BAD. Valor inicial: la app lo cambia con el comando 0x02. */
#define TOLERANCE_DEG        15.0f
#define TOLERANCE_MIN_DEG    1      /* límites que acepta el comando 0x02 */
#define TOLERANCE_MAX_DEG    90

/* Búfer circular de lecturas para las desconexiones BLE (D3: 50 lecturas) */
#define BUFFER_SIZE          50

/* Campo "batería" del paquete. El PoC no tiene batería (USB): 0xFF = no disponible */
#define BATTERY_LEVEL        0xFF

/* Filtro de movimiento PROVISIONAL: umbral sobre la desviación estándar del módulo
  de la aceleración en la ventana (0,042 g = baseline del pipeline con HAPT).
  Se sustituirá por el árbol de decisión reentrenado a 25 Hz. */
#define MOTION_STD_MG        42.0f

/* Vibración: mínimo tiempo entre dos avisos. Desarrollo: 0 (vibra en cada BAD).
  D3: 300 s (5 min). */
#define VIB_MIN_INTERVAL_S   0
