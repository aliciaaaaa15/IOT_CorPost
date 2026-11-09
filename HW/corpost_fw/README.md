# corpost_fw – Firmware del dispositivo CorPost (Proof of Concept)

Firmware del nRF52832 que lee el acelerómetro y el giroscopio, decide si la postura es correcta, activa el vibrador si no lo es y envía cada lectura a la app por **Bluetooth Low Energy (BLE)** con emparejamiento seguro.

Este documento explica cómo funciona el código, qué decisiones se tomaron y por qué. Muchas de esas decisiones se entienden mejor sabiendo los problemas que aparecieron durante las pruebas, y por eso se cuentan en la sección 4.

---

## Resumen rápido

- **Hardware:** nRF52-DK (nRF52832) → Arduino Modulino Vibro (I²C, 0x38) → Atmel BNO055 Xplained Pro (I²C, 0x29).
- **Ciclo:**
  1. Calibra la postura de referencia.
  2. Cada 15 s mide una ventana de 2 s (50 muestras a 25 Hz).
  3. Clasifica la ventana como **OK**, **BAD** o **INVALID**.
  4. Si es BAD, vibra.
  5. Envía la lectura por BLE (paquete de 24 B). Si no hay conexión, la guarda en un búfer de 50 lecturas y la envía al reconectar.
- **BLE:** servicio GATT propio con las características Reading (Notify), Command (Write) y Time (Write). Seguridad: LE Secure Connections con passkey, bonding y un solo móvil emparejado. Ver secciones 7 y 8.
- **Estado:**
  - **Medida, postura y vibración:** probadas en el montaje real. Funcionan los tres estados, la vibración, la calibración y la recalibración con el botón (ver sección 5).
  - **BLE:** compila, pero **aún no está probado con el móvil**. La guía de prueba está en la sección 8.7.

---

## 1. Conceptos previos

### Zephyr y cómo se construye el programa

En el microcontrolador no hay sistema operativo de PC. El programa se compila junto con **Zephyr**, un sistema operativo pequeño para microcontroladores que forma parte del nRF Connect SDK. Todo junto se graba en la memoria flash del nRF52832. Hay tres archivos de configuración:

| Archivo | Qué es | Analogía |
|---|---|---|
| [CMakeLists.txt](CMakeLists.txt) | Qué archivos `.c` se compilan | El CMake de un proyecto C/C++ |
| [prj.conf](prj.conf) | Qué partes de Zephyr se activan: I²C, GPIO, FPU, consola RTT. Es el sistema **Kconfig** | Flags de compilación o `#define` globales |
| [app.overlay](app.overlay) | **Devicetree**: describe el hardware (qué periférico, qué pines, a qué velocidad) | Un archivo de configuración del hardware |

La placa ya trae su propio devicetree (`nrf52dk`), que dice por ejemplo "el bus I²C llamado `arduino_i2c` usa los pines P0.26 (SDA) y P0.27 (SCL)". Nuestro `app.overlay` lo modifica: cambia el periférico a **TWIM**, fija la velocidad a **100 kHz** y activa los **pull-ups internos**. El motivo se explica en la sección 1.4 y en la sección 4.

`west build` lo compila todo y genera `zephyr.hex`. El *flash* lo graba por **SWD** usando el J-Link que lleva integrado el propio DK. **RTT** (Real Time Transfer) es un canal que lee los `printk` del programa a través del mismo J-Link, así que no hace falta puerto serie.

### I²C: el bus que lo conecta todo

- **Dos cables:** SDA (datos) y SCL (reloj), más 3,3 V y GND. El nRF es el **maestro**, que genera el reloj e inicia todas las comunicaciones. El BNO055 y el Vibro son **esclavos**, cada uno con una dirección de 7 bits (0x29 y 0x38).
- **Las líneas son "open-drain":** los chips solo pueden tirar la línea a 0, y una resistencia (**pull-up**) la devuelve a 1 cuando nadie la tira.
  - Con **cables largos y pull-ups débiles**, la línea tarda en subir, y el maestro puede leer un 1 donde debería haber un 0 o al revés.
  - Esto es importante para entender los problemas de la sección 4.
- **Cada esclavo confirma con un ACK** cada byte que recibe. Si no contesta (**NACK**), Zephyr devuelve el error `-EIO` = **−5**.
  - Es el error que se ve cuando un dispositivo no está conectado o el bus falla.
  - En las primeras pruebas con `vibro_test`, el Vibro devolvía −5 simplemente porque estaba desconectado.

### Registros

Un sensor como el BNO055 se maneja como una pequeña memoria: cada dirección (**registro**) tiene un significado. Por ejemplo, `0x00` es el ID del chip (vale `0xA0`), `0x08`/`0x09` son la aceleración X y `0x3D` es el modo de funcionamiento. Las operaciones son:

- **Escribir un registro:** se envían 2 bytes, la dirección del registro y el valor.
- **Leer un registro:** se escribe la dirección del registro y, sin soltar el bus (*repeated start*), se leen N bytes. En Zephyr es `i2c_write_read`. Si se piden varios bytes, el sensor va devolviendo los registros consecutivos (lectura "en ráfaga").

Los valores de 16 bits ocupan dos registros, **LSB** (byte bajo) y **MSB** (byte alto), en *little-endian*. `sys_get_le16(b)` hace `b[0] | (b[1] << 8)` y lo convierte en `int16_t`.

### TWI, TWIM y EasyDMA: qué son y por qué usamos TWIM

- **TWI** (*Two-Wire Interface*) es el nombre que usa Nordic para I²C. Es el mismo protocolo, con otro nombre por motivos de marca.
- El nRF52832 tiene bloques de hardware (periféricos) que implementan I²C, y cada uno puede funcionar en tres variantes:

  | Variante | Qué hace | Cómo se mueven los bytes |
  |---|---|---|
  | **TWI** | Maestro I²C "clásico" (*legacy*) | La **CPU** mueve cada byte: escribe un byte en un registro del periférico, espera la interrupción, escribe el siguiente… Nordic lo considera obsoleto (*deprecated*) en el nRF52832 |
  | **TWIM** | Maestro I²C con **EasyDMA** (la M es de *Master*) | El periférico lee y escribe los bytes **directamente en la RAM**, sin la CPU |
  | **TWIS** | Esclavo I²C con EasyDMA | No lo usamos: el nRF es el maestro |

- **EasyDMA** es el motor de DMA (*Direct Memory Access*) integrado en los periféricos de Nordic.
  - La CPU solo indica "envía estos N bytes de este buffer y guarda lo recibido en este otro buffer" y arranca la transferencia; el periférico hace el resto.
  - Ventajas: menos trabajo para la CPU y una temporización del bus que no depende de lo ocupada que esté la CPU.
  - Limitaciones en el nRF52832: los buffers deben estar en **RAM**, no en flash, y como máximo pueden tener **255 bytes** por transferencia. Ninguna de las dos nos afecta.
