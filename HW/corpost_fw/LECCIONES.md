# Lecciones: el firmware de corpost_fw archivo por archivo

Recorrido didáctico por todo el código de `src/`, de lo más simple a lo que lo une todo:

1. `config.h` y `bno055.h`: parámetros e interfaz del sensor
2. `bno055.c`: el driver del sensor, la parte con más hardware
3. `vibro.h` / `vibro.c`: el actuador
4. `posture.h` / `posture.c`: la lógica (matemáticas)
5. `prj.conf` y `ble.h`: la configuración de Bluetooth y la interfaz del módulo BLE
6. `ble.c`: el servicio GATT, la seguridad y el búfer de lecturas
7. `main.c`: cómo se une todo

Cada lección acaba con unas preguntas de comprobación y sus respuestas.
- **Contexto general** (Zephyr, I²C, registros, TWIM y el historial de problemas de las pruebas): secciones 1-6 del [README](README.md).
- **Teoría de BLE** (GAP, GATT, MTU, seguridad): sección 7 del README. Las lecciones 5 y 6 dan esa teoría por leída y se centran en el código.

---

# Lección 1: `config.h` y `bno055.h`

## [config.h](src/config.h)

```c
#pragma once
```
Evita que el archivo se incluya dos veces en la misma compilación. Si `main.c` incluye `config.h` y también `posture.h`, que a su vez lo incluye, sin esto el compilador vería las definiciones dos veces. Es el equivalente moderno de los `#ifndef CONFIG_H / #define CONFIG_H / #endif` de C/C++.

```c
#define SAMPLE_PERIOD_MS     40
#define WINDOW_SAMPLES       50
```
`#define` no crea una variable: es una **sustitución de texto** que hace el preprocesador antes de compilar. Donde ponga `WINDOW_SAMPLES`, el compilador ve `50`. Se usa en vez de `const int` por dos motivos:
- **Sirve para tamaños de arrays globales.** En `main.c` está `static struct imu_sample win[WINDOW_SAMPLES];`. En C, a diferencia de C++, un `const int` no vale para eso.
- **No ocupa memoria:** es solo un número escrito en el código.

Relación entre los dos valores: 50 muestras × 40 ms = 2000 ms = **2 s de ventana**, y 1000 / 40 = **25 Hz**.

```c
#define MIN_VALID_SAMPLES    40
```
Si el bus falla, algunas muestras de la ventana se pierden. Con menos de 40 de 50 (80 %), la ventana se considera poco fiable y sale INVALID.

```c
#define TOLERANCE_DEG        15.0f
#define MOTION_STD_MG        42.0f
```
La **`f`** final hace que el número sea `float` y no `double`. Importa en un microcontrolador: el nRF52832 tiene una FPU que hace operaciones `float` en hardware, pero **no `double`**. Las operaciones con `double` se emulan por software y son mucho más lentas. Sin la `f`, una comparación como `angulo > 15.0` convertiría el `float` en `double` para comparar.

```c
#define MEASURE_INTERVAL_S   15
#define VIB_MIN_INTERVAL_S   0
```
Son enteros en segundos. En el código se multiplican por 1000, porque Zephyr trabaja en milisegundos.

```c
#define MEASURE_INTERVAL_MIN_S 5
#define MEASURE_INTERVAL_MAX_S 3600
#define TOLERANCE_MIN_DEG    1
#define TOLERANCE_MAX_DEG    90
```
- **El intervalo y la tolerancia ahora los puede cambiar la app por BLE.** `MEASURE_INTERVAL_S` y `TOLERANCE_DEG` pasan a ser los valores **iniciales**, los que se usan al arrancar.
- **Los `_MIN` / `_MAX` son los límites que acepta el firmware.** Si la app envía un valor fuera de rango, el comando se rechaza con un error. Es **validar la entrada**: nunca hay que fiarse de lo que llega desde fuera, aunque sea nuestra propia app. Un intervalo de 0 s, por ejemplo, haría que el dispositivo midiera sin parar.

```c
#define BUFFER_SIZE          50
#define BATTERY_LEVEL        0xFF
```
- **`BUFFER_SIZE`:** cuántas lecturas se guardan mientras no hay conexión (D3: 50).
- **`BATTERY_LEVEL`:** el valor fijo del campo "batería" del paquete BLE. El PoC no tiene batería, así que se envía 0xFF (255), que la app interpreta como "no disponible". Un 0 o un 100 serían engañosos: parecerían una medida real.

## [bno055.h](src/bno055.h)

Es la **interfaz pública** del sensor: lo que otros archivos pueden usar. La implementación está en `bno055.c`. La idea es la de una clase en C++: el `.h` es la parte `public`, y lo `static` del `.c` es la parte `private`.

```c
#include <zephyr/device.h>
#include <stdint.h>
```
- `zephyr/device.h` define `struct device`, el tipo con el que Zephyr representa cualquier periférico (un bus I²C, un GPIO…).
- `stdint.h` define tipos de **tamaño fijo**: `int16_t` (16 bits con signo), `uint8_t` (8 bits sin signo), `uint32_t`… En hardware se usan siempre porque el tamaño de `int` depende de la plataforma, y un registro del sensor mide exactamente 8 o 16 bits.

```c
struct imu_sample {
	int16_t acc[3]; /* mg, incluye la gravedad */
	int16_t gyr[3]; /* 1 LSB = 1/16 dps */
};
```
Una muestra son 6 números: aceleración X, Y, Z y giro X, Y, Z. Se usa `int16_t` porque es **exactamente lo que da el sensor**: cada eje son 2 registros de 8 bits que forman un entero de 16 bits con signo. Una muestra ocupa 12 bytes, y la ventana entera (50 muestras) 600 bytes de los 64 KB de RAM.

Las unidades van en el comentario porque el número en sí no dice nada:
- **Aceleración:** configuramos el sensor para que 1 = 1 mg (milésima de g). Quieto y plano, el eje vertical da unos 1000.
- **Giro:** 1 = 1/16 °/s, así que 160 significa 10 °/s. Es la escala fija del BNO055 en °/s.

`struct imu_sample` en C se escribe siempre con la palabra `struct` delante. En C++ bastaría con `imu_sample`.

```c
struct bno055_stats {
	uint32_t retries;
	uint32_t mismatches;
	uint32_t failed;
};
```
Son los contadores de las líneas `bus: perdidas=… reintentos=… discrepancias=…` del log. Sirven para **medir** lo fiable que es el bus, no para que funcione.

```c
int bno055_init(const struct device *i2c);
```
Recibe un **puntero al bus I²C**. El sensor no "posee" el bus: se lo pasa `main.c`, porque el mismo bus lo comparte con el Vibro. Esto se llama inyección de dependencias.

El `const` significa que la función no modifica el `struct device`. Devuelve `int`: 0 si todo ha ido bien y negativo si hay error. En Zephyr no hay excepciones.

```c
int bno055_read(struct imu_sample *s);
```
La muestra se devuelve **por puntero de salida**, y el `int` de retorno queda libre para el código de error. Es el patrón habitual en C, porque una función no puede devolver "un valor o un error" a la vez.

```c
uint8_t bno055_addr(void);
const struct bno055_stats *bno055_get_stats(void);
```
- **`(void)`:** en C, una función sin parámetros se declara con `(void)`. `()` vacío significaría "parámetros sin especificar", un resto histórico del lenguaje. En C++ ambas formas son iguales.
- **`bno055_addr`:** devuelve la dirección I²C encontrada (0x28 o 0x29), para imprimirla.
- **`bno055_get_stats`:** devuelve un **puntero a `const`** a los contadores internos. Quien llama puede leerlos pero no modificarlos. Es como un *getter* que devuelve una referencia constante.

## Preguntas de comprobación

1. Si cambias `SAMPLE_PERIOD_MS` a 20 y dejas `WINDOW_SAMPLES` en 50, ¿qué frecuencia de muestreo y qué duración de ventana tendrías?
2. ¿Por qué `bno055_read` no devuelve directamente un `struct imu_sample`?
3. Con la placa quieta y plana, ¿qué valores esperarías en `acc[0]`, `acc[1]` y `acc[2]` si el eje Z apunta hacia arriba?

### Respuestas

1. 1000 / 20 = **50 Hz**, y la ventana dura 50 × 20 ms = **1 s**.
2. Porque el valor de retorno se reserva para el **código de error**; la muestra sale por el puntero.
3. **acc[0] ≈ 0, acc[1] ≈ 0, acc[2] ≈ +1000 mg.** Quieto, solo se mide la gravedad, y el acelerómetro la ve como +1 g en el eje que apunta hacia arriba. Es poco intuitivo; tiene que ver con cómo mide el sensor.

---

# Lección 2: [bno055.c](src/bno055.c), el driver del sensor

Es el archivo con más "hardware". Lo divido en cinco bloques.

## Bloque 1: includes (líneas 1-8)

| Include | Para qué |
|---|---|
| `"bno055.h"` | Nuestra propia interfaz. Las comillas significan "busca en mi proyecto"; los `< >`, "busca en las librerías del sistema" |
| `zephyr/kernel.h` | `k_msleep` (esperas) |
| `zephyr/drivers/i2c.h` | `i2c_write`, `i2c_write_read`, `i2c_reg_read_byte` |
| `zephyr/sys/byteorder.h` | `sys_get_le16` (unir LSB + MSB) |
| `zephyr/sys/util.h` | `ARRAY_SIZE` |
| `errno.h` | Los códigos de error `EIO`, `ENODEV` |
| `stdlib.h` | `abs` |

## Bloque 2: el mapa de registros (líneas 10-27)

Estos `#define` son **nombres para direcciones y valores sacados del datasheet** del BNO055. El código funcionaría con los números tal cual (`wr(0x3D, 0x05)`), pero sería ilegible.

**Las páginas.** El BNO055 tiene más registros de los que caben en 256 direcciones, así que los organiza en dos **páginas**. El registro `PAGE_ID` (0x07) dice cuál está activa. Por eso `REG_ACC_DATA` y `REG_ACC_CONFIG` comparten la dirección **0x08**: la primera es de la página 0 y la segunda de la página 1. Según la página activa, 0x08 significa una cosa u otra.

**Los registros de datos, a partir de 0x08:**
```
0x08 ACC_X_LSB   0x09 ACC_X_MSB
0x0A ACC_Y_LSB   0x0B ACC_Y_MSB
0x0C ACC_Z_LSB   0x0D ACC_Z_MSB
0x0E-0x13  magnetómetro (no lo usamos)
0x14 GYR_X_LSB   0x15 GYR_X_MSB   ... hasta 0x19
```
Por eso el eje `i` de la aceleración está en `0x08 + 2*i` y el del giro en `0x14 + 2*i`.

**Los valores de configuración se construyen bit a bit.** Un registro de 8 bits suele guardar varios ajustes a la vez, cada uno en unos bits concretos:

```
ACC_CFG = 0x05 = 0b 000 001 01
                    │   │   └─ bits 1:0 = 01  → rango ±4 g
                    │   └───── bits 4:2 = 001 → filtro 15,63 Hz
                    └───────── bits 7:5 = 000 → modo de energía normal

GYR_CFG = 0x28 = 0b 00 101 000
                       │   └─ bits 2:0 = 000 → rango ±2000 °/s
                       └───── bits 5:3 = 101 → filtro 12 Hz
```
Los significados de cada combinación salen de las tablas del datasheet. Esta forma de empaquetar ajustes en bits es muy habitual en hardware.

## Bloque 3: estado privado (líneas 35-37)

```c
static const struct device *bus;
static uint8_t addr;
static struct bno055_stats stats;
```
Son variables **globales del archivo** y **privadas** por el `static`: ningún otro `.c` puede verlas. Juntas son el "estado del objeto". En C++ serían los miembros privados de una clase `Bno055`. La diferencia es que aquí solo hay **una instancia**: si tuviéramos dos sensores, este diseño no serviría tal cual.

Las variables globales en C empiezan a **cero** automáticamente, así que `stats` arranca con todos los contadores a 0.

Lo que sí se puede hacer desde fuera es pedirle a `bno055_get_stats()` un puntero a `stats`.

## Bloque 4: las funciones de acceso al bus (líneas 39-77)

### `wr`: escribir un registro
```c
uint8_t buf[2] = {reg, val};
return i2c_write(bus, buf, sizeof(buf), addr);
```
En el cable se envía la dirección del dispositivo (`addr`), seguida de 2 bytes: **qué registro** y **qué valor**. El BNO055 entiende "el primer byte es la dirección del registro y el siguiente es lo que hay que guardar ahí".

### `read_i16_once`: leer un eje (2 bytes)
```c
err = i2c_write_read(bus, addr, &reg, 1, b, 2);
```
Es la operación de lectura descrita en el README, en una sola transacción:
1. **Escribe 1 byte** (`&reg`, `1`): "me interesa el registro `reg`".
2. Sin liberar el bus (*repeated start*), **lee 2 bytes** en `b`: el sensor devuelve `reg` y `reg+1`, es decir, LSB y MSB.

`&reg` es la dirección de la variable `reg`, porque la función espera un *buffer*. Aquí el buffer es de un solo byte.

**Por qué los 2 bytes van en la misma transacción.** Si se leyeran LSB y MSB por separado, el sensor podría actualizar el dato entre ambas lecturas, y obtendrías el LSB de una medida con el MSB de otra. Es un valor "roto" que puede estar muy lejos del real.

**Reintentos.** Si el bus da error (`err != 0`, típicamente −5 por un NACK), suma 1 a `stats.retries` y lo vuelve a intentar, hasta `READ_RETRIES` (3) veces. Si la lectura va bien, `sys_get_le16(b)` une los bytes (`b[0] | b[1] << 8`) y lo escribe en `*out`.

