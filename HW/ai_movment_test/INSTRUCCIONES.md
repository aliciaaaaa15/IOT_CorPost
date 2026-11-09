

## 1. App y configuración

**App: Sensor Logger** (Kelvin Choi). Es gratis, existe para iOS y Android, registra acelerómetro y giroscopio a la vez y exporta en "Zipped CSV", que es el formato gratuito. No uses "Combined CSV", que es de pago.

| Ajuste | Valor |
|---|---|
| Sensores activos | Solo **acelerómetro** y **giroscopio**. Desactiva GPS, cámara, micrófono, etc. |
| Frecuencia | **50 Hz** para ambos (o la más alta que permita, si es menor). Luego el código reduce a 10 Hz. |
| Aceleración | La que **incluye gravedad**. Es lo que permite calcular el ángulo. El conversor avisa si en reposo no mide ~1 g. |
| Pantalla | Siempre encendida y app en primer plano. |
| Interrupciones | Modo avión y "no molestar", **sin vibración**. Una vibración por notificación contamina los datos. |
| Batería | Desactiva el ahorro de batería. |
| Móvil | Usa **el mismo móvil** para todo. Los ejes de iOS y Android difieren y los sensores también. |

## 2. Dónde y cómo colocar el móvil

Pregunta primero dónde irá el clip y replícalo. Si aún no está decidido, usa esta posición:

- **Zona**: centro del pecho, justo bajo las clavículas (5-10 cm bajo el cuello).
- **Orientación**: vertical, parte superior hacia arriba y pantalla hacia fuera. Que sea siempre idéntica.
- **Sujeción**: un arnés o banda elástica de pecho para móvil, o un bolsillo muy ajustado. **Nada que cuelgue**, como un cordón.
- **Prueba de sujeción**: camina y salta suavemente. Si el móvil rebota respecto al cuerpo, está mal sujeto y generará un movimiento que el clip real no tendrá.

**Variedad**, que es lo que hace que el modelo generalice:
- Al menos 2 sesiones en días distintos, con ropa distinta (camiseta fina, sudadera).
- Quita y vuelve a poner el móvil entre sesiones.
- Usa al menos 2 sillas distintas, por ejemplo una de oficina con ruedas y una fija.
- Mínimo 3 personas, mejor 4-5, con alturas y complexiones distintas. Pide permiso a quien participe.

## 3. Procedimiento de cada grabación

1. Pon el móvil, abre la app y pulsa **Start**.
2. Durante **5 s** colócate y quédate quieta en la postura inicial. El código recorta esos segundos.
3. Haz la actividad **120 s** (mínimo 90 s). Usa un reloj o temporizador **aparte**, no el móvil.
4. En los **5 s** finales quítate el móvil con calma y pulsa **Stop**.
5. Renombra la grabación y exporta.

Si tienes a alguien que pulse Start/Stop y lleve el cronómetro, mejor.

**Por qué 120 s:** con ventanas de 2 s y 50 % de solape salen unas 110 ventanas por grabación. Es mejor muchas grabaciones de 2 min que pocas de 10, porque así hay más variedad de posturas y recolocaciones.

## 4. Reglas de etiquetado (decidirlas ya)

Imprime esto y no lo cambies después:

- **Válida**: tronco y hombros quietos. Solo se mueven manos, antebrazos, cabeza, respiración, voz.
- **No válida**: se mueve el tronco, los hombros o el cuerpo entero.
- **Cambiar de postura** (de recta a encorvada, recolocarte) es no válida mientras lo haces. Una vez quieta en la nueva postura, es válida.
- **Una postura mantenida quieta** es siempre válida, aunque sea "mala": inclinada, encorvada, de lado.
- **Una sola actividad por grabación.** No cambies de postura en las válidas.
- **Sin pausas largas** en las no válidas: si te paras más de 1 s, esas ventanas quedan mal etiquetadas. Haz los ciclos de forma continua.

## 5. Qué grabar y cómo

Las marcadas con ★ son el **núcleo** (19 grabaciones, unos 40 min por persona). Con todo son 30 grabaciones, algo más de una hora por persona.

### Válidas (nombre empieza por `sentado` o `depie`)