- **Por qué TWIM:**
  - El devicetree de la placa usa por defecto el **TWI** legacy. Lo cambiamos a **TWIM** porque es la variante recomendada y mantenida.
  - También servía para descartar que el driver fuese la causa de los errores de lectura (sección 4). **No los resolvió**, pero lo mantenemos por ser la opción correcta.
  - En el mismo overlay fijamos **100 kHz**, el modo estándar y más tolerante con cables largos, y activamos los **pull-ups internos** de SDA/SCL. Son de unos 13 kΩ: ayudan algo, pero no sustituyen a los de 4,7 kΩ que se suelen poner externamente.

---

## 2. Los módulos

En C no hay clases, así que el código se organiza en "módulos": un `.h` con la interfaz pública y un `.c` con la implementación. Las variables y funciones marcadas `static` dentro de un `.c` son **privadas de ese archivo**. Los errores se devuelven como `int`: 0 significa que todo ha ido bien y un valor negativo es un error, por ejemplo `-EIO` o `-ENODEV`.

### [src/config.h](src/config.h): parámetros

Solo contiene `#define`. Para ajustar el comportamiento se cambia aquí y se recompila.

| Parámetro | Valor actual | Significado |
|---|---|---|
| `SAMPLE_PERIOD_MS` / `WINDOW_SAMPLES` | 40 ms / 50 | Ventana de 2 s a 25 Hz, como en el D3 |
| `MIN_VALID_SAMPLES` | 40 | Si se pierden más de 10 muestras por errores del bus, la ventana es INVALID |
| `MEASURE_INTERVAL_S` | 15 s | Intervalo **inicial** entre medidas. Es un valor de desarrollo (el D3 dice 1, 3 o 5 min); el definitivo se decidirá tras las pruebas. La app lo cambia con el comando 0x01 (entre `MEASURE_INTERVAL_MIN_S` = 5 s y `MEASURE_INTERVAL_MAX_S` = 3600 s) |
| `TOLERANCE_DEG` | 15° | Tolerancia **inicial**: desviación respecto a la referencia a partir de la cual la postura es BAD. La app la cambia con el comando 0x02 (de 1° a 90°) |
| `BUFFER_SIZE` | 50 | Lecturas que caben en el búfer circular mientras no hay conexión BLE (D3) |
| `BATTERY_LEVEL` | 0xFF | Valor del campo "batería" del paquete. El PoC no tiene batería, así que se envía 0xFF = "no disponible" |
| `MOTION_STD_MG` | 42 mg | Umbral del filtro de movimiento **provisional** (sección 2, posture.c) |
| `VIB_MIN_INTERVAL_S` | 0 s | Tiempo mínimo entre dos vibraciones. 0 en desarrollo (vibra en cada BAD); el D3 dice 5 min |

### [src/bno055.c](src/bno055.c): el sensor

- **`bno055_init`:**
  1. Prueba las dos direcciones posibles del BNO055 (0x28 y 0x29) leyendo el registro `CHIP_ID`, y se queda con la que devuelve `0xA0`. En nuestro montaje es **0x29**.
  2. Pone el chip en **modo CONFIG**, porque solo en este modo acepta cambios de configuración.
  3. Configura las unidades: aceleración en **mg** (1 LSB = 1 mg, incluye la gravedad) y giro en **°/s** (1 LSB = 1/16 °/s).
  4. En la **página 1** del mapa de registros (se cambia con `PAGE_ID`), configura el rango y el **filtro paso bajo interno**: acelerómetro ±4 g y 15,6 Hz, giroscopio ±2000 °/s y 12 Hz. El motivo del filtro está en la sección 4.
  5. Vuelve a la página 0 y activa el modo **ACCGYRO**: acelerómetro y giroscopio, sin la fusión de sensores del chip.

  `err |= wr(...)` acumula los errores: si alguna escritura falla, `err` deja de ser 0 y la función lo indica.
- **`read_i16_once`:** lee los 2 bytes (LSB + MSB) de un eje en **una transacción de 2 bytes**. Si el bus da error, reintenta hasta 3 veces.
- **`read_i16`:** llama dos veces seguidas a `read_i16_once` y solo acepta el valor si ambas lecturas se parecen (diferencia ≤ 200 LSB). Es una protección contra bytes corruptos.
- **`bno055_read`:** lee los 6 ejes (3 de aceleración y 3 de giro) llamando a `read_i16` para cada uno.

  Leer cada eje por separado en vez de los 12 bytes de golpe es un *workaround*: con el cableado actual, las lecturas de más de 2 bytes seguidos se corrompen (sección 4).
- **`stats`:** cuenta los reintentos, las discrepancias (dobles lecturas que no coincidían) y las muestras perdidas. Son las líneas `bus:` que se ven en el log.

### [src/vibro.c](src/vibro.c): el actuador

El Modulino Vibro tiene **su propio microcontrolador**. No controlamos el motor directamente: le enviamos una orden de 12 bytes (frecuencia, duración en ms y potencia de 0 a 100, cada uno como `uint32` little-endian) y él se encarga de vibrar.

- **`vibro_init`:** solo comprueba que el Vibro responde en la dirección 0x38.
- **`vibro_pulse`:** envía la orden, con reintentos. **No bloquea:** el Vibro vibra solo durante los ms indicados mientras el nRF sigue a lo suyo.
- **`vibro_alert`:** el aviso de mala postura, dos pulsos de 300 ms separados. Esta función sí espera (`k_msleep`) para que el segundo pulso no pise al primero.

### [src/posture.c](src/posture.c): la lógica de postura

- **`posture_window_stats`** calcula dos cosas sobre las muestras válidas de la ventana:
  - **El vector medio de aceleración.** Con el usuario quieto, el acelerómetro solo mide la **gravedad**, así que este vector indica hacia dónde está "abajo" desde el punto de vista del sensor. De ahí sale la orientación y, por tanto, la postura.
  - **La desviación estándar del módulo `|a|`.**
    - Quieto, `|a|` vale unos 1000 mg (1 g) y casi no varía: en las pruebas, la desviación fue de 0,6 a 2,3 mg.
    - Al moverse, la aceleración del propio movimiento se suma a la gravedad y `|a|` varía mucho: de 145 a 240 mg en las pruebas.
    - Se calcula como `sqrt(E[m²] − E[m]²)`.