### `read_i16`: la doble lectura de verificación
```c
if (read_i16_once(reg, &a) || read_i16_once(reg, &b)) {
	return -EIO;
}
if (abs(a - b) <= MAX_DIFF) { *out = b; return 0; }
stats.mismatches++;
```
- **Lee el mismo eje dos veces seguidas** (con menos de 1 ms entre ambas).
- **El `||` hace evaluación en cortocircuito:** si la primera lectura falla (devuelve distinto de 0, que cuenta como `true`), ni siquiera intenta la segunda y devuelve error.
- **Si las dos lecturas se parecen** (diferencia ≤ 200), el dato se da por bueno. Si no, se cuenta una discrepancia y se repite la pareja, hasta 3 veces.

**Por qué funciona:** un byte corrupto (por ejemplo, un MSB leído como `0xFF`) da diferencias de cientos o miles de unidades. En cambio, el valor real casi no cambia en menos de 1 ms. Es improbable que la misma corrupción aparezca dos veces seguidas igual.

**Su limitación:** con movimientos muy bruscos, el sensor puede actualizar el dato justo entre las dos lecturas y dar una discrepancia "falsa". No es grave: se reintenta, y si al final se pierde la muestra, en movimiento la ventana iba a salir INVALID igualmente.

`abs` necesita `<stdlib.h>`. `a - b` se calcula en `int`, así que no hay desbordamiento aunque sean `int16_t`.

**En el peor caso,** un eje puede costar 3 parejas × 2 lecturas × 3 reintentos = 18 transacciones. Normalmente es 1 pareja = 2 transacciones.

## Bloque 5: las funciones públicas (líneas 79-133)

### `bno055_init`

**1. Buscar el sensor (líneas 81-96)**
```c
static const uint8_t cand[] = {0x28, 0x29};
```
Las dos direcciones posibles del BNO055. Depende de cómo esté cableado un pin del chip; en nuestra placa es 0x29.
- El `static const` dentro de una función hace que el array se guarde **en flash**, una sola vez, en lugar de crearse en la pila en cada llamada.
- `ARRAY_SIZE(cand)` calcula cuántos elementos tiene el array (`sizeof(cand) / sizeof(cand[0])`).

```c
if (i2c_reg_read_byte(bus, cand[i], REG_CHIP_ID, &id) == 0 && id == CHIP_ID)
```
Lee el registro 0x00 en cada dirección candidata. No basta con que alguien conteste: tiene que contestar **`0xA0`**, el identificador fijo del BNO055. Así se evita confundirlo con otro chip que usara esa dirección.

Si ninguna dirección responde así, devuelve `-ENODEV` ("no existe el dispositivo").

**2. Configurar (líneas 98-108)**

El orden importa:

| Línea | Escribe | Por qué |
|---|---|---|
| 98 | `OPR_MODE = CONFIG` | El BNO055 **solo acepta cambios de configuración en modo CONFIG** |
| 99 | espera 25 ms | El chip tarda unos ms en cambiar de modo (el datasheet da unos 7 ms al entrar en CONFIG y unos 19 ms al salir). Se deja margen |
| 100 | `PWR_MODE = 0` | Modo de energía normal, sin suspensión |
| 101 | `UNIT_SEL = 0x01` | Bit 0 = 1: aceleración en **mg** (por defecto sería m/s²). Bit 1 = 0: giro en **°/s** |
| 102 | `SYS_TRIG = 0` | Usa el oscilador interno del chip |
| 103 | `PAGE_ID = 1` | Pasa a la página 1 |
| 104-105 | `ACC_CONFIG`, `GYR_CONFIG0` | Rangos y filtros internos (el desglose bit a bit del bloque 2) |
| 106 | `PAGE_ID = 0` | Vuelve a la página 0, donde están los datos. **Si se olvida,** las lecturas de 0x08 leerían la configuración en vez de la aceleración |
| 107-108 | `OPR_MODE = ACCGYRO`, espera | Empieza a medir |

**`err |= wr(...)`** acumula los errores con un OR de bits. Si todas las escrituras devuelven 0, `err` sigue siendo 0; si alguna devuelve −5, `err` deja de ser 0. Al final, `err ? -EIO : 0` devuelve un error único y limpio. Es más corto que comprobar cada línea, a cambio de no saber **cuál** falló.

### `bno055_read`
```c
for (int i = 0; i < 3; i++) {
	if (read_i16(REG_ACC_DATA + 2 * i, &s->acc[i]) ||
	    read_i16(REG_GYR_DATA + 2 * i, &s->gyr[i])) {
```
- Para cada eje (X, Y, Z) lee la aceleración y el giro.
- `s->acc[i]` es el campo `acc[i]` del struct al que apunta `s`; `&s->acc[i]` es su dirección, para que `read_i16` escriba ahí.
- Si **cualquiera** de los 6 ejes falla, la muestra entera se descarta (`stats.failed++`). Una muestra con 5 ejes buenos y 1 malo no sirve.

El orden de lectura es intercalado (acc X, gyr X, acc Y…), así que entre el primer y el último eje pasan unos milisegundos. A 25 Hz no importa.

### `bno055_addr` y `bno055_get_stats`
Son *getters*. `&stats` devuelve la dirección de la variable privada. Como el tipo de retorno es `const`, quien llama no puede modificarla a través de ese puntero.

## Preguntas de comprobación

1. ¿Qué pasaría si quitaras la línea 106 (`wr(REG_PAGE_ID, 0)`)?
2. Si quisieras el acelerómetro en rango **±2 g** con el mismo filtro de 15,63 Hz, ¿qué valor pondrías en `ACC_CFG`? Pista: en el datasheet, ±2 g corresponde a `00` en los bits 1:0.
3. ¿Por qué la verificación de `read_i16` compara dos lecturas en vez de, por ejemplo, comprobar que el valor esté dentro de ±4000 mg?

### Respuestas

1. **El chip se quedaría en la página 1.** Al leer 0x08 obtendrías `ACC_CONFIG` en lugar de la aceleración, así que todas las lecturas serían basura con valores fijos.
2. **`0b000_001_00` = `0x04`.**
3. **Un byte corrupto puede dar un valor dentro del rango y aun así ser falso.** Por ejemplo, −116 mg corrompido a −2164 mg sigue dentro de ±4000. Comparar dos lecturas detecta la corrupción aunque el valor resultante sea "posible".

---

# Lección 3: `vibro.h` y `vibro.c`, el actuador

## La gran diferencia con el BNO055

El BNO055 se maneja con **registros**: lees y escribes en direcciones con un significado fijo. El Modulino Vibro funciona de otra forma: lleva **su propio microcontrolador** (un pequeño STM32) que controla el motor. Nosotros no tocamos el motor; le enviamos una **orden** y su firmware la interpreta. Es como llamar a una API: el formato del mensaje lo define quien programó el Modulino, no un estándar.

Por eso no hay mapa de registros, solo un mensaje de **12 bytes**: frecuencia, duración y potencia. Es el formato que ya usaba `vibro_test`, que funcionó. El significado exacto de "frecuencia" depende del firmware del Modulino; con 1000 vibra bien y no lo hemos explorado más.

## [vibro.h](src/vibro.h)

```c
#define VIBRO_ADDR 0x38
```
La dirección I²C del Vibro. Está en el `.h`, y no en el `.c`, porque `main.c` la usa para imprimir mensajes.

Las tres funciones siguen el mismo patrón que el sensor: devuelven `int`, con 0 si todo va bien y negativo si hay error.

## [vibro.c](src/vibro.c)

### Estado privado (línea 7)
```c
static const struct device *bus;
```
Solo guarda el bus, porque la dirección es fija (0x38). Es **el mismo bus** que usa el BNO055: los dos módulos reciben el mismo puntero desde `main.c`. Cada transacción I²C lleva la dirección del destinatario, así que no se pisan.

### `vibro_init`: comprobar que está (líneas 9-15)
```c
uint8_t dummy;
bus = i2c;
return i2c_read(bus, &dummy, 1, VIBRO_ADDR);
```
- Lee 1 byte de la dirección 0x38 y descarta el contenido (`dummy` = "de relleno"). No importa qué devuelva: lo que interesa es si **contesta con ACK**.
- Si nadie está en 0x38, el bus da NACK y la función devuelve −5. Es exactamente lo que hace el escaneo del bus en `main.c`, pero con una sola dirección.
- Es lo que pasaba en las primeras pruebas con `vibro_test`: el Vibro estaba desconectado y todas las escrituras devolvían −5.

### `vibro_pulse`: enviar la orden (líneas 18-35)

**1. Construir el mensaje (líneas 20-25)**
```c
uint8_t buf[12];
sys_put_le32(freq, &buf[0]);
sys_put_le32(ms,   &buf[4]);
sys_put_le32(power,&buf[8]);
```
`sys_put_le32` es la operación inversa de `sys_get_le16` del sensor: **descompone** un entero de 32 bits en 4 bytes, en orden little-endian (primero el byte bajo). Por ejemplo, `vibro_pulse(1000, 300, 80)` genera:

```
freq = 1000  = 0x000003E8  →  E8 03 00 00    (buf[0..3])
ms   = 300   = 0x0000012C  →  2C 01 00 00    (buf[4..7])
power= 80    = 0x00000050  →  50 00 00 00    (buf[8..11])
```

**Por qué no se hace `memcpy(buf, &freq, 4)`:** funcionaría en el nRF52832, porque también es little-endian, pero depende del procesador. `sys_put_le32` garantiza el orden de bytes sea cual sea la plataforma. Es buena práctica en cualquier protocolo binario, y la usaremos igual al construir el paquete BLE.

**2. Enviarlo con reintentos (líneas 28-34)**
```c
for (int i = 0; i < 3; i++) {
	err = i2c_write(bus, buf, sizeof(buf), VIBRO_ADDR);
	if (err == 0) break;
}
```
- Aquí no hay registro de destino: los 12 bytes son la orden entera.
- Reintenta hasta 3 veces por los fallos del bus que vimos con los cables largos.
- **No hace falta doble verificación como en el sensor:** aquí escribimos en vez de leer, y si la escritura llega mal el Vibro responde con NACK y nos enteramos.
- **Reintentar es seguro:** si por un fallo el Vibro recibiera la orden dos veces, simplemente reinicia el mismo pulso. Esta propiedad (repetir una orden no cambia el resultado) se llama **idempotencia**, y es la misma idea que la deduplicación de lecturas del D3.

**No bloquea.** La función vuelve en cuanto el Vibro recibe la orden, en menos de 1 ms. El Vibro vibra los 300 ms por su cuenta mientras el nRF sigue a lo suyo.

### `vibro_alert`: el aviso de mala postura (líneas 37-45)
```c
int err = vibro_pulse(1000, 300, 80);
k_msleep(500);
err |= vibro_pulse(1000, 300, 80);
k_msleep(300);
```
Así queda la secuencia en el tiempo:
```
t=0     pulso 1 ███████████ (300 ms)
t=300   pausa   ......      (200 ms)
t=500   pulso 2 ███████████ (300 ms)
t=800   la función vuelve
```
- **La espera de 500 ms es necesaria** porque `vibro_pulse` no bloquea. Sin ella, el segundo pulso llegaría mientras el primero aún vibra y lo reiniciaría, y se notaría **un solo pulso largo**. 500 ms = 300 ms de vibración + 200 ms de pausa.
- **El `k_msleep(300)` final** hace que la función solo vuelva cuando ha terminado de vibrar, para que nada en `main.c` empiece mientras vibra. Por eso bloquea unos 0,8 s.
- **`err |=`** es el mismo patrón que en el sensor: si cualquiera de los dos pulsos falla, se devuelve error.

El comentario del `.h` dice "~1 s en total", pero en realidad son unos 0,8 s.

**¿Afectan estos 0,8 s al BLE?** Antes de añadirlo era una duda; ahora sabemos que no:
- La radio la gestiona el controlador de Nordic con sus propias interrupciones, de mayor prioridad que nuestro código. Las citas de la conexión se cumplen aunque `main` esté dormido en `vibro_alert`.
- Los comandos de la app los recibe el **hilo de Bluetooth**, no el principal (lección 6).
- Lo único que se retrasa como mucho 0,8 s es el envío de la lectura, que se hace justo después de vibrar.

Si algún día molestara, la solución sería un *timer* de Zephyr que lance el segundo pulso sin bloquear.

## Preguntas de comprobación

1. ¿Qué 12 bytes enviaría `vibro_pulse(500, 1000, 50)`?
2. Si cambias el `k_msleep(500)` por `k_msleep(100)`, ¿qué notaría el usuario?
3. Si el Vibro se desconecta con el programa en marcha, ¿qué devuelve `vibro_alert` y qué hace `main.c` con ese error? Pista: busca `vibro_alert` en `main.c`.

### Respuestas

1. 500 = 0x1F4 → `F4 01 00 00`; 1000 = 0x3E8 → `E8 03 00 00`; 50 = 0x32 → `32 00 00 00`.
2. **Notaría un solo pulso largo en vez de dos.** El segundo pulso llegaría a los 100 ms, cuando el primero aún está vibrando, y probablemente lo reiniciaría: unos 400 ms seguidos. Lo exacto depende del firmware del Modulino.
3. **Devuelve −5, porque los dos `vibro_pulse` fallan.** `main.c` imprime `-> vibracion (ERROR I2C)` y sigue funcionando con normalidad; el programa no se cuelga.

---

# Lección 4: `posture.h` y `posture.c`, la lógica (matemáticas)

## La idea física: la gravedad dice la orientación

