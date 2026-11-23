# CorPost Mobile

Aplicación móvil de **CorPost**, desarrollada con React Native y Expo. Permite conectar con el dispositivo hardware mediante Bluetooth Low Energy (BLE) para recibir información relacionada con la monitorización postural.

El proyecto utiliza **Expo Application Services (EAS)** para generar las aplicaciones de Android e iOS en la nube. De esta forma, los desarrolladores no necesitan configurar Android Studio ni disponer de un ordenador Mac para participar en el desarrollo.

---

## 1. Tecnologías utilizadas

| Tecnología | Uso |
|---|---|
| React Native | Desarrollo de la aplicación móvil |
| Expo SDK 58 | Entorno de desarrollo |
| TypeScript | Tipado estático |
| Expo Router | Navegación entre pantallas |
| NativeWind 4 | Estilos mediante clases Tailwind CSS |
| react-native-ble-plx | Comunicación Bluetooth Low Energy |
| React Native Reanimated | Animaciones |
| EAS Build | Compilación en la nube |
| Expo Dev Client | Ejecución de la aplicación durante el desarrollo |

**Importante:** La aplicación no se puede ejecutar utilizando Expo Go, ya que utiliza `react-native-ble-plx`, una dependencia que requiere código nativo. Es necesario utilizar una Development Build.

---

## 2. Requisitos previos

Antes de comenzar, cada desarrollador debe tener instalado:

- [Node.js](https://nodejs.org/) (versión compatible con Expo SDK 58; actualmente se utiliza Node.js 22).
- npm, incluido con Node.js.
- Git.
- Un editor de código, preferiblemente Visual Studio Code.
- Un dispositivo Android o iOS físico para probar la aplicación.

No es necesario instalar Android Studio ni Xcode para trabajar con las compilaciones generadas mediante EAS.

### Herramientas recomendadas

- [Visual Studio Code](https://code.visualstudio.com/)
- [Git](https://git-scm.com/)
- [Node.js](https://nodejs.org/)
- [Expo](https://expo.dev/)

---

## 3. Obtener el proyecto

Clonar el repositorio:

```bash
git clone <https://github.com/aliciaaaaa15/IOT_CorPost.git>
```

Acceder a la carpeta del proyecto:

```bash
cd corpost-mobile
```

Instalar las dependencias:

```bash
npm install
```

Comprobar que las dependencias y la configuración de Expo son correctas:

```bash
npx expo-doctor
```

Si aparecen errores relacionados con las versiones de los paquetes, no actualizar dependencias individualmente sin comprobar primero su compatibilidad con Expo SDK 58.

---

## 4. Configuración de EAS

El proyecto utiliza Expo Application Services para realizar las compilaciones en la nube.

Cada desarrollador puede consultar las compilaciones y los proyectos desde:

https://expo.dev/

Para utilizar EAS CLI:

```bash
npm install -g eas-cli
```

Iniciar sesión con la cuenta de Expo:

```bash
eas login
```

Comprobar la sesión:

```bash
eas whoami
```

**Nota:** Es necesario que el proyecto esté asociado al proyecto de Expo correspondiente y que los desarrolladores tengan los permisos necesarios para acceder a él.

La configuración de compilación se encuentra en `eas.json`.

No es necesario ejecutar `eas build:configure` si el proyecto ya dispone de una configuración EAS válida.

---

## 5. Desarrollo de la aplicación

### 5.1. Obtener la Development Build

Para ejecutar la aplicación en un dispositivo físico, es necesario instalar una Development Build.

Las compilaciones se realizan en los servidores de Expo, por lo que no es necesario utilizar Android Studio ni Xcode.

Si ya existe una compilación compatible con el dispositivo, se puede utilizar la misma sin generar una nueva.

Si es necesario generar una nueva compilación:

**Android:**

```bash
eas build --profile development --platform android
```

**iOS:**

```bash
eas build --profile development --platform ios
```

Una vez finalizada la compilación, EAS proporciona un enlace para descargar e instalar la aplicación.

**Consideraciones para iOS:**

- La compilación se realiza en la nube, por lo que no es necesario disponer de un Mac.
- Para instalar una Development Build en un iPhone mediante distribución interna Ad Hoc, es necesario disponer de las credenciales de Apple Developer y registrar el UDID del dispositivo.
- Cuando se incorpora un nuevo iPhone, puede ser necesario registrar su UDID y generar una nueva compilación que lo incluya.

### 5.2. Iniciar el servidor de desarrollo

Una vez instalada la Development Build en el dispositivo, ejecutar:

```bash
npx expo start --dev-client
```

También se puede utilizar:

```bash
npm start
```

Se mostrará un código QR o una dirección para conectar el dispositivo al servidor Metro.

Abrir CorPost en el dispositivo y conectarlo al servidor de desarrollo.

**Importante:** El ordenador y el dispositivo deben poder comunicarse a través de la red. Si existen problemas de conexión, comprobar el firewall y la configuración de red.

Para limpiar la caché de Metro:

```bash
npx expo start --clear --dev-client
```

---

## 6. Desarrollo y cambios en el código

Durante el desarrollo habitual, los cambios realizados en archivos JavaScript, TypeScript y estilos se pueden visualizar mediante Fast Refresh, sin necesidad de generar una nueva compilación nativa.

Por ejemplo:

- Modificar una pantalla.
- Añadir un componente.
- Cambiar estilos de NativeWind.
- Modificar la lógica de navegación.
- Actualizar formularios.

### ¿Cuándo es necesario generar una nueva Development Build?

Es necesario generar una nueva compilación cuando se realizan cambios que afectan al código nativo, por ejemplo:

- Instalar o actualizar una dependencia nativa.
- Modificar configuraciones nativas de Expo.
- Cambiar permisos nativos.
- Modificar la configuración de BLE.
- Añadir plugins que requieran cambios en la aplicación nativa.

En estos casos, primero se debe comprobar la configuración y posteriormente generar una nueva Development Build mediante EAS.

---

## 7. Pruebas de Bluetooth Low Energy (BLE)

La comunicación con el hardware se realiza mediante Bluetooth Low Energy utilizando `react-native-ble-plx`.

Para probar esta funcionalidad:

1. Instalar la Development Build en un dispositivo físico.
2. Activar el Bluetooth del dispositivo móvil.
3. Encender el hardware CorPost.
4. Abrir la aplicación.
5. Conceder los permisos de Bluetooth solicitados.
6. Buscar el dispositivo CorPost desde la aplicación.
7. Establecer la conexión.
8. Comprobar la recepción de información mediante BLE.

**Importante:**

- No es suficiente con que el dispositivo hardware aparezca como emparejado en los ajustes de Bluetooth. La aplicación debe establecer su propia conexión GATT.
- Si se está utilizando nRF Connect para probar el hardware, desconectar previamente el dispositivo antes de intentar conectar desde CorPost.
- El firmware actual puede limitar las conexiones simultáneas, por lo que no se deben mantener dos conexiones GATT activas al mismo tiempo.


## 8. Estructura del proyecto

La organización del código sigue una separación entre pantallas, componentes y funcionalidades:

```text
corpost-mobile/
│
├── assets/
│
├── src/
│   ├── app/
│   │   ├── _layout.tsx
│   │   ├── index.tsx
│   │   ├── auth.tsx
│   │   └── dashboard.tsx
│   │
│   ├── screens/
│   │   ├── WelcomeScreen.tsx
│   │   ├── HomeScreen.tsx
│   │   └── AuthScreen.tsx
│   │
│   ├── components/
│   │   └── auth/
│   │       ├── LoginForm.tsx
│   │       └── RegisterForm.tsx
│   │
│   │
│   ├── constants/
│   └── types/
│
├── global.css
├── app.json
├── babel.config.js
├── metro.config.js
├── eas.json
├── package.json
└── README.md
```

La estructura puede ampliarse a medida que se incorporen nuevas funcionalidades.

---

## 9. Resolución de problemas habituales

### No se puede conectar al servidor Metro

**Posibles soluciones:**

```bash
npx expo start --clear --dev-client
```

Comprobar que el dispositivo y el ordenador están conectados a una red compatible y que el firewall permite la conexión.

### La aplicación no encuentra el dispositivo BLE

Comprobar:

- Que el Bluetooth está activado.
- Que se han concedido los permisos necesarios.
- Que el hardware está encendido y dentro del alcance.
- Que el dispositivo no está conectado previamente desde nRF Connect.
- Que el hardware está anunciando correctamente su servicio BLE.

### Se han añadido dependencias nativas

Si se instala una nueva dependencia que requiere código nativo, no basta con ejecutar `npm install`. Es necesario generar una nueva Development Build mediante EAS.

### Problemas con las dependencias

Ejecutar:

```bash
npx expo-doctor
```

Comprobar las versiones compatibles antes de modificar `package.json`.

---

## 10. Flujo de trabajo recomendado

Para mantener una colaboración organizada, se recomienda seguir este flujo:

1. Obtener la última versión de la rama de desarrollo.
2. Crear una rama propia para implementar una funcionalidad.
3. Realizar los cambios correspondientes.
4. Probar la aplicación utilizando la Development Build.
5. Comprobar que no existen errores de TypeScript.
6. Realizar las pruebas necesarias.
7. Crear un commit descriptivo.
8. Abrir una Pull Request hacia la rama de desarrollo.

Comprobar los tipos de TypeScript:

```bash
npm run typecheck
```

Ejemplo de nombres de ramas:

```text
feature/authentication
feature/ble-connection
feature/dashboard
fix/ble-permissions
```

Ejemplos de commits:

```text
feat: implement login and registration screens
feat: add BLE device discovery
fix: handle BLE connection errors
style: improve dashboard layout
```

---

## 11. Recursos útiles

- Expo Documentation: https://docs.expo.dev/
- EAS Build: https://docs.expo.dev/build/introduction/
- Expo Development Builds: https://docs.expo.dev/develop/development-builds/introduction/
- Expo Router: https://docs.expo.dev/router/introduction/
- NativeWind: https://www.nativewind.dev/
- react-native-ble-plx: https://github.com/dotintent/react-native-ble-plx

---

**CorPost Mobile**  
Mobile application for the CorPost IoT project.