- **`posture_set_reference`:** guarda el vector medio de la calibración como postura de **0°**.
- **`angle_between`:** el ángulo entre dos vectores, `cos θ = (a·b) / (|a|·|b|)`, de modo que `θ = acos(...)`.
  - Limita el coseno a [−1, 1], porque por redondeo podría salir 1,0000001 y `acos` devolvería NaN.
  - Como el ángulo se mide **respecto a la referencia** y no respecto a la vertical, no importa cómo esté orientado el sensor en la ropa.
- **`posture_eval`** decide el estado:
  1. Si hay menos de 40 muestras válidas, o la desviación de `|a|` supera 42 mg, la ventana es **INVALID**: el usuario se está moviendo y la medida no es fiable.
     - Este **filtro de movimiento es provisional.** Es un umbral simple: 42 mg sale del *baseline* del pipeline de entrenamiento con el dataset HAPT.
     - Se sustituirá por el **árbol de decisión** cuando se reentrene con nuestros datos a 25 Hz.
  2. Si no, calcula el ángulo respecto a la referencia: si supera 15° es **BAD**; si no, **OK**.

  Los valores del `enum` (OK = 0, BAD = 1, INVALID = 2) coinciden con el campo "status" del paquete BLE definido en el D3.

### [src/ble.c](src/ble.c): Bluetooth Low Energy

Todo lo relacionado con BLE: el servicio GATT, el advertising, la seguridad y el búfer de lecturas. Se explica en detalle en la sección 8; aquí, solo la interfaz que usa `main.c`:

- **`ble_init`:** registra los *callbacks* de seguridad, arranca Bluetooth (`bt_enable`), carga de la flash los emparejamientos guardados (`settings_load`) y empieza a anunciarse.
- **`ble_submit`:** guarda una lectura en el búfer circular. Si el búfer está lleno, sobrescribe la más antigua.
- **`ble_flush`:** si el enlace está listo, envía todas las lecturas pendientes como notificaciones de 24 B. "Listo" significa: conectado, con seguridad de nivel 4, con las notificaciones activadas, con MTU suficiente y con la hora UTC recibida.
- **`ble_clear_bonds`:** borra los emparejamientos guardados.
- **Los comandos de la app** llegan por el hilo de Bluetooth y se pasan a `main.c` mediante la estructura `ble_cmd_handlers`, que contiene punteros a funciones. Esas funciones solo guardan el valor o activan un *flag*, igual que la interrupción del botón, y es el bucle principal quien actúa.

### [src/main.c](src/main.c): el programa principal

- **Variables globales del hardware**, obtenidas con macros del devicetree:
  - `DEVICE_DT_GET(DT_NODELABEL(arduino_i2c))` es, **en tiempo de compilación**, un puntero al driver del bus I²C descrito en el devicetree.
  - `GPIO_DT_SPEC_GET(DT_ALIAS(sw0), gpios)` hace lo mismo con el **Botón 1** del DK: puerto, pin y si es activo a nivel alto o bajo. `sw1` es el **Botón 2**.
- **Los botones usan interrupciones:**
  - `on_button1` y `on_button2` son *callbacks* que Zephyr llama cuando se pulsa un botón. Solo ponen un *flag* (`recalibrate` o `clear_bonds`), y es el bucle principal el que actúa. Es la práctica habitual: el código que se ejecuta dentro de una interrupción debe ser mínimo.
  - Las variables son `volatile` porque las modifica una interrupción o el hilo de Bluetooth. Así el compilador no las "optimiza" leyéndolas una sola vez.
- **Los comandos BLE** (`cmd_set_interval`, `cmd_set_tolerance`, `cmd_recalibrate`, `cmd_set_vibration`) siguen la misma idea: guardan el nuevo valor en una variable y el bucle lo usa en la siguiente vuelta.
- **`capture_window`:** toma 50 muestras, una cada 40 ms, usando un ***deadline***.
  - Suma 40 ms a `next` y duerme solo lo que falta hasta ese instante (`next − ahora`). Así, si una lectura tarda más de lo normal (por ejemplo, por reintentos), el ritmo de 25 Hz no se desplaza.
  - `win_ok[i]` marca qué muestras se leyeron bien.
- **`calibrate`:** repite ventanas hasta encontrar una en la que el usuario esté quieto, guarda su vector medio como referencia y da un pulso corto de vibración como confirmación.
- **`main`:**
  1. Espera 3 s, para dar tiempo a conectar el visor RTT y a que arranque el BNO055 (necesita unos 650 ms).
  2. Escanea el bus e imprime los dispositivos encontrados.
  3. Inicializa el sensor y el Vibro. Si el Vibro no responde, sigue funcionando sin vibración.
  4. Arranca el BLE. Si falla, sigue funcionando sin enviar datos.
  5. Calibra.
  6. Repite el bucle:
     - recalibrar si se ha pulsado el botón o lo ha pedido la app;
     - capturar la ventana y evaluarla;
     - imprimir el resultado;
     - vibrar si es BAD, la vibración está activada y se respeta `VIB_MIN_INTERVAL_S`;
     - guardar la lectura en el búfer (`ble_submit`) e intentar enviarla (`ble_flush`);
     - imprimir las estadísticas del bus;
     - esperar hasta el siguiente intervalo.

     La espera se hace a trozos de 100 ms. Así el botón la puede interrumpir y, en cada trozo, `service_ble` envía lo pendiente (por ejemplo, la ráfaga del búfer justo después de reconectar) y atiende el Botón 2.
- **Detalles menores:**
  - `print_f1` existe porque el `printk` de Zephyr no imprime números `float` por defecto. Imprime con un decimal usando enteros.
  - `last_vib` empieza en un valor negativo para que la **primera** vez que salga BAD vibre aunque no haya pasado el intervalo mínimo.

---

## 3. Limitaciones conocidas

- **El filtro de movimiento es un umbral simple.** Se sustituirá por el árbol de decisión (proyecto `ai_movment_test`) reentrenado a 25 Hz con datos propios.
- **`vibro_alert` bloquea unos 0,8 s.** No afecta al BLE: la radio la gestiona el controlador de Nordic por su cuenta, y los comandos llegan por el hilo de Bluetooth, no por el principal.
- **El BLE está compilado pero aún no se ha probado con el móvil** (sección 8.7).
- **El passkey se "muestra" por RTT**, así que para emparejar hace falta el PC con el visor RTT abierto. En un producto real se usaría una pantalla o un código impreso en el dispositivo (sección 8.3).
- **El intervalo de medida y el tiempo mínimo entre vibraciones están en valores de desarrollo** (15 s y 0). El D3 dice 1, 3 o 5 min y 5 min.
- **Las lecturas de 2 bytes por eje son un workaround del cableado actual** (sección 4). Con cables cortos y pull-ups correctos se podría volver a leer en ráfaga.