Un acelerómetro **quieto** no mide 0. Mide la gravedad: **1 g ≈ 1000 mg**, y la ve "hacia arriba". En el log de calibración salió `x=1,6 y=−80,4 z=1007,5`: casi todo en Z, porque la placa estaba casi plana, con una pequeña inclinación en Y.

Si inclinas el sensor, esos 1000 mg se reparten entre los ejes. El **vector** (x, y, z) apunta siempre en la dirección de la gravedad, pero vista desde el sensor. Así que:
- **Calibrar** = guardar ese vector cuando la postura es correcta.
- **Medir la postura** = calcular el **ángulo** entre el vector actual y el guardado.

Hay un **requisito**: esto solo funciona **quieto**. Si el usuario se mueve, el acelerómetro suma la aceleración del movimiento a la gravedad y el vector ya no indica solo "abajo". Por eso existe el filtro de movimiento.

## [posture.h](src/posture.h)

```c
enum posture_status {
	POSTURE_OK = 0,
	POSTURE_BAD = 1,
	POSTURE_INVALID = 2,
};
```
Un `enum` da nombres a números. Los valores se fijan explícitamente (0, 1, 2), y no se deja que el compilador los asigne, porque **deben coincidir con el campo "status" del paquete BLE** del D3 (00 = OK, 01 = BAD, 10 = INVALID). Así, `ble.c` mete `r.status` directamente en el byte 16 del paquete, sin traducir (lección 6).

```c
struct window_result {
	int n_valid;
	float acc_mean[3];
	float gyr_mean_dps[3];
	float amag_std_mg;
	float angle_deg;
	enum posture_status status;
};
```
Todo lo que se calcula de una ventana. Dos detalles:
- **`gyr_mean_dps` no se usa para decidir la postura**, pero sí se envía: el paquete BLE incluye la velocidad angular media de la ventana.
- **`angle_deg` solo tiene sentido si el estado no es INVALID.** En el paquete, un INVALID se envía con ángulo 0.

```c
void posture_set_tolerance(float deg);
```
Permite cambiar la tolerancia mientras el programa corre. La llama `main.c` cuando la app envía el comando 0x02.

```c
void posture_eval(const struct imu_sample *s, const bool *ok, int n, struct window_result *r);
```
Recibe dos arrays "paralelos" de la misma longitud: `s[i]` es la muestra i y `ok[i]` dice si esa muestra se leyó bien. Se usa `bool` porque es un sí/no; en C hay que incluir `<stdbool.h>`, mientras que en C++ viene de serie.

Los `const` indican que la función solo lee las muestras, no las modifica. El resultado sale por el puntero `r`, igual que en `bno055_read`.

## [posture.c](src/posture.c)

### Constantes y estado (líneas 7-15)
```c
#define RAD2DEG 57.29577951f
static float ref[3] = {0.0f, 0.0f, 1000.0f};
static volatile float tolerance_deg = TOLERANCE_DEG;

void posture_set_tolerance(float deg)
{
	tolerance_deg = deg;
}
```
- **`RAD2DEG`** es 180/π: `acosf` devuelve radianes y los queremos en grados.
- **`ref`** es la postura de referencia, privada del archivo (`static`). Empieza en (0, 0, 1000), "plano con Z hacia arriba", pero es solo un valor por defecto: `main.c` siempre calibra antes de medir.
- **`tolerance_deg`** sustituye a la constante `TOLERANCE_DEG`, que ahora solo da el valor inicial. Es `volatile` porque la escribe **otro hilo**: el comando llega por el hilo de Bluetooth y la lee el hilo principal en `posture_eval`. Por qué no hace falta un *lock* (mutex o spinlock):
  - un `float` son 32 bits, y el Cortex-M4 lee y escribe 32 bits alineados en **una sola instrucción**, así que nunca se puede leer "medio valor";
  - en el peor caso, una ventana se evalúa con la tolerancia anterior, y la siguiente ya usa la nueva. El D3 dice precisamente que la configuración "se aplica desde el siguiente ciclo".

  En la lección 6 hay un caso donde **sí** hace falta un *lock*: un valor de 64 bits.

### `norm3`: el módulo de un vector (líneas 17-20)
```c
return sqrtf(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
```
Es Pitágoras en 3D: `|v| = √(x² + y² + z²)`. Quieto, el módulo de la aceleración es ≈ 1000 mg sea cual sea la orientación, porque la gravedad es la misma, solo repartida entre los ejes.

Se usa `sqrtf` y no `sqrt`: la `f` es la versión `float`, que la FPU hace en hardware (lo que vimos en la lección 1).

### `angle_between`: el ángulo entre dos vectores (líneas 22-33)

Usa el **producto escalar**:

```
a · b = |a| · |b| · cos θ     →     θ = acos( (a · b) / (|a| · |b|) )
```
con `a · b = ax·bx + ay·by + az·bz`.

```c
if (na < 1e-3f || nb < 1e-3f) return 0.0f;
```
**Protege contra la división por cero.** Si un vector fuera (0, 0, 0), no tiene dirección y el ángulo no existe. Físicamente no debería ocurrir: sería caída libre, o un fallo grave del sensor.

```c
c = c > 1.0f ? 1.0f : (c < -1.0f ? -1.0f : c);
```
**Limita el coseno a [−1, 1].** Matemáticamente nunca sale de ese rango, pero con redondeos de `float` podría salir 1,0000001, y `acosf` devolvería **NaN** ("no es un número"). Un NaN haría que todas las comparaciones siguientes dieran `false` en silencio. Es un fallo típico y muy difícil de encontrar.

**Ejemplo con datos reales de la prueba:** la referencia fue (324, −774, 526). Al inclinar el sensor se midieron 39-60°. Con los vectores de la calibración y de la ventana BAD, esta función da el ángulo entre ambos.

**Dos limitaciones importantes de este método:**
1. **El ángulo es la desviación total en 3D, sin dirección.** 20° hacia delante y 20° de lado dan lo mismo. Para CorPost basta, porque el D3 solo compara con una tolerancia.
2. **No detecta giros alrededor del eje vertical.** Si giras en una silla giratoria manteniendo la postura, la gravedad no cambia respecto al sensor, así que el ángulo sigue en 0. Tampoco hace falta: girar en la silla no es mala postura.

### `posture_window_stats`: estadísticas de la ventana (líneas 35-66)

**Reset (línea 39):**
```c
*r = (struct window_result){0};
```
Pone todos los campos del resultado a cero. `(struct window_result){0}` es un "literal compuesto": crea un struct temporal con todo a cero y lo copia en `*r`. Es imprescindible, porque luego se **suma** sobre `r->acc_mean`: si tuviera basura de antes, las medias saldrían mal.

**Bucle sobre las muestras (líneas 40-54):**
```c
if (!ok[i]) continue;
```
Salta las muestras perdidas por errores del bus. Por eso se cuenta `n_valid` y no se divide simplemente entre 50.

```c
float a[3] = {s[i].acc[0], s[i].acc[1], s[i].acc[2]};
```
Convierte los `int16_t` del sensor a `float`, para no perder decimales en las medias y poder usar `norm3`.

```c
r->acc_mean[k] += a[k];
r->gyr_mean_dps[k] += s[i].gyr[k] / 16.0f;
sum_mag += m;
sum_mag2 += m * m;
```
- **Acumula para las medias.** El giro se pasa a °/s dividiendo entre 16, la escala del sensor.
- **Acumula el módulo y su cuadrado,** para la desviación estándar.

**Medias (líneas 58-61):** se divide lo acumulado entre `n_valid`. La guarda `if (r->n_valid == 0) return;` evita dividir entre cero si se perdieron todas las muestras.

**Desviación estándar del módulo (líneas 62-65):**
```c
float mean = sum_mag / r->n_valid;
float var  = sum_mag2 / r->n_valid - mean * mean;
r->amag_std_mg = var > 0.0f ? sqrtf(var) : 0.0f;
```
Usa la fórmula `Var(m) = E[m²] − (E[m])²`, "la media de los cuadrados menos el cuadrado de la media". La ventaja es que permite calcularla **en una sola pasada**, sin recorrer la ventana dos veces.

**Su punto débil numérico:** con m ≈ 1000, m² ≈ 1.000.000. Un `float` tiene unos 7 dígitos de precisión, así que se restan dos números casi iguales de un millón. El resultado es poco preciso cuando la desviación es muy pequeña: en reposo, el 0,6 mg del log no es exacto. Por eso existe el `var > 0.0f ?`: por redondeo, la varianza podría salir ligeramente **negativa**, y `sqrtf` de un negativo da NaN.

Para nuestro uso no importa, porque el umbral es 42 mg, muy por encima de esa imprecisión. Si algún día hiciera falta más precisión, se usaría el algoritmo de Welford o se calcularía en dos pasadas.

**Por qué el módulo detecta movimiento:**
- Quieto, `|a|` es siempre ≈ 1000 mg, gire como gire el sensor, así que su desviación es casi 0.
- En movimiento, la aceleración del propio movimiento hace subir y bajar `|a|`, y la desviación crece. En la prueba, 145-235 mg agitándolo, frente a 0,6-2,3 en reposo.
- Usar el **módulo** en vez de cada eje hace que el filtro sea **independiente de la orientación**. Es la misma idea que usa el pipeline del árbol de decisión.

### `posture_set_reference` (líneas 68-73)
Copia el vector medio de la calibración en `ref`. En C los arrays no se pueden asignar con `=` (`ref = acc_mean` no compila), por eso el bucle.

### `posture_eval`: la decisión (líneas 75-86)
```c
posture_window_stats(s, ok, n, r);

if (r->n_valid < MIN_VALID_SAMPLES || r->amag_std_mg > MOTION_STD_MG) {
	r->status = POSTURE_INVALID;
	return;
}
r->angle_deg = angle_between(r->acc_mean, ref);
r->status = r->angle_deg > tolerance_deg ? POSTURE_BAD : POSTURE_OK;
```
1. Calcula las estadísticas.
2. **Primero decide si la ventana es fiable:** si faltan muestras o hay movimiento, es **INVALID** y sale **sin calcular el ángulo**. En ese caso `angle_deg` queda a 0 por el reset, y `main.c` no lo imprime. Este `if` es el que se sustituirá por el árbol de decisión.
3. Solo si es fiable, calcula el ángulo y lo compara con la tolerancia (`tolerance_deg`, 15° al arrancar): **BAD** u **OK**.

### `posture_status_str` (líneas 88-98)
Convierte el enum en texto para el log. Devuelve `const char *` a textos literales, que viven en flash y no se pueden modificar.

El `default` cubre `POSTURE_INVALID` y cualquier valor inesperado, para que la función siempre devuelva algo.

## Preguntas de comprobación

1. Si la referencia es (0, 0, 1000) y la ventana da (1000, 0, 0), ¿qué ángulo devuelve `angle_between`? ¿Y si da (0, 0, −1000)?
2. Un usuario gira en su silla giratoria manteniendo la espalda recta. ¿Qué estado sale (suponiendo que está quieto durante la ventana) y por qué?
3. ¿Por qué `posture_eval` comprueba el movimiento **antes** de calcular el ángulo, y no al revés?

### Respuestas

1. **(1000, 0, 0) frente a (0, 0, 1000) da 90°**, porque los vectores son perpendiculares y el producto escalar es 0. **(0, 0, −1000) da 180°**: el sensor está boca abajo.
2. **OK.** Girar alrededor del eje vertical no cambia la dirección de la gravedad vista desde el sensor, así que el ángulo sigue cerca de 0.
3. **En movimiento, el vector medio ya no es solo la gravedad**, porque se le suma la aceleración del movimiento. El ángulo calculado sería falso y podría provocar vibraciones injustificadas. Por eso primero se descarta, y solo se mide si es fiable.

---

# Lección 5: [prj.conf](prj.conf) y [ble.h](src/ble.h), configuración e interfaz del BLE

## Antes del código: quién hace qué en la pila Bluetooth

BLE no se programa "a mano" byte a byte. Casi todo lo hace software que ya existe, y nuestro código solo se ocupa de la parte de CorPost:

| Pieza | Qué hace | Quién la escribe |
|---|---|---|
| **SoftDevice Controller** | La parte de tiempo real (*Link Layer*): enciende la radio en el instante exacto, salta de canal, reenvía los paquetes perdidos y cifra con AES-CCM | Nordic (librería ya compilada) |
| **Host Bluetooth de Zephyr** | L2CAP, ATT, GATT, GAP y SMP: descubrimiento de servicios, permisos, emparejamiento, MTU, guardar los bonds… | Zephyr |
| **[ble.c](src/ble.c)** | Define el servicio de CorPost, decide qué enviar y cuándo, y reacciona a los eventos | Nosotros |

Nuestro código habla con el host de dos formas:
- **Llamando a funciones** `bt_...` (`bt_enable`, `bt_gatt_notify`, `bt_le_adv_start`…).
- **Recibiendo *callbacks*:** funciones nuestras que el host llama cuando pasa algo (se conecta un móvil, llega una escritura, termina el emparejamiento…).

**Lo más importante: esos *callbacks* no se ejecutan en el hilo de `main`.** Ahora hay varios hilos:

| Hilo | Qué ejecuta |
|---|---|
| `main` (prioridad 0) | Nuestro bucle: medir, vibrar, `ble_submit`, `ble_flush` |
| **BT RX** (el hilo de recepción de Bluetooth, prioridad 8) | Los *callbacks* de conexión, seguridad y escrituras GATT de `ble.c`, y desde ahí las funciones `cmd_*` de `main.c` |
| **System workqueue** (cola de trabajo del sistema, prioridad −1) | Tareas diferidas, como arrancar el advertising (`adv_work_handler`) |
| Interrupciones | Los botones y, con máxima prioridad, la radio (controlador de Nordic) |

