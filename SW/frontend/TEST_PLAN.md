# Plan de prueba de integración

## Antes de abrir la app
- [ ] Firmware CorPost ejecutándose y anunciando `CorPost`.
- [ ] RTT abierto en el ordenador.
- [ ] Passkey visible en RTT para la primera vinculación.
- [ ] Bluetooth del teléfono activado.
- [ ] App instalada como development build (no Expo Go).

## Prueba 1 – Descubrimiento
- [ ] La app obtiene permiso Bluetooth.
- [ ] Encuentra el dispositivo por el UUID de servicio.
- [ ] Muestra nombre, identificador BLE y RSSI.

## Prueba 2 – Conexión y seguridad
- [ ] Conecta.
- [ ] El sistema operativo solicita pairing si es la primera vez.
- [ ] Introducir el passkey de RTT.
- [ ] RTT indica nivel de seguridad 4 y bonding completado.
- [ ] La app descubre el servicio y las tres características.

## Prueba 3 – Hora
- [ ] La app escribe 4 bytes en Time.
- [ ] RTT muestra `BLE hora UTC = ...`.
- [ ] Verificar que el valor corresponde al epoch actual en segundos.

## Prueba 4 – Notificaciones
- [ ] La app activa la suscripción de Reading.
- [ ] Esperar al siguiente ciclo de medición.
- [ ] La app recibe 24 bytes.
- [ ] CRC correcto.
- [ ] Valores de acelerómetro, giroscopio, ángulo, estado y timestamp razonables.

## Prueba 5 – Comandos
- [ ] Enviar `03` y verificar la recalibración (dos pulsos).
- [ ] Enviar `011E00` y verificar intervalo 30 s en RTT.
- [ ] Enviar `020A` y verificar tolerancia 10° en RTT.
- [ ] Enviar `0400` y `0401` y comprobar la vibración.

## Prueba 6 – Reconexión
- [ ] Desconectar desde la app.
- [ ] Volver a escanear y conectar.
- [ ] Comprobar que el bond evita introducir otra vez el passkey.
- [ ] Comprobar recepción de lecturas almacenadas en el buffer.

## Evidencias a guardar
- Captura de la app conectada.
- Captura de una lectura recibida y CRC válido.
- RTT mostrando la hora y comandos recibidos.
- RTT mostrando `seguridad nivel 4` y `bond guardado`.