---

## 4. Historial de problemas encontrados en las pruebas

Esta sección explica por qué el código es como es. Las pruebas se hicieron con proyectos intermedios (`bno055_test`, en la carpeta superior) antes de crear este.

1. **El BNO055 está en la dirección 0x29, no en 0x28.** El chip admite las dos según cómo esté cableada la placa. Por eso `bno055_init` prueba ambas.
2. **Las lecturas en ráfaga se corrompían.**
   - Al leer los 18 bytes de datos de golpe, solo los **2 primeros** eran correctos y el resto llegaba como `0xFF` o `0x00`. Además, había errores −5 intermitentes.
   - Leyendo **byte a byte**, los valores eran correctos y estables: unos 1000 mg en el eje vertical y giro cerca de 0 en reposo.
   - Conclusión: el sensor funciona y el problema está en el transporte por el bus.
   - Causa más probable, **no verificada** porque no teníamos osciloscopio ni analizador lógico: **cables largos y pull-ups débiles o inexistentes**, sumados a que el BNO055 hace *clock stretching* (retiene el reloj del bus mientras prepara los datos).
3. **Cambiar el driver no lo solucionó.**
   - Se pasó de TWI a TWIM, se fijaron 100 kHz y se activaron los pull-ups internos (`app.overlay`). El fallo fue idéntico, lo que descarta el driver como causa.
   - Se mantienen estos ajustes porque son los correctos de todas formas.
4. **Solución adoptada (workaround): leer cada eje en una transacción de 2 bytes,** que sí era fiable, con **reintentos** si el bus da error y **doble lectura** para detectar bytes corruptos.
   - Con el sensor quieto: se perdió 1 muestra de 625 (0,16 %), y unos 2 % de las lecturas necesitaron un reintento, que siempre se recuperó.
5. **Con el sensor en movimiento aparecen errores; en reposo, no.**
   - En una captura de unos 45 s en reposo hubo 0 reintentos. Al mover el sensor aparecieron reintentos, discrepancias y alguna muestra perdida, cerca del 1 %.
   - Lo más probable es que **al mover el sensor se muevan también los cables**, provocando fallos de contacto momentáneos. No está verificado.
   - Para la postura no es grave: la postura se mide con el usuario quieto, y una ventana con movimiento tiene que salir INVALID de todas formas. El firmware detecta y descarta las lecturas fallidas en lugar de usar datos corruptos.
6. **Picos aislados en movimiento.**
   - Moviendo el sensor se veían valores que saltaban mucho de una muestra a la siguiente y volvían (por ejemplo, −251 → −2200 → −219).
   - Se pensó que podía ser *aliasing*, es decir, vibraciones rápidas que, al muestrear a 25 Hz, aparecen como saltos. Para comprobarlo se bajó el filtro interno del sensor a 15,6 Hz (acelerómetro) y 12 Hz (giroscopio).
   - **Los picos no se redujeron**, así que la causa sigue sin estar clara: pueden ser golpes reales o fallos de contacto.
   - El filtro se mantiene porque es la práctica correcta al muestrear a 25 Hz.
   - Ojo: los datos de entrenamiento del árbol (grabados con el móvil) no pasaron por este filtro. Es otro motivo para reentrenar con datos del propio dispositivo.
7. **El montaje encadenado funciona:** nRF → Vibro → BNO055. El BNO055 se conecta al segundo conector del Vibro, y en el escaneo aparecen los dos dispositivos, 0x29 y 0x38.


---

## 5. Resultado de la prueba final

Secuencia probada con el montaje encadenado:

| Acción | Resultado en el log |
|---|---|
| Quieto unos 5 s (calibración) | Primera ventana rechazada por movimiento (`std_mg=235`); la segunda se toma como referencia |
| Postura igual que la referencia | `OK angulo=0.1` / `0.7` |
| Inclinado más de 15° y quieto | `BAD angulo=39.4` … `60.3` → vibración (dos pulsos) |
| Agitado mientras mide | `INVALID std_mg=144.9` / `193.0`, sin vibración |
| Vuelta a la posición inicial | `OK angulo=3.3` |

En toda la prueba, de unos 150 s, se perdió 1 muestra y ninguna ventana se vio afectada.

---

## 6. Cómo compilar, flashear y ver la salida

- **Compilar:** con la extensión nRF Connect for VS Code, o desde un terminal del nRF Connect SDK:
  ```
  west build -p always -b nrf52dk/nrf52832
  ```
- **Flashear:** con nRF Connect for VS Code, o con `west flash`.
- **Ver la salida:** con J-Link RTT Viewer, o con la terminal RTT de la extensión.
  - El programa espera 3 s al arrancar para dar tiempo a conectarse.
  - Si se pierden las primeras líneas, reinicia la placa con el visor ya abierto.
- **El RTT es imprescindible para emparejar**, porque el código de emparejamiento (passkey) aparece ahí.
- **Botones:**
  - **Botón 1:** recalibrar.
  - **Botón 2:** borrar el emparejamiento guardado (para emparejar otro móvil).
- **Flashear no borra el emparejamiento**, porque está en otra zona de la flash (la partición `storage`). Para empezar de cero, pulsa el Botón 2 o borra el chip entero (`west flash --erase`).
- **Conexiones:**
  - El nRF52-DK conecta al Modulino Vibro por **P0.26 (SDA)**, **P0.27 (SCL)**, **3,3 V** y **GND**.
  - El BNO055 Xplained Pro va al segundo conector del Vibro (mismo bus I²C).

---

## 7. Qué es BLE y cómo funciona

### 7.1 Qué es

**Bluetooth Low Energy** (BLE, o Bluetooth LE) es la versión de bajo consumo de Bluetooth, introducida en Bluetooth 4.0. **No es una mejora del Bluetooth "clásico"** de auriculares y altavoces: es un protocolo distinto que comparte con él el nombre y la banda de 2,4 GHz.

| | Bluetooth clásico | BLE |
|---|---|---|
| Pensado para | Flujo continuo (audio, ficheros) | Datos pequeños y esporádicos |
| Consumo | Alto, radio casi siempre encendida | Muy bajo, la radio duerme casi siempre |
| Velocidad | ~2-3 Mbit/s | 1 Mbit/s en el aire (2 Mbit/s con BLE 5), mucho menos de datos útiles |
| Uso típico | Auriculares, coche | Pulseras, sensores, wearables |

Encaja con CorPost porque el dispositivo envía unos pocos bytes cada X segundos y entre envío y envío no hace falta radio.

**La idea clave de BLE es que la radio está apagada casi todo el tiempo** y se despierta en momentos acordados durante unos pocos cientos de microsegundos.