En Zephyr, **un número de prioridad menor significa más prioridad**: el *workqueue* va por delante de `main`, y `main` por delante del hilo de Bluetooth (lección 7).

En la lección 4 ya apareció la consecuencia (`tolerance_deg` es `volatile`). En la lección 6 se ve con detalle cómo se protege cada dato compartido.

## [prj.conf](prj.conf)

Es el archivo de **Kconfig** del proyecto (README, sección 1). Cada línea `CONFIG_X=valor` activa o ajusta una parte de Zephyr. Se combina con la configuración por defecto de la placa, y el resultado final de la compilación queda en `build/corpost_fw/zephyr/.config`. Ese archivo es útil para comprobar qué valor ha acabado teniendo una opción.

La extensión de VS Code marca a veces "Value is X by default" en una línea. Significa que esa línea no cambia nada; se dejan solo las que documentan una decisión, como `CONFIG_BT_MAX_CONN=1`.

### Lo que no es Bluetooth

```
CONFIG_CRC=y
```
Incluye en la compilación la librería de CRC de Zephyr, donde está `crc16_itu_t`. Sin ella, el enlazador daría `undefined reference to crc16_itu_t`: el `.h` existe, pero el código no se compila si no se activa.

### Bluetooth básico

```
CONFIG_BT=y
CONFIG_BT_PERIPHERAL=y
CONFIG_BT_DEVICE_NAME="CorPost"
CONFIG_BT_MAX_CONN=1
```
- **`CONFIG_BT`** activa toda la pila Bluetooth.
- **`CONFIG_BT_PERIPHERAL`** incluye solo el código del rol periférico, sin el de central (escanear y conectarse a otros). Menos código, menos flash.
- **`CONFIG_BT_DEVICE_NAME`** es el nombre del anuncio. Zephyr también lo pone en el servicio estándar *Generic Access* (UUID 0x1800), que se crea solo y que nRF Connect mostrará junto al nuestro.
- **`CONFIG_BT_MAX_CONN=1`** reserva memoria para una sola conexión. Además, es lo que pide el D3: un dispositivo, un móvil.

### Parámetros de conexión preferidos

```
CONFIG_BT_PERIPHERAL_PREF_MIN_INT=80
CONFIG_BT_PERIPHERAL_PREF_MAX_INT=160
CONFIG_BT_PERIPHERAL_PREF_LATENCY=4
CONFIG_BT_PERIPHERAL_PREF_TIMEOUT=400
```
Las unidades vienen del estándar Bluetooth y no son milisegundos:

| Opción | Unidad | Valor | Equivale a |
|---|---|---|---|
| `MIN_INT` | 1,25 ms | 80 | 100 ms |
| `MAX_INT` | 1,25 ms | 160 | 200 ms |
| `LATENCY` | citas que se puede saltar el nRF | 4 | hasta 1 s sin despertar si no hay nada que enviar |
| `TIMEOUT` | 10 ms | 400 | 4 s |

Zephyr pide estos valores al móvil 5 s después de conectar, y el móvil decide (README, 7.3). La regla del timeout es que debe ser mayor que `(1 + latencia) × intervalo máximo × 2` = 5 × 200 ms × 2 = 2 s. Si no, el móvil daría la conexión por perdida mientras el nRF se salta citas legítimamente.

### MTU

```
CONFIG_BT_GATT_CLIENT=y
CONFIG_BT_GATT_AUTO_UPDATE_MTU=y
CONFIG_BT_L2CAP_TX_MTU=247
CONFIG_BT_BUF_ACL_RX_SIZE=251
CONFIG_BT_BUF_ACL_TX_SIZE=251
```
- **El paquete (24 B) no cabe en el MTU por defecto** (23 B, de los que 20 son datos). Hay que negociar uno mayor.
- **La negociación la empieza siempre el cliente GATT,** con una *Exchange MTU Request*. El nRF es servidor, pero con `CONFIG_BT_GATT_CLIENT` puede hacer también de cliente para esto, y `AUTO_UPDATE_MTU` hace que lo pida solo al conectar. Así no dependemos de que la app lo pida: en Android, si la app no llama a `requestMtu`, el MTU se queda en 23.
- **247** es el MTU que ofrecemos. 247 + 4 B de cabecera L2CAP = **251**, el máximo que cabe en una trama de radio con *Data Length Extension*. Así un mensaje ATT completo viaja en una sola trama. Los dos `BUF_ACL_*_SIZE` son el tamaño de los buffers de la pila para esas tramas.
- **Cada lado dice su máximo y se usa el menor.** El valor real lo imprime `mtu_updated` en el RTT.

### Seguridad

```
CONFIG_BT_SMP=y
CONFIG_BT_SMP_SC_ONLY=y
CONFIG_BT_BONDABLE=y
CONFIG_BT_MAX_PAIRED=1
CONFIG_BT_PRIVACY=y
```

| Opción | Qué hace |
|---|---|
| `BT_SMP` | Activa SMP, el protocolo de emparejamiento. Sin él no hay cifrado |
| `BT_SMP_SC_ONLY` | **Solo LE Secure Connections y solo autenticado (nivel 4).** Se rechaza el *legacy pairing* y también "Just Works", que no protege contra MITM |
| `BT_BONDABLE` | Guardar las claves tras emparejar (bonding) |
| `BT_MAX_PAIRED=1` | Como mucho un bond guardado: un segundo móvil no puede emparejarse |
| `BT_PRIVACY` | Dirección aleatoria que cambia cada 15 min (`CONFIG_BT_RPA_TIMEOUT=900`, valor por defecto) |

Ninguna de estas líneas pide un passkey. **El método de emparejamiento lo decide el código**, según los *callbacks* que se registren (lección 6, bloque 10).

### Guardar los bonds en flash

```
CONFIG_BT_SETTINGS=y
CONFIG_SETTINGS=y
CONFIG_FLASH=y
CONFIG_FLASH_PAGE_LAYOUT=y
CONFIG_FLASH_MAP=y
CONFIG_NVS=y
```
Es una cadena de capas:

```
Pila Bluetooth  → "guarda la clave del móvil X"        (BT_SETTINGS)
Settings        → almacén clave/valor: "bt/keys/…" = …  (SETTINGS)
NVS             → escribe registros en flash repartiendo el desgaste (NVS)
Flash map       → en qué zona de la flash: partición "storage" (FLASH_MAP)
Driver de flash → borrar y escribir páginas               (FLASH, FLASH_PAGE_LAYOUT)
```
- **La partición `storage`** la define el devicetree de la placa: 24 KB en la dirección 0x7a000, al final de los 512 KB. Como el programa no se graba ahí, flashear no borra los bonds.
- **NVS** (*Non-Volatile Storage*) existe porque una página de flash solo aguanta unos 10.000 borrados. NVS no reescribe siempre el mismo sitio: va añadiendo registros nuevos y reparte el desgaste.

### Lo que cuesta el BLE

| | Antes del BLE | Con BLE |
|---|---|---|
| Flash | 33 KB | 168 KB (32 % de 512 KB) |
| RAM | 7 KB | 37 KB (57 % de 64 KB) |

Casi todo es la pila Bluetooth (controlador, host, criptografía de LE Secure Connections). Nuestro `ble.c` es una parte pequeña: el búfer de lecturas ocupa 1,6 KB de RAM.

## [ble.h](src/ble.h)

```c
#define BLE_READING_LEN 24

#define CMD_SET_INTERVAL  0x01 /* + uint16 LE: segundos */
#define CMD_SET_TOLERANCE 0x02 /* + uint8: grados */
#define CMD_RECALIBRATE   0x03 /* sin parámetro */
#define CMD_SET_VIBRATION 0x04 /* + uint8: 0 = off, 1 = on */
```
El "contrato" con la app, en forma de constantes: el tamaño del paquete y los opcodes del D3. Están en el `.h` y no en el `.c` porque son parte de la interfaz pública: si mañana hubiera un test o un simulador en C, usaría los mismos nombres.

### Punteros a función: `struct ble_cmd_handlers`

```c
struct ble_cmd_handlers {
	void (*set_interval)(uint16_t seconds);
	void (*set_tolerance)(uint8_t degrees);
	void (*recalibrate)(void);
	void (*set_vibration)(bool on);
};
```

**Cómo se lee `void (*set_interval)(uint16_t seconds);`:** `set_interval` es un **puntero** (`*`) **a una función** que recibe un `uint16_t` y devuelve `void`. Los paréntesis de `(*set_interval)` son imprescindibles: `void *set_interval(uint16_t)` declararía una función que devuelve un `void *`.

**Para qué sirve.** Cuando llega un comando, `ble.c` tiene que avisar a `main.c`. Hay dos formas:

| Forma | Problema |
|---|---|
| `ble.c` modifica directamente `interval_s`, `recalibrate`… de `main.c` | `ble.c` necesitaría conocer las variables internas de `main.c`. Los dos archivos quedarían atados y no se podrían probar ni cambiar por separado |
| **`main.c` le pasa a `ble.c` una "ficha" con las funciones a llamar** | `ble.c` solo sabe que existe *algo* que sabe cambiar el intervalo. No sabe qué hace ni dónde está |

Es la misma idea que una **interfaz** en Java, una clase abstracta con métodos virtuales en C++ o un `onCommand` en JavaScript. Zephyr usa este patrón por todas partes: en la lección 6 lo veremos al revés, con `ble.c` pasándole a Zephyr sus funciones (`connected`, `disconnected`…).

El comentario del `.h` avisa de la condición importante: **se llaman desde el hilo de Bluetooth y deben ser rápidas.**

### Las funciones públicas

| Función | Qué hace | Quién la llama |
|---|---|---|
| `ble_init(handlers)` | Arranca Bluetooth y el advertising; guarda la ficha de comandos | `main`, una vez |
| `ble_submit(r, uptime_ms)` | Mete una lectura en el búfer | `main`, tras cada medida |
| `ble_flush()` | Envía lo pendiente si el enlace está listo; devuelve cuántas envió | `main`, tras cada medida y cada 100 ms en la espera |
| `ble_pending()` | Cuántas lecturas hay en el búfer | `main`, para el log |
| `ble_clear_bonds()` | Borra los emparejamientos | `main`, al pulsar el Botón 2 |
| `ble_crc16(data, len)` | El CRC del paquete | `ble.c`. Es pública por si se quiere probar el CRC desde fuera |

**`ble.h` no menciona ningún tipo de Zephyr Bluetooth** (`bt_conn`, `bt_gatt_attr`…). Desde `main.c`, el BLE es una caja negra con seis funciones: **encapsulación**. Si se cambiara de radio, `main.c` no se tocaría.

`ble.h` incluye `posture.h` porque `ble_submit` recibe un `struct window_result`.

## Preguntas de comprobación

1. Si el MTU negociado se quedara en 23, ¿qué pasaría con las lecturas?
2. ¿Por qué hace falta `CONFIG_BT_GATT_CLIENT` si el nRF es el servidor?
3. Con `PREF_MAX_INT=160` y `PREF_LATENCY=4`, ¿cuál es el valor mínimo válido de `PREF_TIMEOUT` (en unidades de 10 ms)?
4. Escribe el campo que añadirías a `ble_cmd_handlers` para un comando nuevo que reciba un `int16_t` y devuelva un `int`.

### Respuestas

1. **No se enviaría ninguna.** `link_ready` exige un MTU ≥ 27 (24 + 3 de cabecera), así que se acumularían en el búfer, el RTT diría `enlace no listo` y, al llenarse, se irían sobrescribiendo.
2. **Porque la petición de MTU es un procedimiento del cliente GATT.** Para no depender de que la app la haga, el nRF actúa como cliente solo para eso.
3. (1 + 4) × 200 ms × 2 = 2000 ms, es decir, **más de 200 unidades**. Usamos 400 (4 s), con margen.
4. `int (*nombre)(int16_t valor);`

---

# Lección 6: [ble.c](src/ble.c), el BLE de CorPost

Es el archivo más largo (unas 520 líneas). Lo divido en trece bloques, en el orden del archivo. La teoría de cada parte está en la sección 7 del README, y lo que hace cada pieza desde fuera, en la sección 8.

## Bloque 1: includes (líneas 13-26)

| Include | Para qué |
|---|---|
| `"ble.h"`, `"config.h"` | Nuestra interfaz y los parámetros (`BUFFER_SIZE`, `BATTERY_LEVEL`, límites de los comandos) |
| `zephyr/kernel.h` | Spinlock, mutex, `k_work`, `k_uptime_get` |
| `zephyr/bluetooth/bluetooth.h` | `bt_enable`, advertising, `bt_data` |
| `zephyr/bluetooth/conn.h` | Conexiones, seguridad, emparejamiento |
| `zephyr/bluetooth/gatt.h` | El servicio, notificaciones, MTU |
| `zephyr/bluetooth/hci.h` | `bt_hci_err_to_str` (texto de los códigos de desconexión) |
| `zephyr/bluetooth/uuid.h` | Los tipos y macros de UUID |
| `zephyr/settings/settings.h` | `settings_load` (leer los bonds de la flash) |
| `zephyr/sys/byteorder.h` | `sys_put_le16/32`, `sys_get_le16/32`, como en `vibro.c` |
| `zephyr/sys/crc.h` | `crc16_itu_t` |
| `string.h`, `math.h` | `memcpy`, `roundf` |

## Bloque 2: los UUIDs (líneas 28-39)