| Nombre | Grab. | Cómo hacerlo |
|---|---|---|
| ★ `sentado_recto` | 2 | Espalda recta apoyada en el respaldo, pies en el suelo. Mira la pantalla, teclea y usa el ratón con normalidad. |
| ★ `sentado_encorvado` | 2 | Hombros caídos, cabeza adelantada, espalda redondeada. Es la postura "mala" típica. |
| ★ `sentado_adelante` | 1 | Tronco inclinado ~20-30° hacia delante, codos en la mesa. |
| `sentado_reclinado` | 1 | Reclinada hacia atrás en el respaldo, ~20°. |
| `sentado_ladoizq` / `sentado_ladoder` | 1+1 | Tronco inclinado ~10-15° a un lado, apoyada en el reposabrazos. |
| ★ `sentado_teclear` | 2 | Trabajo normal: teclear, ratón, mirar la pantalla, con micro-movimientos naturales y sin cambiar de postura. |
| `sentado_movil` | 1 | Mirando el móvil o leyendo en papel, cabeza baja. |
| `sentado_hablar` | 1 | Hablar, beber de un vaso, rascarte la cara, toser, reír. Tronco quieto. |
| ★ `depie_quieto` | 1 | De pie parada, peso repartido. |

### No válidas (el primer token es la clase)

| Nombre | Grab. | Cómo hacerlo |
|---|---|---|
| ★ `andar_normal` | 1 | Andar a ritmo normal por la sala o el pasillo, con giros. |
| ★ `andar_lento` | 1 | Paseo muy lento, paso corto. Es un caso difícil. |
| ★ `levantarse_normal` | 1 | Ciclo continuo: sentada, levantarte, quedarte de pie, sentarte. Unos 5-6 s por ciclo. |
| ★ `levantarse_lento` | 1 | Lo mismo muy despacio, unos 8-10 s por ciclo. Es el caso límite del que hablaba tu documento. |
| ★ `estirar_delante` | 1 | Sentada, alcanzar un objeto 40-60 cm más allá de lo cómodo, volver, alternar manos. Unos 4 s por repetición. |
| `estirar_lado` | 1 | Alcanzar algo a tu lado, a la altura del hombro. |
| `estirar_arriba` | 1 | Desperezarte con los brazos arriba, bostezar. |
| ★ `girar_tronco` | 1 | Sentada, girar el torso 90° a izquierda y derecha, como mirar a quien está detrás. |
| `girar_silla` | 1 | Girar con la silla giratoria a un lado y otro. |
| ★ `agacharse_sentado` | 1 | Sentada, inclinarte hacia el suelo a recoger algo y volver, en ciclos de ~5 s. |
| `agacharse_depie` | 1 | De pie, agacharte a recoger algo. |
| ★ `gesticular` | 1 | Sentada, explicar algo en voz alta con gestos amplios de brazos. |
| ★ `inclinarse_normal` | 1 | Pasar de recta a encorvada y volver en ciclos de ~3 s, sin parar. |
| ★ `inclinarse_lento` | 1 | Igual pero muy despacio, unos 6 s por ciclo. Es otro caso difícil. |
| ★ `moverse_silla` | 1 | Recolocarte en la silla, desplazarte hacia delante o atrás, apoyarte. |
| `moverse_piernas` | 1 | Cruzar y descruzar piernas, apoyar un pie en la silla. |
| `moverse_chaqueta` | 1 | Ponerte y quitarte una chaqueta una y otra vez. |

**Cuántas más grabaciones:** en tu documento proponías 15-20 min por clase y persona. Esta versión es una versión reducida. Si los resultados con el núcleo son prometedores, amplía sobre todo los casos difíciles (`levantarse_lento`, `inclinarse_lento`, `andar_lento`, `moverse_*`).

## 6. Nombrado y preparación de los datos

**Formato del nombre:** `clase_detalle_persona_nn`, todo en minúsculas, sin acentos ni espacios, y sin guiones bajos dentro de cada parte.

Ejemplos: `sentado_recto_ana_01.zip`, `levantarse_lento_luis_02.zip`. La **persona** es el penúltimo bloque y es la que usa el código para dejar a alguien fuera en la validación.

Pasos:

1. Exporta cada grabación como **Zipped CSV** y pásala al ordenador.
2. Renombra cada zip como arriba. El nombre pasa a ser la etiqueta.
3. Convierte y revisa los avisos:
   ```bash
   python convert_sensorlogger.py --src ./exportaciones --out ./mis_grabaciones
   ```
   Cada línea indica `OK` o `REVISAR`, con la duración, la frecuencia real (debería rondar los 50 Hz), si la aceleración es m/s² o g, si la magnitud en reposo es ~1 g y si hay giroscopio.
4. Entrena y evalúa:
   ```bash
   python run_own.py --data ./mis_grabaciones --out ./out_own --orientation-free
   ```

**No hay que hacer nada más a los datos.** No quites la gravedad, no los filtres, no los recortes a mano (ya recorta 5 s por extremo) y no los normalices. Guarda los zips originales como copia.