### 7.2 Las capas que nos importan

BLE se organiza en capas, de abajo arriba:

| Capa | Qué hace | ¿La tocamos? |
|---|---|---|
| Física (PHY) | Radio a 2,4 GHz en 40 canales de 2 MHz: 3 de advertising y 37 de datos | No |
| Link Layer | Temporización de las conexiones, salto de canal, acuses de recibo y reintentos, cifrado AES-CCM | No: lo hace el *SoftDevice Controller* de Nordic |
| L2CAP | Divide y reúne los mensajes de las capas superiores | No |
| **ATT** | Protocolo de atributos: "lee el atributo con handle X", "escribe Y en el handle Z" | Indirectamente, por el **MTU** |
| **SMP** | Emparejamiento y generación de claves | Sí: lo configuramos (**seguridad**) |
| **GAP** | **Cómo se encuentran y se conectan** los dispositivos | Sí |
| **GATT** | **Cómo se organizan e intercambian los datos** una vez conectados | Sí |

En la práctica trabajamos con **GAP**, **GATT** y la configuración de **SMP**. El resto lo resuelve la pila Bluetooth.

### 7.3 GAP: descubrirse y conectarse

**Roles:**
- **Periférico:** anuncia que existe y espera a que se conecten. **Es el nRF52 de CorPost.**
- **Central:** busca dispositivos y decide conectarse. **Es el móvil con la app React Native.**

**Advertising (anuncio):** el periférico emite periódicamente, en los 3 canales de advertising, un paquete pequeño de hasta 31 bytes de datos. Ese paquete lleva:
- el nombre, por ejemplo "CorPost";
- el UUID del servicio, que identifica qué tipo de dispositivo es;
- *flags* (por ejemplo, "solo BLE, no Bluetooth clásico") y, opcionalmente, otros datos.

El móvil hace **scanning** (escucha esos canales), ve el anuncio, filtra por el UUID para mostrar solo dispositivos CorPost y pide la conexión.

El intervalo de advertising es un compromiso: si es más corto, el móvil lo encuentra antes, pero se gasta más energía.

**La conexión y sus parámetros.** Una vez conectados, los dos dispositivos quedan sincronizados y "se citan" periódicamente. Cada cita se llama *connection event*. Hay tres parámetros clave:

- **Connection interval** (7,5 ms - 4 s): cada cuánto se despiertan los dos para intercambiar paquetes. Fuera de esas citas, la radio duerme.
- **Slave latency** (latencia del periférico): cuántas citas puede saltarse el periférico si no tiene nada que enviar. Ahorra batería sin perder la conexión.
- **Supervision timeout:** si pasa este tiempo sin oír al otro, la conexión se da por perdida. **Es lo que dispara la desconexión** y, en nuestro diseño, el uso del búfer.

**El central (el móvil) es quien manda** en estos parámetros. El periférico solo puede proponer los que prefiere, y Android e iOS suelen imponer los suyos.

### 7.4 GATT: cómo están organizados los datos

Una vez conectados, los roles se llaman de otra forma:
- **Servidor GATT:** el que **tiene** los datos. Es el nRF52.
- **Cliente GATT:** el que **los lee o los escribe**. Es el móvil.

GATT y GAP son independientes: lo normal es que el periférico sea el servidor, pero no es obligatorio. Por ejemplo, nuestro nRF también actúa como cliente durante un momento para pedir el MTU (sección 8.1, paso 4).

Los datos del servidor están organizados en una jerarquía:

```
Servicio (UUID)                       → p. ej. "CorPost Service"
 ├─ Característica (UUID, propiedades, valor)   → p. ej. "Reading"
 │   └─ Descriptor (p. ej. CCCD)
 ├─ Característica …
```

- **Servicio:** un grupo de datos relacionados, identificado por un UUID.
- **Característica:** un dato concreto, con su UUID, su **valor** (bytes) y sus **propiedades** (qué se puede hacer con él).
- **Descriptor:** metadatos de una característica. El importante es el **CCCD** (siguiente apartado). Otro es el **CUD**, un nombre legible que muestran apps como nRF Connect.

Por debajo, cada elemento es un **atributo** con un número (*handle*). Las operaciones ATT trabajan con esos handles, y por eso el cliente hace un **descubrimiento de servicios** al conectar: averigua qué handle corresponde a cada UUID.

**UUIDs:**
- Los servicios estándar del Bluetooth SIG usan UUIDs cortos de 16 bits. Por ejemplo, 0x180F es "Battery Service".
- Los servicios propios, como el nuestro, usan **UUIDs de 128 bits** generados al azar, de modo que no chocan con nadie.

### 7.5 Las formas de intercambiar datos

| Operación | Dirección | Confirmación | Uso en CorPost |
|---|---|---|---|
| **Read** | El móvil pide y el nRF responde | Sí | No se usa |
| **Write** | Móvil → nRF | Sí (el nRF acepta o devuelve un error) | Comandos y hora |
| **Write without response** | Móvil → nRF | No | No se usa |
| **Notify** | nRF → móvil, por iniciativa propia | No a nivel de aplicación (el Link Layer sí reintenta) | **Lecturas de postura** |
| **Indicate** | nRF → móvil | Sí, el móvil confirma cada una | No se usa (es más lenta) |

La diferencia importante es **Read frente a Notify**:
- Con Read, el móvil tendría que preguntar continuamente "¿hay dato nuevo?" (*polling*), y eso gasta.
- Con **Notify**, el nRF **empuja** el dato justo cuando tiene una medida nueva, que es lo que queremos.

**CCCD: cómo se activan las notificaciones.** El nRF no puede enviar notificaciones a quien no las ha pedido. El móvil se **suscribe** escribiendo `0x0001` en el descriptor CCCD (*Client Characteristic Configuration Descriptor*) de la característica. Desde ese momento, cada notificación del nRF le llega; si escribe `0x0000`, se desuscribe. En la app nRF Connect es el botón de las tres flechas hacia abajo.

### 7.6 MTU: cuánto cabe en un mensaje

- El **ATT_MTU** es el tamaño máximo de un mensaje ATT. Por defecto es de **23 bytes**, de los que 3 son cabecera (opcode y handle), así que caben **20 bytes de datos**.
- **Nuestro paquete mide 24 bytes**, así que no cabe con el MTU por defecto: el D3 pide un MTU de al menos 27.
- Tras conectar, los dos lados negocian uno mayor (*MTU exchange*): cada uno dice el máximo que soporta y se usa el menor de los dos.
- No hay que confundirlo con el **Data Length Extension** (DLE), que es el tamaño de la trama de radio del Link Layer: 27 bytes por defecto y hasta 251. Si un mensaje ATT no cabe en una trama, L2CAP lo parte en varias. Con DLE, nuestro paquete viaja en una sola trama.