```c
#define CORPOST_UUID(n) BT_UUID_128_ENCODE(0xbd5f0000 + (n), 0x319b, 0x420e, 0xae78, 0x678d1c7cf46d)
```
- **Un UUID de 128 bits se escribe en cinco grupos** de 8-4-4-4-12 cifras hexadecimales: `bd5f0001-319b-420e-ae78-678d1c7cf46d`. `BT_UUID_128_ENCODE` recibe esos cinco grupos tal como se leen y genera los 16 bytes en **orden inverso** (*little-endian*), que es como BLE los transmite. Así, en el código se escriben igual que los muestra nRF Connect.
- **`CORPOST_UUID(n)` es una macro con parámetro:** `CORPOST_UUID(2)` sustituye `n` por 2, y el primer grupo queda `0xbd5f0002`. Los cuatro UUIDs comparten la base y solo cambia ese número. Es una práctica habitual: el servicio UART de Nordic usa `6E400001-…`, `6E400002-…`, etc.
- **`(n)` va entre paréntesis** por seguridad con las macros: si alguien escribiera `CORPOST_UUID(1 + 1)`, sin paréntesis también funcionaría aquí, pero en otras expresiones (por ejemplo, con una multiplicación) el texto sustituido cambiaría el orden de las operaciones.

```c
#define BT_UUID_CORPOST_SERVICE_VAL CORPOST_UUID(1)
static const struct bt_uuid_128 uuid_service = BT_UUID_INIT_128(CORPOST_UUID(1));
```
El UUID se usa de dos formas:
- **Como 16 bytes sueltos** (`..._VAL`), para meterlo en el anuncio.
- **Como `struct bt_uuid_128`**, que es lo que espera la API de GATT.

**"Herencia" en C.** La estructura es así:
```c
struct bt_uuid_128 {
	struct bt_uuid uuid;   /* cabecera común: el tipo (16, 32 o 128 bits) */
	uint8_t val[16];
};
```
Las funciones de GATT reciben un `const struct bt_uuid *` genérico. Por eso las características usan `&uuid_reading.uuid`: un puntero a la cabecera. La función mira el tipo, ve que es de 128 bits y sabe que detrás vienen 16 bytes. Como la cabecera es el **primer campo**, su dirección es la misma que la del struct entero. Es la forma de imitar la herencia en C: el primer campo hace de "clase base".

(En `BT_GATT_PRIMARY_SERVICE(&uuid_service)` se pasa el struct entero sin `.uuid`. Funciona por eso mismo: esa macro guarda el puntero como dato genérico, y apunta a la misma dirección.)

```c
static const struct ble_cmd_handlers *cmd;
```
Guarda la "ficha" de comandos que `main.c` pasa a `ble_init` (lección 5).

## Bloque 3: la hora UTC (líneas 41-61)

```c
static struct k_spinlock time_lock;
static bool time_set;
static uint32_t utc_ref;       /* hora UTC recibida (s) */
static int64_t utc_ref_uptime; /* uptime en ese momento (ms) */
```
El nRF no tiene reloj de calendario, solo el uptime (`k_uptime_get`), que lo cuenta el RTC del chip desde el arranque. Cuando la app escribe la hora, se apunta la pareja **(hora recibida, uptime en ese momento)**. Con eso, cualquier uptime se puede convertir en hora:

```c
*utc = (uint32_t)((int64_t)utc_ref + (uptime_ms - utc_ref_uptime) / 1000);
```
**Ejemplo:** la app escribe 1 793 800 000 cuando el uptime es 60 000 ms. Una lectura tomada con uptime 45 000 ms tiene la hora 1 793 800 000 + (45 000 − 60 000) / 1000 = **1 793 799 985**, 15 s antes.

- **También funciona para lecturas anteriores a la sincronización.** La diferencia sale negativa y por eso se calcula en `int64_t` con signo, con el cast explícito de `utc_ref`.
- **Deriva:** el cristal de 32 kHz del DK tiene un error de unas 20 ppm, es decir, menos de 2 s al día. Como la app reescribe la hora en cada conexión, el error no se acumula.

**Por qué hace falta un *lock* aquí.** Estas variables las **escribe** `write_time`, en el hilo de Bluetooth, y las **lee** `ble_flush`, en el hilo principal. Hay dos problemas:

1. **Lectura "rota" (*torn read*).** `utc_ref_uptime` es de 64 bits y el Cortex-M4 es de 32: escribirlo cuesta **dos instrucciones**. Si el hilo principal leyera entre las dos, vería la mitad nueva y la mitad vieja, un valor que nunca existió. Con la mitad alta de otro valor, el error sería de 2³² ms, unos 49 días.
2. **Coherencia del conjunto.** Las tres variables deben cambiar "a la vez". Leer `time_set` nuevo con un `utc_ref` viejo también estaría mal.

```c
k_spinlock_key_t key = k_spin_lock(&time_lock);
...
k_spin_unlock(&time_lock, key);
```
- **En un procesador de un solo núcleo, un *spinlock* desactiva las interrupciones,** y con ellas los cambios de hilo, durante esas pocas instrucciones. Nadie puede meterse en medio. `key` guarda el estado anterior para restaurarlo.
- **Regla:** la sección protegida debe ser **mínima**. Nada de esperas ni de `printk` dentro. Por eso `write_time` imprime **después** de soltar el lock (línea 217) y vuelve a leer el valor de `buf` en lugar de tocar `utc_ref` fuera del lock.
- **Un mutex también serviría,** pero para tres asignaciones el spinlock es más barato y se puede usar desde cualquier contexto.

Comparado con la lección 4: `tolerance_deg` (32 bits, un solo valor) no necesita lock; esto (64 bits, tres valores relacionados) sí.

## Bloque 4: el búfer circular (líneas 63-115)

```c
struct entry {
	int16_t acc[3];
	int16_t gyr[3];
	float angle;
	uint8_t status;
	int64_t uptime_ms;
};
```
**Por qué no se guarda directamente el paquete de 24 B:** el paquete lleva la hora UTC y el CRC. Si la lectura se toma antes de que la app escriba la hora, el timestamp aún no se conoce. Por eso se guarda el **uptime**, y el paquete se construye **en el momento de enviarlo**.

**Tamaño real: 32 B, no 25.** El compilador añade **relleno** (*padding*) para que cada campo esté alineado a su tamaño:

| Offset | Campo | Bytes |
|---|---|---|
| 0-11 | `acc`, `gyr` | 12 |
| 12-15 | `angle` | 4 |
| 16 | `status` | 1 |
| 17-23 | *relleno* | 7 |
| 24-31 | `uptime_ms` (`int64_t`, alineado a 8) | 8 |

50 × 32 B = 1,6 KB de RAM. Se podría compactar, pero no hace falta.

```c
static struct entry ring[BUFFER_SIZE];
static int ring_head; /* siguiente posición libre */
static int ring_count;
```
El búfer circular se representa con **dónde se escribe la siguiente** (`head`) y **cuántas hay** (`count`). La más antigua (`tail`) se calcula: `tail = (head − count + N) % N`.

Ejemplo con N = 5:
```
3 lecturas (A, B, C):      [A][B][C][ ][ ]   head=3 count=3  tail=(3-3+5)%5=0 → A
se envía A:                [A][B][C][ ][ ]   head=3 count=2  tail=1 → B   (A queda como basura)
llegan D, E, F, G:         [F][G][C][D][E]   head=2 count=5  tail=2 → C   (F y G han dado la vuelta)
llega H (lleno):           [F][G][H][D][E]   head=3 count=5  tail=3 → D   (C sobrescrita)
```
- **Lleno = sobrescribir la más antigua** (D3). `ble_submit` siempre escribe en `head` y avanza. Si estaba lleno, `count` se queda en N y la `tail` calculada avanza sola.
- **El `+ N` del cálculo** existe porque en C el `%` de un número negativo da negativo: `-2 % 5` es `-2`, no `3` como en Python. Sumando N antes, el número nunca es negativo.

```c
static int16_t to_i16(float v)
```
Las medias son `float` y el paquete lleva `int16_t`. `roundf` redondea al entero más cercano y después se **satura** al rango de `int16_t`. La saturación no es por precaución estética: en C, convertir un `float` fuera de rango a entero es **comportamiento indefinido** (puede dar cualquier cosa).

**En `ble_submit`:**
- `r->gyr_mean_dps[k] * 16.0f` devuelve el giro a las unidades del sensor (1/16 °/s) para que quepa en un entero sin perder decimales. La app divide entre 16.
- **Un INVALID se guarda con ángulo 0,** porque su ángulo no tiene significado.

**No hay lock en el búfer** porque solo lo usa el hilo principal (`ble_submit` y `ble_flush`). Regla general: cada dato compartido o tiene **un único dueño** o se **protege**.

## Bloque 5: CRC y construcción del paquete (líneas 117-138)

```c
return crc16_itu_t(0xFFFF, data, len);
```
**"CRC-16/CCITT" es ambiguo:** hay varias variantes con el mismo polinomio (0x1021) que cambian el valor inicial y el orden de los bits (KERMIT, XMODEM, CCITT-FALSE…) y dan resultados distintos. Si la app y el firmware usan variantes diferentes, todos los paquetes parecerán corruptos. Por eso se fija una, **CCITT-FALSE** (valor inicial 0xFFFF, sin reflejar), con su valor de comprobación: `"123456789"` → **0x29B1** (README, 8.5).

```c
static void encode(const struct entry *e, uint32_t ts, uint8_t out[BLE_READING_LEN])
```
`uint8_t out[24]` como parámetro **es en realidad un puntero**: en C, un array que se pasa a una función se convierte en un puntero a su primer elemento. El 24 solo documenta lo que se espera.

```c
sys_put_le16((uint16_t)e->acc[k], &out[0 + 2 * k]);
```
El cast de `int16_t` a `uint16_t` **conserva los bits**, porque los negativos se guardan en complemento a dos. Por ejemplo, −774 = 0xFCFA, que se escribe como `FA FC`.

**El `float` del ángulo.** Hay que meter sus 4 bytes IEEE-754 en el paquete. Hay tres formas de intentarlo:

| Código | Resultado |
|---|---|
| `(uint32_t)e->angle` | **Mal:** convierte el **valor** (39,4 → 39), no los bits |
| `*(uint32_t *)&e->angle` | Reinterpreta los bits, pero rompe la regla de *strict aliasing* de C: es comportamiento indefinido y el optimizador puede generar código incorrecto |
| **`memcpy(&angle_bits, &e->angle, 4)`** | **Correcto.** Copia los 4 bytes tal cual. El compilador lo convierte en una sola instrucción |

```c
out[16] = e->status & 0x03;
out[17] = BATTERY_LEVEL;
sys_put_le32(ts, &out[18]);
sys_put_le16(ble_crc16(out, 22), &out[22]);
```
- `& 0x03` garantiza que los bits 2-7 del estado son 0, como pide el D3.
- **El CRC se calcula sobre los 22 primeros bytes y se escribe en los dos últimos.** El orden importa: primero todos los datos, luego el CRC.

**Ejemplo completo.** Una lectura BAD con aceleración (324, −774, 526) mg, giro (3, −2, 0) en 1/16 °/s, ángulo 39,4°, sin batería y timestamp 1 793 800 000:
```
44 01 FA FC 0E 02 | 03 00 FE FF 00 00 | 9A 99 1D 42 | 01 | FF | 40 37 EB 6A | B9 99
 acc 324 −774 526 |  gyr 3 −2 0       | 39,4 (float)| BAD| N/D| timestamp   | CRC 0x99B9
```
Es lo que debería verse en nRF Connect al recibir esa lectura.

## Bloque 6: las escrituras de la app (líneas 140-225)

```c
static ssize_t write_command(struct bt_conn *conn, const struct bt_gatt_attr *attr,
			     const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
```
Es la firma que Zephyr exige para un *callback* de escritura GATT. La llama el host cuando la app escribe en Command:

| Parámetro | Qué es |
|---|---|
| `conn` | La conexión que escribe |
| `attr` | El atributo escrito |
| `buf`, `len` | Los bytes recibidos y cuántos son |
| `offset` | Para las "escrituras largas", en las que el valor llega a trozos. No las usamos: si `offset ≠ 0`, error |
| `flags` | Detalles del tipo de escritura. No los usamos |

**El valor de retorno es la respuesta a la app:**
- `return len;` → "aceptado". La app recibe la confirmación del *write*.
- `return BT_GATT_ERR(código);` → un número negativo que el host convierte en una *ATT Error Response* con ese código. En la app, la escritura falla con ese error.

**La validación, por capas:**
1. `len` entre 1 y 4: opcode + como mucho 3 B (D3). Si no, `INVALID_ATTRIBUTE_LEN`.
2. `switch (b[0])` según el opcode. Cada caso comprueba su longitud exacta y su rango. Un opcode desconocido da `VALUE_NOT_ALLOWED`.
3. Solo si todo es correcto, `cmd->set_interval(s)`. Llamar a través de un puntero a función se escribe igual que una llamada normal.

```c
case CMD_SET_INTERVAL: {
	...
	uint16_t s = sys_get_le16(&b[1]);
	...
}
```
**Las llaves del `case`** son necesarias porque se declara una variable (`s`). En C (antes de C23) no se puede declarar una variable justo después de una etiqueta, y además su ámbito se extendería a los demás `case`.

**Lo que no está aquí: la seguridad.** No hay ningún "¿está emparejado?" en `write_command`. La característica se declaró con `BT_GATT_PERM_WRITE_AUTHEN` (bloque 7), así que **el host rechaza la escritura antes de llamar a nuestra función** si el enlace no tiene seguridad suficiente. Nuestro código nunca ve una escritura no autenticada. La seguridad es **declarativa**: se dice en la tabla del servicio, no se programa en cada función.

**El contexto: el hilo de Bluetooth.** Mientras `write_command` se ejecuta, la pila no procesa nada más que llegue del móvil. Por eso el comando "recalibrar" solo pone una bandera. Si llamara aquí a `calibrate()`, que tarda 2 s o más, el hilo de Bluetooth quedaría bloqueado. `printk` sí es aceptable: es rápido.