### 7.7 Seguridad: emparejamiento, cifrado y bonding

**Sin seguridad, BLE no cifra nada:** cualquiera con un móvil y nRF Connect podría conectarse, leer los datos de postura (que el D3 trata como datos de salud) y enviar comandos. Además, alguien cerca con un *sniffer* podría capturar el tráfico.

**Pairing (emparejamiento):** los dos dispositivos acuerdan una clave para cifrar el enlace. Lo gestiona la capa **SMP**. Hay dos generaciones:

- **LE Legacy Pairing (BLE 4.0/4.1):** la clave se deriva de un valor que un atacante que escuche el emparejamiento puede romper. **No se debe usar.**
- **LE Secure Connections (BLE 4.2+):** usa **ECDH** con la curva P-256. Cada lado genera un par de claves pública y privada, se intercambian las públicas y ambos calculan el mismo secreto sin que viaje nunca por el aire. Aunque alguien escuche todo el emparejamiento, no puede obtener la clave. Es lo que pide el D3.

**Autenticación: ¿hablo con quien creo?** ECDH protege contra quien escucha, pero no contra un atacante que se ponga **en medio** (*man-in-the-middle*, MITM) y haga de "dispositivo" ante el móvil y de "móvil" ante el dispositivo. Para evitarlo, el usuario debe confirmar algo que el atacante no puede ver. El método depende de lo que tenga cada dispositivo (sus **capacidades de E/S**):

| Método | Qué hace el usuario | ¿Protege contra MITM? |
|---|---|---|
| Just Works | Nada | **No** |
| Numeric Comparison | Comprueba que los dos dispositivos muestran el mismo número de 6 cifras | Sí (los dos necesitan pantalla) |
| **Passkey Entry** | Uno muestra un código de 6 cifras y el usuario lo teclea en el otro | **Sí** |
| Out of Band (OOB) | La clave se intercambia por otro medio, por ejemplo NFC | Sí |

**Niveles de seguridad** (modo 1 de LE):
- Nivel 1: sin seguridad.
- Nivel 2: cifrado sin autenticar (Just Works).
- Nivel 3: cifrado y autenticado, con *legacy pairing*.
- **Nivel 4: cifrado y autenticado con LE Secure Connections.** Es el que usamos.

**Cifrado:** con la clave acordada, el Link Layer cifra cada paquete con **AES-CCM de 128 bits**. CCM, además de cifrar, añade un código de integridad (MIC), de modo que un paquete modificado se descarta.

**Bonding:** consiste en **guardar** las claves tras el emparejamiento. En la siguiente conexión, los dos dispositivos simplemente reactivan el cifrado con la clave guardada, sin repetir el emparejamiento ni volver a pedir el código.

**Privacidad (direcciones aleatorias resolubles, RPA):**
- Si un dispositivo se anuncia siempre con la misma dirección, cualquiera puede seguir a la persona que lo lleva.
- Con privacidad, la dirección cambia periódicamente (cada 15 min por defecto). Solo los dispositivos emparejados, que tienen la clave IRK intercambiada en el bonding, saben reconocer que es el mismo.

**Permisos de las características:** cada atributo GATT declara qué nivel de seguridad exige. Si el móvil intenta leer o escribir sin cumplirlo, el servidor responde con un error (*Insufficient Authentication*). Los móviles reaccionan a ese error iniciando el emparejamiento automáticamente.

---

## 8. BLE en CorPost

### 8.1 El flujo completo

1. El nRF arranca y hace **advertising** como "CorPost", con el UUID del servicio.
2. La app **escanea**, lo encuentra filtrando por el UUID y se **conecta**.
3. El nRF pide **seguridad de nivel 4**:
   - **Primera vez:** empieza el **emparejamiento**. El nRF muestra un código de 6 cifras (por RTT en el PoC), el usuario lo teclea en el móvil y se crea el **bond**.
   - **Siguientes veces:** se reactiva el cifrado con la clave guardada, sin pedir nada.
4. El nRF pide un **MTU** de 247 y el móvil responde con el suyo. Basta con que sea ≥ 27.
5. La app **descubre** el servicio y sus tres características.
6. La app **escribe la hora UTC** en la característica **Time**, porque el nRF no tiene reloj real.
7. La app **se suscribe** (CCCD) a **Reading**.
8. Cada intervalo, el nRF mide y envía una **notificación** con el paquete de 24 B.
9. Si el usuario cambia la configuración, la app **escribe** en **Command**: intervalo, tolerancia, recalibrar o vibración.
10. Si se pierde la conexión (**supervision timeout**), el nRF sigue midiendo y vibrando, guarda las lecturas en el **búfer** y vuelve a anunciarse. Al reconectar se repiten los pasos 3-7 y el nRF envía en ráfaga todo lo acumulado.

### 8.2 GAP: advertising y conexión

| Elemento | Valor | Dónde |
|---|---|---|
| Rol | Periférico, 1 conexión como máximo | `CONFIG_BT_PERIPHERAL`, `CONFIG_BT_MAX_CONN=1` |
| Nombre | `CorPost` | `CONFIG_BT_DEVICE_NAME` |
| Datos del anuncio | *Flags* (3 B) + UUID del servicio de 128 bits (18 B) + nombre (9 B) = 30 de 31 B | `ad[]` en [ble.c](src/ble.c) |
| Intervalo de advertising | 100-150 ms (`BT_LE_ADV_CONN_FAST_2`) | `adv_work_handler` |
| Parámetros preferidos de conexión | Intervalo 100-200 ms, latencia 4, *supervision timeout* 4 s | `CONFIG_BT_PERIPHERAL_PREF_*` en [prj.conf](prj.conf) |

- **Sobre los parámetros de conexión:** con latencia 4, el nRF puede saltarse hasta 4 citas seguidas si no tiene nada que enviar. El timeout debe ser mayor que `(1 + latencia) × intervalo × 2` = 5 × 200 ms × 2 = 2 s, y 4 s lo cumple.
- **El móvil decide:** Zephyr pide estos parámetros automáticamente 5 s después de conectar, pero el móvil puede no aceptarlos. Los valores reales aparecen en el RTT (`BLE: parametros actualizados ...`) y hay que anotarlos (sección 8.7).
- **Tras una desconexión** se vuelve a anunciar automáticamente, en el *callback* `recycled`, que se llama cuando la conexión anterior ya está liberada.

### 8.3 Seguridad implementada

| Medida | Cómo | Configuración |
|---|---|---|
| **Solo LE Secure Connections** | Se rechaza el *legacy pairing* | `CONFIG_BT_SMP_SC_ONLY=y` |
| **Autenticado (anti-MITM) con passkey** | El nRF tiene "pantalla" (el RTT) y ningún teclado, así que su capacidad de E/S es *DisplayOnly* y el método es Passkey Entry: el nRF genera un código aleatorio de 6 cifras y el usuario lo teclea en el móvil. **Se rechaza Just Works** | `auth_passkey_display` en [ble.c](src/ble.c) |
| **Nivel 4 en todo el servicio** | Las tres características (y el CCCD) tienen permisos `*_AUTHEN`. Sin emparejar no se puede leer, escribir ni suscribirse | `BT_GATT_PERM_*_AUTHEN` |
| **El nRF pide la seguridad nada más conectar** | El emparejamiento empieza sin esperar a que la app toque una característica | `bt_conn_set_security(conn, BT_SECURITY_L4)` en `connected` |
| **Doble comprobación antes de enviar** | Solo se notifica si el enlace tiene nivel ≥ 4. Así, un móvil emparejado que reconecta no recibe datos hasta que el cifrado se ha reactivado | `link_ready` |
| **Bonding persistente** | Las claves se guardan en la partición `storage` de la flash y sobreviven a reinicios y reflasheos | `CONFIG_BT_SETTINGS`, `CONFIG_NVS` |
| **Un solo móvil emparejado** | El D3 pide un enlace único con un solo edge. Un segundo móvil no puede emparejarse hasta borrar el bond actual con el **Botón 2** | `CONFIG_BT_MAX_PAIRED=1` |
| **Privacidad** | El nRF se anuncia con una dirección aleatoria que cambia cada 15 min. El móvil emparejado la reconoce gracias a la IRK | `CONFIG_BT_PRIVACY=y` |
| **Integridad** | Por radio, el MIC de AES-CCM. Además, el CRC-16 del paquete detecta errores entre el firmware y la app, por ejemplo al decodificar | Paquete de 24 B |

**Limitaciones y decisiones del PoC:**
- **El passkey se muestra por RTT.** En un producto real, sin pantalla, las opciones serían:
  - un **passkey fijo impreso** en el dispositivo (más débil: si alguien lo ve una vez, lo sabe para siempre);
  - **OOB por NFC** (el nRF52832 tiene NFC);
  - un **LED o vibración** que indique el código.
- **Cualquiera puede conectarse**, aunque no podrá emparejarse ni leer nada. Como solo se admite una conexión, un intruso conectado bloquearía al móvil legítimo (denegación de servicio). Una mejora sería, una vez emparejado, aceptar conexiones solo del móvil del bond (lista de filtrado del advertising).
- **No hay actualización de firmware firmada.** El D3 la menciona como trabajo futuro.

### 8.4 GATT: el servicio CorPost

UUID base, generado al azar: `bd5fXXXX-319b-420e-ae78-678d1c7cf46d`.

| Elemento | UUID | Propiedad | Permiso | Contenido |
|---|---|---|---|---|
| **Servicio CorPost** | `bd5f0001-319b-420e-ae78-678d1c7cf46d` | — | — | — |
| **Reading** | `bd5f0002-319b-420e-ae78-678d1c7cf46d` | Notify | CCCD: lectura/escritura autenticada | Paquete de 24 B (8.5) |
| **Command** | `bd5f0003-319b-420e-ae78-678d1c7cf46d` | Write | Escritura autenticada | Opcode (1 B) + parámetro (0-2 B) |
| **Time** | `bd5f0004-319b-420e-ae78-678d1c7cf46d` | Write | Escritura autenticada | uint32 LE, segundos UTC desde 1970 |

Cada característica tiene además un descriptor **CUD** con su nombre, para que nRF Connect lo muestre. Es público porque no contiene datos.

**Comandos** (característica Command; todos los valores en little-endian):

| Opcode | Comando | Parámetro | Ejemplo (bytes en hex) | Validación |
|---|---|---|---|---|
| `0x01` | Intervalo de medida | uint16, segundos | `01 1E 00` = 30 s; `01 B4 00` = 180 s | 5-3600 s |
| `0x02` | Tolerancia | uint8, grados | `02 0A` = 10° | 1-90° |
| `0x03` | Recalibrar (0°) | ninguno | `03` | — |
| `0x04` | Vibración | uint8: 0 = off, 1 = on | `04 00` = desactivar | 0 o 1 |

- **Si el comando no es válido**, la escritura falla con un error ATT y la app lo recibe como error del *write*:
  - opcode desconocido o valor fuera de rango: *Value Not Allowed*, 0x13;
  - longitud incorrecta: *Invalid Attribute Length*, 0x0D.
- **Cuándo se aplican:**
  - El intervalo afecta a la espera en curso.
  - La tolerancia se aplica desde la siguiente ventana.
  - Recalibrar interrumpe la espera y empieza en menos de 100 ms. Si llega durante una ventana de medida, empieza al terminar esa ventana.
- **Qué no hace la vibración off:** desactiva solo el aviso de mala postura. El pulso de confirmación de la calibración se mantiene.
- **Nada de esto se guarda en flash:** al reiniciar se vuelve a los valores de [config.h](src/config.h). La app debería reenviar la configuración al conectar.

**Time:** la app escribe la hora UTC del móvil (4 B, LE) en cada conexión. El nRF guarda la pareja (hora recibida, uptime en ese momento) y, a partir de ahí, calcula `hora = hora_recibida + (uptime_lectura − uptime_recepción)`. El uptime lo cuenta el RTC del chip, que sigue funcionando sin conexión.

### 8.5 El paquete de lectura (24 B)

| Offset | Campo | Tipo | Contenido en el firmware |
|---|---|---|---|
| 0-5 | Aceleración X, Y, Z | 3 × int16 | Media de la ventana, en **mg** (1 LSB = 1 mg, incluye la gravedad) |
| 6-11 | Velocidad angular X, Y, Z | 3 × int16 | Media de la ventana, en **1/16 °/s** (LSB del BNO055): dividir entre 16 |
| 12-15 | Ángulo | float32 IEEE-754 | Grados respecto a la calibración. **0 si el estado es INVALID** |
| 16 | Estado | uint8 | 0 = OK, 1 = BAD, 2 = INVALID (bits 2-7 a 0) |
| 17 | Batería | uint8 | **0xFF = no disponible** (el PoC va por USB). En el producto, 0-100 % |
| 18-21 | Timestamp | uint32 | Segundos UTC del final de la ventana |
| 22-23 | CRC | uint16 | **CRC-16/CCITT-FALSE** de los bytes 0-21 |