**`write_time`** sigue el mismo esquema: exige exactamente 4 B y guarda la hora bajo el spinlock (bloque 3).

**`reading_ccc_changed`** la llama el host cuando la app escribe en el CCCD de Reading, es decir, cuando activa o desactiva las notificaciones. Solo imprime. **No se usa para guardar un "está suscrito" propio**, porque con bonding el host restaura la suscripción desde la flash al reconectar. La fuente de verdad es el host, y por eso `link_ready` le pregunta con `bt_gatt_is_subscribed`.

## Bloque 7: la tabla del servicio (líneas 227-247)

```c
BT_GATT_SERVICE_DEFINE(corpost_svc,
	BT_GATT_PRIMARY_SERVICE(&uuid_service),
	BT_GATT_CHARACTERISTIC(&uuid_reading.uuid, BT_GATT_CHRC_NOTIFY,
			       BT_GATT_PERM_NONE, NULL, NULL, NULL),
	BT_GATT_CCC(reading_ccc_changed, BT_GATT_PERM_READ_AUTHEN | BT_GATT_PERM_WRITE_AUTHEN),
	BT_GATT_CUD("Reading", BT_GATT_PERM_READ),
	...
);
```
`BT_GATT_SERVICE_DEFINE` construye **en tiempo de compilación** un array constante de atributos, `corpost_svc.attrs[]`, y lo registra automáticamente. No hay que llamar a ninguna función de inicio. Cada macro aporta uno o dos atributos:

| Índice | Macro | Atributo |
|---|---|---|
| 0 | `BT_GATT_PRIMARY_SERVICE` | Declaración del servicio |
| 1 | `BT_GATT_CHARACTERISTIC` (Reading) | Declaración de la característica: UUID y propiedades |
| 2 | (la misma macro) | **Valor** de Reading |
| 3 | `BT_GATT_CCC` | CCCD de Reading |
| 4 | `BT_GATT_CUD` | Nombre "Reading" |
| 5-7 | Command | Declaración, valor y nombre |
| 8-10 | Time | Declaración, valor y nombre |

Esta es la lista de **handles** que el móvil recorre en el descubrimiento de servicios (README, 7.4). **El orden importa:** el CCCD y el CUD pertenecen a la característica que tienen justo antes.

**Parámetros de `BT_GATT_CHARACTERISTIC`:** UUID, **propiedades**, **permisos**, función de lectura, función de escritura y datos de usuario.

**Propiedades y permisos no son lo mismo:**

| | Propiedades (`BT_GATT_CHRC_*`) | Permisos (`BT_GATT_PERM_*`) |
|---|---|---|
| Qué son | Lo que el servidor **anuncia** que se puede hacer | Lo que el servidor **exige** de verdad al acceder |
| Dónde van | En la declaración, y el móvil las lee | Solo en el servidor; el móvil no las ve |
| Ejemplo | `NOTIFY`, `WRITE` | `WRITE_AUTHEN`: escritura solo con enlace autenticado |

- **El valor de Reading tiene `PERM_NONE`:** nadie puede leerlo ni escribirlo directamente. Solo se reciben notificaciones.
- **El CCCD tiene `READ_AUTHEN | WRITE_AUTHEN`:** suscribirse exige estar emparejado. Así, nada llega nunca a un móvil sin emparejar.
- **Los CUD son de lectura pública:** solo contienen un nombre.

```c
#define READING_ATTR (&corpost_svc.attrs[1])
```
Es la declaración de Reading. `bt_gatt_notify` y `bt_gatt_is_subscribed` aceptan la declaración y encuentran solos el valor y el CCCD que van detrás.

## Bloque 8: el advertising (líneas 249-270)

```c
static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID128_ALL, BT_UUID_CORPOST_SERVICE_VAL),
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};
```
Cada entrada se convierte en una estructura `[longitud][tipo][datos]` dentro de los 31 B del anuncio:

| Entrada | Bytes |
|---|---|
| *Flags*: "visible siempre" (`GENERAL`) y "sin Bluetooth clásico" (`NO_BREDR`) | 1 + 1 + 1 = 3 |
| UUID del servicio (128 bits) | 1 + 1 + 16 = 18 |
| Nombre "CorPost" | 1 + 1 + 7 = 9 |
| **Total** | **30 de 31** |

- **`BT_DATA_BYTES`** recibe los bytes directamente. **`BT_DATA`** recibe un puntero y una longitud.
- **`sizeof("CorPost")` es 8,** porque cuenta el `'\0'` final de la cadena. Por eso el `- 1`.
- **Si el nombre tuviera más de 8 letras, no cabría.** Entonces habría que moverlo a la *scan response*: el segundo array de `bt_le_adv_start`, que aquí es `NULL, 0`.

```c
static struct k_work adv_work;
...
int err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_2, ad, ARRAY_SIZE(ad), NULL, 0);
```
- **`BT_LE_ADV_CONN_FAST_2`:** anuncio conectable cada 100-150 ms. Con `CONFIG_BT_PRIVACY`, la dirección aleatoria (RPA) la pone la pila sola.
- **Por qué con un `k_work`:** el advertising se reinicia tras cada desconexión, desde el *callback* `recycled`. Ese *callback* se ejecuta dentro de la pila, y arrancar el advertising desde ahí puede fallar porque la pila aún está ocupada. Un `k_work` es una tarea que se encola en el **system workqueue** y se ejecuta un poco después, en otro hilo y sin prisa. Se inicializa una vez (`k_work_init`, en `ble_init`) y se lanza cada vez con `k_work_submit`. Es el patrón del ejemplo oficial de Nordic (`peripheral_lbs`).
- **En Zephyr 4.x, el advertising no se reanuda solo** después de una conexión. Por eso hay que relanzarlo.

## Bloque 9: la conexión (líneas 272-370)

```c
static K_MUTEX_DEFINE(conn_lock);
static struct bt_conn *cur_conn;
```
**`cur_conn` es la conexión actual**, para que el hilo principal pueda enviar notificaciones. Tiene dos protecciones:

**1. Conteo de referencias.** El objeto `bt_conn` es de la pila. `bt_conn_ref` suma 1 a su contador de "usuarios" y `bt_conn_unref` resta 1; la pila solo lo libera cuando el contador llega a 0. Es como un `shared_ptr` de C++. Guardar el puntero **sin** `ref` sería peligroso: tras la desconexión, la pila podría reutilizar esa memoria y el puntero apuntaría a basura.

**2. Mutex.** `cur_conn` lo escriben `connected` y `disconnected` (hilo de Bluetooth) y lo leen `ble_flush` y `ble_clear_bonds` (hilo principal). Aquí se usa un **mutex** y no un spinlock porque, mientras está tomado, se llaman funciones de la pila que pueden tardar o esperar. Un mutex permite que el hilo duerma con él tomado; un spinlock, no.

**`connected`:**
- Si `err ≠ 0`, la conexión ha fallado y no hay nada que hacer.
- Imprime la dirección del móvil y los parámetros iniciales. `bt_conn_get_info` da el intervalo en `interval_us` (microsegundos). El campo antiguo, en unidades de 1,25 ms, está obsoleto en Zephyr 4.
- Guarda la conexión, con `ref` y bajo el mutex.
- **`bt_conn_set_security(conn, BT_SECURITY_L4)`** envía al móvil una petición de seguridad. Si el móvil ya está emparejado, reactiva el cifrado con la clave guardada. Si no, empieza el emparejamiento. Así no se espera a que la app intente acceder a algo protegido.

**`disconnected`** imprime el motivo y suelta la referencia. Dos motivos habituales, útiles en las pruebas:
- `0x13`, *Remote User Terminated*: el móvil ha cerrado la conexión.
- `0x08`, *Connection Timeout*: el *supervision timeout* (por ejemplo, al alejarse).

**`recycled`** relanza el advertising (bloque 8).

**`le_param_updated`** imprime los parámetros nuevos. Las unidades son las del estándar: el intervalo en 1,25 ms (× 1250 para pasarlo a µs) y el timeout en 10 ms. `print_params` imprime decimales con enteros, igual que `print_f1` en `main.c`.

**`security_changed`** imprime el nivel alcanzado o el error.

```c
BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
	.disconnected = disconnected,
	...
};
```
- **Registro en tiempo de compilación:** igual que el servicio, esta macro deja la estructura en una sección especial de la memoria que la pila recorre. No hace falta llamar a ninguna función de registro.
- **`.connected = connected`** es un **inicializador designado**: se rellena el campo por su nombre. Los campos que no se mencionan quedan a `NULL`, y la pila no los llama.
- Es el patrón de la lección 5, pero al revés: aquí es `ble.c` quien le da a Zephyr su "ficha" de funciones.

**`gatt_callbacks`** hace lo mismo para el MTU (`mtu_updated`), pero se registra en tiempo de ejecución con `bt_gatt_cb_register`, en `ble_init`. Zephyr tiene los dos estilos según la API.

## Bloque 10: el emparejamiento (líneas 372-414)

```c
static struct bt_conn_auth_cb auth_callbacks = {
	.passkey_display = auth_passkey_display,
	.cancel = auth_cancel,
};
```
**Aquí se decide el método de emparejamiento.** La pila deduce las **capacidades de E/S** del nRF según qué *callbacks* existen:

| *Callbacks* definidos | Capacidad anunciada | Método con un móvil |
|---|---|---|
| Ninguno | *NoInputNoOutput* | Just Works. **Con `SC_ONLY` se rechaza** (no protege contra MITM) |
| **`passkey_display`** | ***DisplayOnly*** | **Passkey Entry: el nRF muestra el código y el usuario lo teclea en el móvil** (nuestro caso) |
| `passkey_display` + `passkey_confirm` | *DisplayYesNo* | Numeric Comparison |
| `passkey_entry` | *KeyboardOnly* | Passkey Entry al revés: el móvil muestra y se teclea en el nRF |

Nuestra "pantalla" es el RTT.
- **El código** lo genera la pila al azar en cada emparejamiento. `%06u` lo imprime con ceros a la izquierda (`004213`, no `4213`).
- **Por qué protege contra un atacante en medio:** el código se usa bit a bit dentro del protocolo de LE Secure Connections. Un atacante que no lo ve tiene 1 posibilidad entre un millón de acertar, y un fallo aborta el emparejamiento.
- **`auth_cancel`** se llama si el usuario cancela en el móvil o pasan 30 s sin terminar.

```c
static struct bt_conn_auth_info_cb auth_info_callbacks = {
	.pairing_complete = pairing_complete,
	.pairing_failed = pairing_failed,
};
```
Es una estructura aparte porque estos *callbacks* son solo **informativos**: no cambian las capacidades. `bonded = true` indica que las claves se han guardado. `pairing_failed` recuerda que, con un bond ya guardado (`MAX_PAIRED=1`), un segundo móvil será rechazado.

```c
static void count_bond(const struct bt_bond_info *info, void *user_data)
{
	(*(int *)user_data)++;
}
```
**El patrón *callback* + `void *user_data`.** `bt_foreach_bond` llama a `count_bond` una vez por cada bond guardado. Para que la función pueda sumar en una variable nuestra, se le pasa su dirección como `void *` ("puntero a cualquier cosa"), y dentro se convierte de vuelta a `int *`. Es la forma de C de suplir las *closures* o *lambdas* de otros lenguajes.

Lectura de `(*(int *)user_data)++`, de dentro afuera: convierte a puntero a `int`, accede al `int` apuntado y súmale 1. Los paréntesis exteriores son necesarios: `*(int *)user_data++` incrementaría el **puntero**, no el valor.

## Bloque 11: `ble_init` (líneas 416-448)

El orden de los pasos importa:

| Paso | Por qué en este orden |
|---|---|
| `cmd = handlers` | Antes de que pueda llegar ningún comando |
| Registrar los *callbacks* de emparejamiento | **Antes de `bt_enable`:** la pila debe conocer las capacidades de E/S desde el principio |
| `bt_gatt_cb_register` | Para recibir el aviso del MTU |
| `bt_enable(NULL)` | Arranca el controlador y el host. Con `NULL` es síncrono: vuelve cuando todo está listo |
| `settings_load()` | Lee de la flash la **identidad** del nRF (su dirección y su clave de privacidad), los **bonds** y las **suscripciones** guardadas. **Después de `bt_enable` y antes de anunciarse:** si se anunciara antes, usaría una identidad nueva y el móvil emparejado no lo reconocería |
| Contar los bonds | Informativo |
| `k_work_init` + `k_work_submit` | Empieza el advertising |

`err |= ...` acumula errores, el mismo patrón que en `bno055_init`.

## Bloque 12: `link_ready` y `ble_flush` (líneas 450-506)

**`link_ready`** concentra las condiciones para enviar:

| Condición | Por qué |
|---|---|
| `bt_conn_get_security(conn) >= BT_SECURITY_L4` | Un móvil emparejado que reconecta está conectado unos milisegundos **antes** de que se reactive el cifrado. No se envía nada en claro |
| `bt_gatt_is_subscribed(...)` | La app ha activado las notificaciones |
| `bt_gatt_get_mtu(conn) >= 24 + 3` | El paquete cabe (3 B de cabecera ATT) |
| `has_time` | Sin hora, el timestamp sería 0 y la app, que deduplica por `(device_id, timestamp)`, descartaría todas las lecturas menos una |

**`ble_flush`, paso a paso:**