- **Todo es little-endian.**
- **El CRC** usa polinomio 0x1021, valor inicial 0xFFFF, sin reflexión y sin XOR final. Para comprobar una implementación: el CRC de la cadena ASCII `"123456789"` debe dar **0x29B1**. En el firmware es `crc16_itu_t(0xFFFF, ...)` de Zephyr.
- **El ejemplo del D3 (sección 5.4 del documento base)** pone `batt_pct: 100`. Con el PoC llegará 255, y la app debe tratarlo como "sin dato".

Decodificación en la app (JavaScript/TypeScript):

```js
function crc16ccittFalse(bytes) {          // bytes: Uint8Array
  let crc = 0xFFFF;
  for (const b of bytes) {
    crc ^= b << 8;
    for (let i = 0; i < 8; i++)
      crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) & 0xFFFF : (crc << 1) & 0xFFFF;
  }
  return crc;
}

function decodeReading(buf) {             // buf: ArrayBuffer de 24 B
  if (buf.byteLength !== 24) return null;
  const v = new DataView(buf);
  if (crc16ccittFalse(new Uint8Array(buf, 0, 22)) !== v.getUint16(22, true)) return null;
  const batt = v.getUint8(17);
  return {
    acc_mg:  [v.getInt16(0, true), v.getInt16(2, true), v.getInt16(4, true)],
    gyr_dps: [v.getInt16(6, true) / 16, v.getInt16(8, true) / 16, v.getInt16(10, true) / 16],
    angle_deg: v.getFloat32(12, true),
    status: ["OK", "BAD", "INVALID"][v.getUint8(16) & 0b11],
    batt_pct: batt <= 100 ? batt : null,
    ts: v.getUint32(18, true),
  };
}
```

### 8.6 El búfer circular

- **Siempre pasa por el búfer:** cada lectura se guarda primero en el búfer de 50 entradas (`ble_submit`) y después se intenta enviar (`ble_flush`). Si se envía, sale del búfer; si no, se queda.
- **Cuándo se envía:** solo con el enlace **listo**, es decir:
  - hay conexión;
  - la seguridad es de nivel 4;
  - la app está suscrita a Reading;
  - el MTU es ≥ 27;
  - **se ha recibido la hora**. Sin hora, el timestamp sería 0 y la app, que deduplica por `(device_id, timestamp)`, descartaría todas las lecturas menos una.
- **Ráfaga al reconectar:** mientras espera al siguiente intervalo, el bucle llama a `ble_flush` cada 100 ms. En cuanto el enlace queda listo, sale la ráfaga con todo lo pendiente. La pila solo tiene 3 buffers de envío, así que a mitad de la ráfaga `bt_gatt_notify` **espera** a que se libere uno: la ráfaga avanza al ritmo del enlace y el hilo principal queda ocupado mientras tanto. Si la conexión se cae a mitad, `bt_gatt_notify` devuelve error, la lectura se queda en el búfer y se reintenta en la siguiente conexión.
- **Búfer lleno:** se sobrescribe la lectura más antigua (D3) y el RTT lo indica. La app ve el hueco en los timestamps.
- **Se guarda el uptime, no la hora UTC:** así, las lecturas tomadas **antes** de que la app escriba la hora (por ejemplo, después de reiniciar el nRF sin móvil cerca) reciben su timestamp correcto cuando la hora llega.
- **El búfer está en RAM**, así que se pierde si el nRF se reinicia (documento base, sección 8).
- **Cobertura:** con 50 lecturas, la desconexión que se puede cubrir depende del intervalo. Con 15 s son 12,5 min; con 3 min, 2,5 h.

### 8.7 Guía de prueba con nRF Connect (móvil)

Se necesitan:
- la app **nRF Connect for Mobile** (Android o iOS);
- el DK conectado al PC con el visor RTT abierto, porque es donde sale el código de emparejamiento.

1. **Advertising.** En la pestaña *Scanner* aparece "CorPost". Anota el RSSI, el intervalo de advertising que muestra la app y el UUID del servicio.
2. **Conectar.** Pulsa *Connect*:
   - El RTT muestra `BLE: conectado a ...` y `CODIGO DE EMPAREJAMIENTO: xxxxxx`.
   - El móvil pide un código: teclea ese.
   - El RTT debe mostrar `seguridad nivel 4` y `emparejamiento completado, bond guardado`.
3. **MTU y parámetros.** El RTT muestra `MTU actualizado tx=… rx=…` y, a los 5 s, `parametros actualizados intervalo=… latencia=… timeout=…`. Anótalos.
4. **Servicio.** Abre el servicio desconocido `bd5f0001-…`. Deben verse Reading, Command y Time con sus nombres.
5. **Hora.** En Time, pulsa la flecha de escribir:
   - Elige *UINT32* (o *BYTE ARRAY* en little-endian).
   - Escribe la hora UTC actual en segundos. Se obtiene, por ejemplo, en epochconverter.com o con `python -c "import time;print(int(time.time()))"`.
   - El RTT muestra `BLE hora UTC = …`.
6. **Notificaciones.** En Reading, pulsa el botón de las tres flechas. Tras la siguiente medida llega un valor de 24 B y el RTT muestra `BLE: 1 lectura(s) enviada(s)`. Comprueba los bytes con la tabla de la sección 8.5 (o con `decodeReading`).
7. **Comandos.** En Command, escribe en hexadecimal:
   - `011E00`: intervalo de 30 s;
   - `020A`: tolerancia de 10°;
   - `03`: recalibrar;
   - `0400`: vibración desactivada.

   Cada uno debe aparecer en el RTT y notarse en el comportamiento. Prueba también uno inválido, como `09`: el móvil debe mostrar un error.
8. **Seguridad.**
   - Con otro móvil (o tras borrar el emparejamiento en el móvil), intenta suscribirte o escribir sin emparejar: debe fallar.
   - Con un bond ya guardado, un segundo móvil no puede emparejarse. El RTT muestra `emparejamiento fallido` y la pista del Botón 2.
9. **Desconexión y búfer.**
   - Desconecta (o aléjate o apaga el Bluetooth del móvil) durante varias medidas. El RTT muestra `enlace no listo, N lectura(s) en el bufer`.
   - Reconecta, escribe la hora y suscríbete: debe llegar la ráfaga con las N lecturas, con timestamps espaciados según el intervalo.
   - Comprueba también que **no pide el código otra vez** (bonding).
10. **Evidencias.** Haz capturas del móvil y guarda el log RTT: sirven para la entrega individual y para rellenar la sección 4 del documento base.

**Si se emparejó y luego se borró el emparejamiento solo en el móvil**, el nRF aún guarda el bond antiguo y rechazará al "nuevo" móvil. Pulsa el Botón 2 en el DK para borrarlo y vuelve a emparejar.