```c
k_mutex_lock(&conn_lock, K_FOREVER);
if (cur_conn) {
	conn = bt_conn_ref(cur_conn);
}
k_mutex_unlock(&conn_lock);
```
1. **Toma su propia referencia a la conexión y suelta el mutex enseguida.** Con su referencia, el objeto sigue existiendo aunque el móvil se desconecte a mitad: las llamadas simplemente fallarán. Y **no se mantiene el mutex durante la ráfaga** para evitar un bloqueo mutuo (*deadlock*):
   - `bt_gatt_notify` puede quedarse esperando un buffer libre (siguiente punto).
   - Si el enlace se cae, el hilo de Bluetooth procesa la desconexión y llama a `disconnected`, que necesita el mutex.
   - Si `ble_flush` lo tuviera tomado, cada hilo esperaría al otro para siempre.

```c
while (ring_count > 0 && link_ready(conn)) {
	int tail = (ring_head - ring_count + BUFFER_SIZE) % BUFFER_SIZE;
	...
	uptime_to_utc(ring[tail].uptime_ms, &ts);
	encode(&ring[tail], ts, pkt);
	if (bt_gatt_notify(conn, READING_ATTR, pkt, sizeof(pkt)) != 0) {
		break;
	}
	ring_count--;
	sent++;
}
```
2. **Envía de la más antigua a la más nueva** mientras quede algo y el enlace siga listo. El paquete se construye en el momento, con la hora ya conocida.
3. **`bt_gatt_notify` puede esperar.** La pila tiene solo 3 buffers de envío (`CONFIG_BT_ATT_TX_COUNT=3`). Llamada desde el hilo principal, si no queda ninguno libre **espera** a que se libere uno, y eso ocurre cuando el controlador transmite los anteriores. Así la ráfaga va al ritmo del enlace, sin perder nada, aunque el hilo principal queda ocupado mientras dura. (Desde el *system workqueue* no esperaría: devolvería error.)
4. **`ring_count--` solo si `bt_gatt_notify` tuvo éxito.** Si falla (por ejemplo, porque se cayó la conexión), la lectura sigue en el búfer para la próxima vez.
5. **`bt_conn_unref`** suelta la referencia propia. Cada `ref` debe tener su `unref`.

**Una limitación de Notify:** `bt_gatt_notify` devuelve 0 cuando el paquete queda **en cola**, no cuando el móvil lo recibe. Si la conexión se cae justo después, esa lectura se pierde: ya no está en el búfer y no llegó. Con **Indicate** el móvil confirmaría cada paquete, a cambio de ser mucho más lento. El D3 acepta este riesgo (≥ 95 % de paquetes correctos).

## Bloque 13: `ble_clear_bonds` (líneas 508-519)

- Corta la conexión actual. El enlace está cifrado con una clave que se va a borrar, así que no tiene sentido mantenerlo.
- **`bt_unpair(BT_ID_DEFAULT, BT_ADDR_LE_ANY)`** borra **todos** los bonds, de la RAM y de la flash. `BT_ADDR_LE_ANY` es el comodín "cualquier dirección".

## Resumen: qué se ejecuta en cada hilo y cómo se protege lo compartido

| Funciones | Hilo |
|---|---|
| `connected`, `disconnected`, `le_param_updated`, `security_changed`, `mtu_updated` | Bluetooth (RX) |
| `write_command`, `write_time`, `reading_ccc_changed` | Bluetooth (RX) |
| `auth_passkey_display`, `auth_cancel`, `pairing_complete`, `pairing_failed` | Bluetooth (RX) |
| `recycled` → `adv_work_handler` | Bluetooth → system workqueue |
| `ble_init`, `ble_submit`, `ble_flush`, `ble_pending`, `ble_clear_bonds` | `main` |

| Dato compartido | Lo escribe | Lo lee | Protección |
|---|---|---|---|
| `time_set`, `utc_ref`, `utc_ref_uptime` | `write_time` (BT) | `ble_flush` (main) | **Spinlock** (64 bits + coherencia) |
| `cur_conn` | `connected`/`disconnected` (BT) | `ble_flush`, `ble_clear_bonds` (main) | **Mutex + conteo de referencias** |
| `ring`, `ring_head`, `ring_count` | main | main | Ninguna: un solo dueño |
| `cmd` | `ble_init` (main) | `write_command` (BT) | Ninguna: se escribe **antes** de `bt_enable`, cuando aún no puede llegar ningún comando |
| `recalibrate`, `interval_s`, `vibration_on` (en `main.c`), `tolerance_deg` (en `posture.c`) | BT (comandos) | main | `volatile`, un solo valor de ≤ 32 bits |

## Recorrido: una primera conexión en el log

Esto es lo que **debería** verse en el RTT la primera vez que se conecta el móvil. Aún no está probado, y el orden exacto de algunas líneas (MTU, seguridad) puede variar según el móvil:

```
BLE: anunciandose como "CorPost"                   adv_work_handler
BLE: conectado a 4F:...:12 (random)                connected
BLE: parametros iniciales intervalo=45.00 ms ...   connected
  CODIGO DE EMPAREJAMIENTO: 482913                 auth_passkey_display  (se teclea en el móvil)
BLE: seguridad nivel 4 (LE Secure Connections...)  security_changed
BLE: emparejamiento completado, bond guardado      pairing_complete
BLE: MTU actualizado tx=247 rx=247                 mtu_updated
BLE: parametros actualizados intervalo=... ms ...  le_param_updated      (unos 5 s después)
BLE hora UTC = 1793800000                          write_time            (la app escribe Time)
BLE notificaciones de Reading activadas            reading_ccc_changed   (la app se suscribe)
[45 s] BAD angulo=39.4 std_mg=1.2 validas=50/50    main
  BLE: 3 lectura(s) enviada(s), 0 pendiente(s)     ble_flush             (las 2 de antes + la nueva)
```

## Preguntas de comprobación

1. La app escribe `01 02 00` en Command. ¿Qué pasa?
2. ¿Y si escribe `03 00`?
3. Un móvil **sin emparejar** escribe `03` en Command. ¿Se ejecuta `write_command`?
4. Con un búfer de 5 entradas y el móvil desconectado, se toman 7 lecturas. ¿Cuántas se envían al reconectar y cuáles?
5. ¿Por qué `ble_flush` no mantiene el mutex mientras llama a `bt_gatt_notify`?
6. ¿Por qué el ángulo se copia con `memcpy` en lugar de `(uint32_t)e->angle`?
7. Si la app nunca escribe la hora, ¿qué ocurre?

### Respuestas

1. **Error *Value Not Allowed*.** `02 00` es 2 s, por debajo del mínimo de 5 s. El intervalo no cambia y la app recibe el error del *write*.
2. **Error *Invalid Attribute Length*.** Recalibrar no lleva parámetro y la longitud tiene que ser exactamente 1.
3. **No.** El permiso `WRITE_AUTHEN` lo comprueba la pila antes de llamarla, y responde *Insufficient Authentication*. Normalmente el móvil reacciona iniciando el emparejamiento.
4. **5: de la 3ª a la 7ª.** La 6ª sobrescribió a la 1ª y la 7ª a la 2ª. Queda `head = 2`, `count = 5`, `tail = (2 − 5 + 5) % 5 = 2`: la posición de la 3ª.
5. **Para evitar un *deadlock*.** `bt_gatt_notify` puede esperar a que se libere un buffer. Si el enlace se cae en ese momento, el hilo de Bluetooth llama a `disconnected`, que necesita el mutex. Si lo tuviera `ble_flush`, cada hilo esperaría al otro para siempre.
6. **Porque el cast convierte el valor, no los bits.** 39,4 pasaría a ser 39 y en el paquete aparecería un entero, no un `float` IEEE-754. `memcpy` copia los 4 bytes tal cual.
7. **No se envía nada.** `link_ready` es falso, las lecturas se acumulan, al llenarse el búfer se sobrescriben las más antiguas, y el RTT muestra `enlace no listo`.

---

# Lección 7: [main.c](src/main.c), donde se une todo

## Bloque 1: hardware y estado compartido (líneas 34-46)

```c
static const struct device *i2c = DEVICE_DT_GET(DT_NODELABEL(arduino_i2c));
```
- **`DT_NODELABEL(arduino_i2c)`** busca en el devicetree el nodo con la etiqueta `arduino_i2c`: el bus I²C de los pines Arduino del DK, que modificamos con `app.overlay`.
- **`DEVICE_DT_GET(...)`** devuelve un puntero al **driver** de ese bus.
- Todo esto se resuelve **en tiempo de compilación**. Si el nodo no existiera, el programa no compilaría. Es mejor que descubrirlo al ejecutar.

```c
static const struct gpio_dt_spec button1 = GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios);
static const struct gpio_dt_spec button2 = GPIO_DT_SPEC_GET(DT_ALIAS(sw1), gpios);
static struct gpio_callback button1_cb, button2_cb;
```
- **`DT_ALIAS(sw0)` y `DT_ALIAS(sw1)`** son alias estándar: en la placa nrf52dk son el **Botón 1** y el **Botón 2**.
- **`gpio_dt_spec`** agrupa tres datos: qué puerto GPIO, qué pin y si el botón es activo a nivel alto o bajo. En el DK, al pulsar, el pin va a 0 V. Gracias a esta estructura no hay que saberlo: Zephyr lo traduce. El mismo código funcionaría en otra placa con los botones en otros pines.
- **`button1_cb` y `button2_cb`** son las estructuras con las que Zephyr registra cada *callback*. Deben ser **globales** y no locales: Zephyr guarda un puntero a ellas, así que tienen que existir mientras el programa corra.

```c
static volatile bool recalibrate;
static volatile bool clear_bonds;
static volatile uint16_t interval_s = MEASURE_INTERVAL_S;
static volatile bool vibration_on = true;
```
Son las variables que se modifican "desde fuera" del hilo principal:

| Variable | La modifica | La usa el bucle para |
|---|---|---|
| `recalibrate` | Interrupción del Botón 1 y comando 0x03 (hilo BT) | Recalibrar |
| `clear_bonds` | Interrupción del Botón 2 | Borrar el emparejamiento |
| `interval_s` | Comando 0x01 (hilo BT). Empieza en `MEASURE_INTERVAL_S` | La duración de cada ciclo |
| `vibration_on` | Comando 0x04 (hilo BT) | Decidir si vibra |

- **`volatile`** obliga al compilador a leerlas de memoria cada vez. Si no, podría "optimizar" un bucle leyéndolas una sola vez y no ver nunca el cambio.
- **No necesitan lock:** cada una es un solo valor de 8 o 16 bits, que el procesador escribe en una instrucción (la misma razón que `tolerance_deg` en la lección 4).

```c
static struct imu_sample win[WINDOW_SAMPLES];
static bool win_ok[WINDOW_SAMPLES];
```
Son 50 × 12 B = 600 B de muestras, más 50 B de banderas. Se declaran **globales** y no dentro de `capture_window` por una lección importante de sistemas embebidos:
- **La pila (*stack*) de cada hilo es pequeña.** En esta configuración, el hilo de `main` tiene 2 KB (`CONFIG_MAIN_STACK_SIZE=2048`). Meter 650 B en la pila se comería un tercio de ella. Si se desborda, el programa se cuelga o corrompe memoria de forma aleatoria, y son de los fallos más difíciles de depurar.
- **Las variables `static` van en RAM fija,** reservada al compilar. Están incluidas en los 37 KB del informe de la compilación, la mayoría de los cuales son de la pila Bluetooth.

## Bloque 2: `print_f1` (líneas 48-54)

El `printk` de Zephyr **no imprime `float`** por defecto: habría que activar `CONFIG_CBPRINTF_FP_SUPPORT`, que ocupa flash. Así que se imprime "a mano" con un decimal:
```c
int t = (int)(v * 10.0f + (v >= 0 ? 0.5f : -0.5f));   // 39,44 → 394,9 → 394 (redondeado)
printk("%s=%s%d.%d ", label, t < 0 ? "-" : "", abs(t) / 10, abs(t) % 10);  // "39.4"
```
- El `± 0.5f` **redondea** al entero más cercano en lugar de truncar.
- El signo se imprime aparte. Si no, −0,5 daría `t = −5`, `−5 / 10 = 0` y `−5 % 10 = −5`, e imprimiría "0.-5".

## Bloque 3: los botones (líneas 56-78)

```c
static void on_button1(const struct device *dev, struct gpio_callback *cb, uint32_t pins)
{
	recalibrate = true;
}
```
- Cuando pulsas, el hardware **interrumpe** lo que esté haciendo la CPU y ejecuta esta función. Esto se llama contexto de interrupción, o **ISR**.
- **Regla de oro: dentro de una ISR, lo mínimo.** Nada de esperas, ni de I²C, ni de llamadas a la pila Bluetooth. Por eso `on_button2` **no** llama a `ble_clear_bonds`: borrar los bonds escribe en flash y puede esperar, algo prohibido en una ISR. Solo levanta la bandera `clear_bonds`, y lo hace el hilo principal (bloque 6).
- Los parámetros (`dev`, `cb`, `pins`) los exige la firma de Zephyr; aquí no se usan.

```c
static void button_setup(const struct gpio_dt_spec *b, struct gpio_callback *cb,
			 gpio_callback_handler_t handler)
{
	...
	gpio_pin_configure_dt(b, GPIO_INPUT);                         // el pin es una entrada
	gpio_pin_interrupt_configure_dt(b, GPIO_INT_EDGE_TO_ACTIVE);  // interrumpe al pulsar
	gpio_init_callback(cb, handler, BIT(b->pin));                 // qué función, para qué pin
	gpio_add_callback(b->port, cb);                               // registrarlo
}
```
- **Antes había un solo botón** y la función `button_init` lo configuraba directamente. Con dos botones, en lugar de copiar el código, la función recibe como parámetros **qué botón**, **qué estructura de callback** y **qué función llamar**. Es el principio *DRY* (*don't repeat yourself*).
- **`gpio_callback_handler_t`** es un tipo de Zephyr que significa "puntero a una función con la firma de un callback de GPIO". Pasar una función como parámetro es la misma idea que `ble_cmd_handlers` (lección 5).
- **`EDGE_TO_ACTIVE`** dispara la interrupción en el **flanco**, el instante en que el botón pasa a pulsado. No mientras se mantiene pulsado.
- **`BIT(b->pin)`** es `1 << pin`: una máscara que indica a qué pines responde el callback.
- **Rebotes:** al pulsar un botón mecánico, el contacto "rebota" durante unos milisegundos y puede generar varias interrupciones. No importa: poner la bandera a `true` varias veces es lo mismo que una (**idempotencia**).
- **En un producto,** borrar el emparejamiento con una simple pulsación sería demasiado fácil de hacer sin querer. Se pediría, por ejemplo, mantenerlo pulsado 5 s.

## Bloque 4: los comandos BLE (líneas 80-106)

```c
static void cmd_set_interval(uint16_t s)
{
	interval_s = s;
}
...
static const struct ble_cmd_handlers cmd_handlers = {
	.set_interval = cmd_set_interval,
	.set_tolerance = cmd_set_tolerance,
	.recalibrate = cmd_recalibrate,
	.set_vibration = cmd_set_vibration,
};
```
- **Son las cuatro funciones de la "ficha"** que se le pasa a `ble_init` (lección 5). Se ejecutan en el **hilo de Bluetooth**, así que siguen la regla de la ISR: solo guardan el valor o levantan una bandera.
- **El nombre de una función sin paréntesis** (`cmd_set_interval`) es su dirección. Eso es lo que se guarda en cada campo.
- **`const`** hace que la ficha vaya en flash y nadie pueda cambiarla.
- **`cmd_set_tolerance`** recibe un `uint8_t` y llama a `posture_set_tolerance`, que espera un `float`. C hace la conversión sola.

**El viaje completo de un comando**, por ejemplo "tolerancia 10°" (`02 0A`):
```
móvil escribe 02 0A en Command
 → radio / controlador de Nordic
 → host de Zephyr (hilo BT): ¿enlace autenticado? sí
 → write_command (ble.c): opcode 0x02, longitud 2, 10 entre 1 y 90 → válido
 → cmd->set_tolerance(10)
 → cmd_set_tolerance (main.c)
 → posture_set_tolerance(10.0f) (posture.c): tolerance_deg = 10
 → la siguiente ventana se evalúa con 10°
```

## Bloque 5: medida y calibración (líneas 108-162)

### `scan` (líneas 109-120)
Recorre las direcciones **0x08 a 0x77** e imprime las que contestan con ACK. Es el rango válido de direcciones de 7 bits; 0x00-0x07 y 0x78-0x7F están reservadas por el estándar I²C. Es lo que imprimió `Dispositivos I2C: 0x29 0x38`.

### `capture_window`: muestrear con deadline (líneas 122-137)
```c
int64_t next = k_uptime_get();
for (...) {
	win_ok[i] = (bno055_read(&win[i]) == 0);
	next += SAMPLE_PERIOD_MS;
	int64_t wait = next - k_uptime_get();
	if (wait > 0) k_msleep(wait);
}
```
`k_uptime_get()` devuelve los milisegundos desde el arranque, en `int64_t`. Hay dos formas de muestrear cada 40 ms:

| Forma | Qué pasa si una lectura tarda 5 ms más |
|---|---|
| `leer(); k_msleep(40);` | Cada ciclo dura 40 + lo que tarde la lectura. El error se **acumula** y la ventana dura más de 2 s |
| **Deadline** (la nuestra) | Se apunta al instante exacto `inicio + i × 40`. Si una lectura tarda más, se duerme menos. **No se acumula** |

El `if (wait > 0)` cubre el caso de que una lectura tarde más de 40 ms, por ejemplo con muchos reintentos: no se duerme y se pasa a la siguiente. `win_ok[i]` guarda `true` si la lectura fue bien; es la bandera que luego usa `posture.c` para saltar las muestras perdidas.

### `calibrate` (líneas 139-162)
```c
recalibrate = false;
...
while (1) {
	capture_window();
	posture_window_stats(win, win_ok, WINDOW_SAMPLES, &r);
	if (r.n_valid >= MIN_VALID_SAMPLES && r.amag_std_mg <= MOTION_STD_MG) break;
	...
}
posture_set_reference(r.acc_mean);
...
vibro_pulse(1000, 150, 60);
```
- Toma ventanas hasta que una sea **quieta y completa**, con el mismo criterio que el filtro de movimiento. Usa `posture_window_stats` y no `posture_eval` porque aún **no hay referencia** con la que calcular ángulos. En la prueba, la primera ventana salió `std_mg=235` (el usuario aún se estaba colocando) y se repitió.
- `r` se declara **fuera** del `while` para poder usarla después del `break`.
- Guarda la referencia y da un pulso corto y suave (150 ms al 60 %) como confirmación, para que el usuario sepa que ya puede moverse sin mirar el log.
- **Cambio respecto a la versión sin BLE: la bandera se baja al principio,** no al final. Antes, una pulsación **durante** la calibración se perdía. Ahora la recalibración puede pedirla también la app (comando 0x03), y es mejor no perder una petición: si llega durante la calibración, al terminar se hace otra.

## Bloque 6: `service_ble` (líneas 164-172)

```c
static void service_ble(void)
{
	if (clear_bonds) {
		clear_bonds = false;
		ble_clear_bonds();
	}
	ble_flush();
}
```
Son las tareas de BLE que se atienden **mientras se espera** al siguiente intervalo (bloque 7):
- **Borrar el emparejamiento** si se pulsó el Botón 2, ya en el hilo principal (bloque 3).
- **Enviar lo pendiente.** Si el móvil se reconecta en mitad de la espera, la ráfaga con las lecturas acumuladas sale enseguida, sin esperar a la siguiente medida. Si no hay nada pendiente, `ble_flush` vuelve al instante.

## Bloque 7: `main` (líneas 174-260)

### Arranque (líneas 176-208)

| Paso | Si falla |
|---|---|
| `device_is_ready(i2c)`: comprueba que el driver del bus se inicializó | `return 0`: no hay nada que hacer sin bus |
| `k_msleep(3000)` | No puede fallar. Da tiempo a conectar el visor RTT (si no, se pierden las primeras líneas, como pasó en las pruebas) y al BNO055 a arrancar (necesita unos 650 ms) |
| `scan()` | Solo informativo |
| `bno055_init` | `return 0`: **sin sensor, el dispositivo no sirve** |
| `vibro_init` | **Sigue funcionando**, solo avisa |
| `button_setup` (×2) | Avisa y sigue sin ese botón |
| `ble_init` | **Sigue funcionando** sin enviar datos |
| `calibrate()` | No falla: repite hasta que el usuario esté quieto |

Es una decisión de diseño: **degradar con elegancia**. Lo imprescindible (el sensor) detiene el programa; lo accesorio no. El BLE entra en lo accesorio porque el D3 pide que el dispositivo funcione de forma autónoma: mide y vibra aunque no haya móvil.

**`ble_init` va antes de `calibrate`** para que el móvil pueda conectarse y emparejarse mientras el usuario se calibra. Las lecturas no se pierden aunque aún no haya conexión: se acumulan en el búfer.

En Zephyr, que `main` termine con `return` **no apaga** el dispositivo: solo acaba ese hilo. Los hilos de Bluetooth seguirían funcionando.

### El temporizador de vibración (línea 210)
```c
int64_t last_vib = -((int64_t)VIB_MIN_INTERVAL_S * 1000) - 1;
```
- **Inicializa "la última vibración"** en un instante **del pasado** suficientemente lejano. Así, la primera vez que salga BAD, `ahora − last_vib` ya supera el intervalo mínimo y vibra.
- **El cast `(int64_t)`** hace la multiplicación en 64 bits. Con 300 s no habría problema en 32 bits, pero es un buen hábito: multiplicar constantes en `int` (32 bits con signo) desborda a partir de unos 2.147 millones.

### El bucle principal (líneas 212-258)

| Paso | Líneas | Qué hace |
|---|---|---|
| 1 | 213 | `t0 = k_uptime_get()`: apunta cuándo empieza el ciclo |
| 2 | 215-217 | Recalibra si lo ha pedido el Botón 1 o la app |
| 3 | 219-222 | Captura la ventana de 2 s y la evalúa |
| 4 | 224 | `now = k_uptime_get()`: el instante de la lectura. Se usa para el log, para la vibración y como hora de la lectura en `ble_submit` |
| 5 | 226-231 | Informa por RTT: el estado y, si no es INVALID, el ángulo |
| 6 | 233-239 | Vibra si es BAD, **la vibración está activada** (`vibration_on`, comando 0x04) y ha pasado el intervalo mínimo. `last_vib` se actualiza aunque la vibración falle, para no reintentar en bucle |
| 7 | 241-245 | **Guarda la lectura en el búfer y la intenta enviar.** Si `ble_flush` no envía nada, lo dice y muestra cuántas hay acumuladas |
| 8 | 247-250 | Imprime las estadísticas del bus I²C |
| 9 | 254-257 | Espera hasta el siguiente ciclo |

**La espera:**
```c
while (!recalibrate && k_uptime_get() - t0 < (int64_t)interval_s * 1000) {
	service_ble();
	k_msleep(100);
}
```
- **Usa `interval_s`, no la constante:** la duración del ciclo la puede cambiar la app. Como se relee en cada vuelta, un comando 0x01 afecta a la espera en curso. Si el nuevo intervalo es menor que el tiempo ya transcurrido, la espera termina en la siguiente vuelta y se mide enseguida.
- **`(int64_t)`:** `interval_s` puede llegar a 3600, y 3600 × 1000 cabría en 32 bits, pero así se compara en 64 bits con el resultado de `k_uptime_get()` sin conversiones raras.
- **Cada 100 ms**, `service_ble` atiende el BLE y se comprueba la bandera `recalibrate`. Si se pulsa el botón o la app pide recalibrar, la espera se corta.

**Cronología de un ciclo BAD con el móvil conectado:**
```
t0     captura 2 s       evalúa  vibra 0,8 s  envía   espera (service_ble cada 100 ms)   t0 + interval_s
|────────────────────────|──|──────────────|──|───────────────────────────────────────|
```

### Hilos y energía
- **`k_msleep` no es una espera activa.** El hilo se duerme y, si no hay nada más que hacer, Zephyr pone la CPU en reposo. Es la base del bajo consumo que exige el D3.
- **Mientras `main` duerme, el BLE sigue funcionando.** La radio la gestiona el controlador de Nordic, en interrupciones de máxima prioridad, y los mensajes del móvil los procesa el hilo de Bluetooth.
- **Prioridades:** en Zephyr, **un número menor significa más prioridad**. `main` tiene prioridad 0 y el hilo de Bluetooth, 8, así que `main` va **por delante**. Funciona porque `main` pasa casi todo el tiempo dormido (`k_msleep`) o esperando al bus I²C, y en esos huecos se ejecuta el hilo de Bluetooth. Un `main` que calculara sin parar nunca dormiría y dejaría sin ejecutar al hilo de Bluetooth. Es otro motivo para no hacer esperas activas.
- **Despertarse cada 100 ms** para mirar las banderas y llamar a `ble_flush` es una pequeña ineficiencia. La alternativa limpia sería un **semáforo** (`k_sem_take` con timeout): la ISR, los comandos o la reconexión "darían" el semáforo y el hilo dormiría hasta que pasara el tiempo o hubiera algo que hacer. Para el PoC, alimentado por USB, no importa.

## Preguntas de comprobación

1. ¿Por qué `win` y `win_ok` son globales en lugar de variables locales de `capture_window`?
2. Llevas 10 s de una espera de 15 s y la app envía el comando 0x01 con 5 s. ¿Cuándo empieza la siguiente medida?
3. ¿Por qué `on_button2` no llama directamente a `ble_clear_bonds`?
4. Si `ble_init` falla al arrancar, ¿vibra el dispositivo cuando la postura es mala?
5. Si quitaras `volatile` de `interval_s`, ¿qué podría pasar?
6. Si `VIB_MIN_INTERVAL_S` fuera 300 y el usuario mantuviera la mala postura 2 minutos, ¿cuántas veces vibraría con el intervalo de 15 s?

### Respuestas

1. **Por el tamaño de la pila.** Juntos ocupan unos 650 B, y la pila del hilo de `main` es de 2 KB. Como variables locales se comerían un tercio y podrían desbordarla; como `static` van en RAM fija reservada al compilar.
2. **Como mucho unos 100 ms después.** En la siguiente vuelta de la espera, `k_uptime_get() − t0` (10 s) ya no es menor que 5 s, así que el bucle termina y empieza otro ciclo.
3. **Porque se ejecuta en una interrupción.** `ble_clear_bonds` borra datos de la flash y corta la conexión, operaciones que pueden esperar y no están permitidas en una ISR. La interrupción solo levanta la bandera y el hilo principal lo hace en `service_ble`.
4. **Sí.** El fallo del BLE solo se avisa por RTT y el programa sigue. Medir y vibrar no dependen del BLE; las lecturas se guardarían en el búfer sin enviarse nunca.
5. **El compilador podría leer `interval_s` una sola vez** antes del bucle de espera, porque dentro del bucle nada parece modificarla. Un comando 0x01 no afectaría a la espera en curso ni, en el peor caso, a las siguientes. Depende de las optimizaciones, que es justamente por lo que este tipo de fallo es traicionero.
6. **Una vez.** En 2 minutos hay unas 8 medidas BAD. La primera vibra, y la siguiente vibración solo se permitiría 300 s (5 min) después, que es más que los 2 minutos.
