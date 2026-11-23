# Doc 6 — Setup del entorno de desarrollo

Objetivo: poder armar la máquina **desde cero, de forma repetible**. Se basa en lo que
ya funciona en `almacenero` (ver su Doc 3 para los problemas conocidos, sobre todo
descargas que se cortan). El stack es el mismo, así que el entorno de una sirve para
la otra.

Máquinas (D41):

| Máquina | Uso | Sistema |
|---------|-----|---------|
| Mac actual | Desarrollo | macOS, Apple Silicon |
| Mac nueva (más potente) | **Desarrollo principal** desde la próxima sesión | macOS, Apple Silicon |
| Windows (Intel i9) | Pruebas ocasionales | Windows, x86_64. **No puede compilar iOS** (requiere macOS y Xcode) |

Las dos Mac siguen la guía de macOS; Windows tiene la suya más abajo.

## Versiones de referencia (máquina actual, 2026-11-18)

| Herramienta | Versión | Notas |
|-------------|---------|-------|
| Flutter | 3.50.0 stable (Dart 3.14.0) | Fijar la misma versión en ambas máquinas |
| Supabase CLI | 3.1.0 | Es la que fija el CI; hay una 3.2.0 más nueva, no actualizar sin probar |
| Docker | 24.0.6 | Docker Desktop |
| Python | 3.12 (el CI); el proyecto pide >= 3.10 | |
| PostgreSQL cliente (`psql`) | 17 | Lo usan los targets de seed |
| JDK | 17 (`openjdk@17`) | Para Gradle y `sdkmanager`. Java 8 de sdkman no sirve |
| Android SDK | platforms 35 y 36, build-tools 35.0.0 y 28.0.3, NDK 28.2.13676358 | Los pide el Flutter usado |

## Qué instalo yo y qué hacés vos

| Paso | Quién | Por qué |
|------|-------|---------|
| Instalar Homebrew | **Vos** (pide contraseña de administrador) | `https://brew.sh` |
| Instalar **Docker Desktop** | **Vos** (instalador gráfico con permisos y licencia) | Lo necesita el stack local de Supabase |
| `gh auth login` | **Vos** (autenticación en el navegador) | Credenciales de GitHub |
| Aceptar licencias del SDK de Android | Yo, con `yes | sdkmanager --licenses` | Es tu aceptación; te aviso antes |
| Resto (Flutter, Java, SDK, Supabase CLI, psql, Python, emulador) | Yo | Por línea de comandos |

Antes de la sesión de setup, lo único que **conviene tener hecho** es Homebrew y
Docker Desktop abierto y funcionando. Xcode no hace falta (iOS está fuera de alcance);
`flutter doctor` lo va a marcar en rojo y es esperable.

## Preparar iOS (para compilar y probar sin pagar)

Objetivo (D29): que el día que se pague el Apple Developer Program solo haya que
firmar y recompilar. Sin pagar se puede **compilar y correr en el simulador** y, con un
Apple ID gratuito, instalar en un iPhone propio (con vencimiento corto). No hay push
real, TestFlight ni App Store.

| Paso | Quién |
|------|-------|
| Instalar **Xcode** (App Store, varios GB; requiere iniciar sesión con tu Apple ID) | **Vos** |
| `sudo xcode-select -s /Applications/Xcode.app` y `sudo xcodebuild -license accept` | Vos (pide contraseña) |
| `xcodebuild -runFirstLaunch` y `xcodebuild -downloadPlatform iOS` (runtime del simulador) | Yo |
| `brew install cocoapods` | Yo |
| `flutter doctor` debe mostrar iOS en verde | Yo |
| Generar la carpeta `ios/` de cada app y compilar con `flutter build ios --simulator` | Yo, al crear los proyectos |

Decidir **antes de crear los proyectos** los identificadores definitivos de cada app
(`applicationId` en Android y *bundle id* en iOS: `dev.crulises.guazu.cliente` y
`dev.crulises.guazu.negocio`, D50): cambiarlos después duele, y Firebase y Apple los usan.

Esta máquina hoy tiene solo las herramientas de línea de comandos, sin Xcode, CocoaPods
ni Node.

## Para push: Firebase

Cuando llegue el momento: `npm i -g firebase-tools` y
`dart pub global activate flutterfire_cli` (hace falta Node). Detalle de cuentas en
`costos.md`.

## Guion de «computadora nueva» (para Claude)

Si el usuario dice algo como *«Esta es una computadora nueva, tiene macOS y quisiera arrancar
con el setup»* (o Windows), Claude **no instala a ciegas**: guía en este orden y espera la
confirmación de cada paso del usuario antes de seguir.

1. **Diagnóstico**: `uname -m`, `sw_vers`, qué hay ya instalado (`brew`, `git`, `docker`,
   `flutter`, `java`, `gh`, `psql`, `xcodebuild`). Decir qué falta.
2. **Pasos que solo hace el usuario** (con el comando exacto y por qué): Homebrew, Docker
   Desktop (con ≥ 8 GB de memoria), Xcode y su licencia (`sudo xcodebuild -license`,
   `xcodebuild -runFirstLaunch`), `gh auth login`, `supabase login`, `fly auth login`.
3. **Pasos que hace Claude** una vez listo lo anterior: `git config` (noreply de GitHub),
   clonar `guazu` y, como referencia, `almacenero`; `brew install` de lo que falte (sección
   siguiente); variables de entorno; SDK, NDK y AVD `guazu_pixel`; `flutter config`.
4. **`.env`** desde `.env.example` (el usuario trae los secretos, nunca están en el repo).
5. **Verificar**: `make doctor && make up && make test` (cuando existan). Mientras no haya
   Makefile, la lista de verificación de abajo.
6. **Anotar** en `03-problemas-soluciones.md` todo lo que falle, con fecha, y ajustar este doc.

Claude pide permiso para cada descarga grande y avisa que la máquina no debe hibernar.

## Pasos (macOS Apple Silicon)

```bash
# 1. Herramientas base
brew install gh openjdk@17 supabase/tap/supabase libpq python@3.12
brew install --cask android-commandlinetools flutter
# Flutter: si se prefiere la versión exacta, instalar desde git en el tag 3.50.0
# (ver "Versionado de Flutter" abajo)

# 2. Variables y PATH: van en ~/.zshenv (NO en ~/.zshrc: ese solo lo lee un shell interactivo y
#    las herramientas, los scripts y make no lo ven). Ejemplo completo en docs/03 ("PATH en shells no interactivos").
export JAVA_HOME=/opt/homebrew/opt/openjdk@17
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:/opt/homebrew/opt/libpq/bin:$PATH"

# 3. SDK de Android (aceptar licencias)
yes | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "platforms;android-35" "platforms;android-36" \
  "build-tools;35.0.0" "build-tools;28.0.3" "ndk;28.2.13676358" \
  "system-images;android-35;google_apis;arm64-v8a"

# 4. Flutter apuntando a ese SDK y a ese JDK
flutter config --jdk-dir "$JAVA_HOME" --android-sdk "$ANDROID_HOME"
flutter doctor

# 5. Emulador
echo no | avdmanager create avd -n guazu_pixel -d pixel_8 \
  -k "system-images;android-35;google_apis;arm64-v8a"

# 6. Proyecto
gh auth login && gh repo clone <usuario>/guazu && cd guazu
make doctor && make up && make test
```

### Versionado de Flutter
`brew install --cask flutter` instala la última estable, que puede no ser la 3.50.0.
Para fijar la versión, clonar el repositorio de Flutter en el tag exacto y
agregarlo al `PATH`, o usar un gestor de versiones (por ejemplo FVM). Se decide al
armar el proyecto, y la versión queda anotada en el `pubspec.yaml` y acá.

### Descargas que se cortan
Las descargas grandes (imagen del emulador ~1,5 GB, NDK, Gradle) fallan por timeout si
la red es inestable o la Mac hiberna. Reintentar en bucle y evitar la hibernación:
```bash
for i in 1 2 3 4 5 6; do sdkmanager --install "<paquete>" && break; done
```
Detalle en el Doc 3 de almacenero.

## Lo que hay que automatizar en el repo (pendiente de código)

Cuando haya Makefile:

- `make setup`: instala lo que falte con Homebrew y el SDK de Android (idempotente).
- `make doctor`: **verifica** versiones y herramientas y dice qué falta. Es lo primero
  que se corre en una máquina nueva.
- `make up` / `make down` / `make migrate` / `make seed` / `make test` / `make lint` /
  `make build` — igual que almacenero.
- `make apk-cliente` y `make apk-negocio` — un APK por app; `make apk` arma los dos.
  Cada uno usa `--dart-define=API_URL=...` y su propio `applicationId`.
- `make admin` pasa a ser un target de **dueño** (asigna rol de dueño por SQL),
  adaptado al modelo de permisos del Doc 2.
- CI: GitHub Actions que solo llama a targets del Makefile.

## Lo que aprendimos de almacenero para armar la máquina

Detalle en `03-problemas-soluciones.md`. Lo esencial, antes de empezar:

- **Actualizar Flutter primero** y recién después crear los proyectos (si no, `android/` sale
  viejo y no compila).
- `brew install gh openjdk@17 supabase/tap/supabase libpq python@3.12 flyctl`; `libpq` no queda
  en el PATH solo: `brew link --force libpq` (o agregarlo) para tener `psql` y `pg_dump`
  (el `pg_dump` debe ser de versión igual o mayor que el servidor).
- **Docker Desktop con al menos 8 GB** (Preferencias > Resources); con 16 GB de RAM sobra
  para emulador + Supabase + Gradle. Si se siente lento, `supabase start -x` para los servicios
  que no se usan.
- **Evitar que la Mac hiberne** durante descargas grandes (SDK, NDK, imagen del emulador) y
  reintentar en bucle si se cortan.
- Instalar el NDK (`ndk;28.2.13676358`) antes del primer build: Gradle se cuelga bajándolo.
- `supabase login` y `fly auth login` los hacés vos (abren el navegador).
- **Dos proyectos en la misma Mac**: guazu usa otros puertos y `name: guazu` en el compose
  (Doc 3 §Docker). No levantar ambos con la misma configuración.
- Configurar `git config user.name` y `user.email` (noreply de GitHub) **antes del primer
  commit** en cada máquina.
- **Compose fija `name:`** y un worktree nuevo necesita copiar `.env` y correr `make venv`.

### Lista de verificación de una máquina nueva

`make doctor` debe mostrar OK para: Flutter y Dart, JDK 17, Android SDK y NDK, emulador
`guazu_pixel`, Docker corriendo, Supabase CLI, `psql`, Python 3.12, `gh` logueado, `fly` y
(en Mac) Xcode y CocoaPods. Luego `make up && make test`.

### Lo que NO viaja con el repo

`.env`, `.venv`, keystore y `key.properties`, `backups/`, credenciales (`gh`, `supabase`,
`fly`), los volcados de OFF y SEPA (se vuelven a bajar) y las sesiones de Claude.

## Qué hay que copiar a mano a la otra máquina

- El repositorio `guazu` y, como referencia, `almacenero` (se clonan de GitHub).
- El archivo `.env` (nunca está en el repo; se regenera con `.env.example`).
- Credenciales: `gh auth login` y la clave de firma del APK cuando exista.
- Las transcripciones de las sesiones no se mudan: el contexto vive en `CLAUDE.md` y
  `docs/`.

## Windows (Intel i9): pruebas ocasionales

**Sin verificar en esta máquina**: es una guía de partida que se completa y corrige en la
primera instalación real (y lo aprendido va a `03-problemas-soluciones.md`).

Qué se puede hacer en Windows: correr el backend y la base, compilar y probar las apps en
**Android** (emulador o celular), y compilar la app **Negocio de escritorio** para
Windows. Qué no: nada de iOS.

Esquema recomendado:

- **WSL2 con Ubuntu** para el backend, `make`, la CLI de Supabase y Docker (Docker Desktop
  con el motor WSL2). Los targets del Makefile son de bash, así que corren ahí. **Clonar el
  repo dentro del sistema de archivos de WSL** (no en `C:\`): es mucho más rápido.
- **Flutter instalado en Windows** (no en WSL) para el emulador y para la app de
  escritorio, con Android Studio o las herramientas de línea de comandos.
  - El emulador debe usar la imagen **`x86_64`** (no la `arm64-v8a` de la Mac) con la
    aceleración de Windows (Windows Hypervisor Platform) activada.
  - Para compilar la app de escritorio hace falta **Visual Studio 2022** con la carga
    "Desktop development with C++".
- Si se quiere correr `make lint`, `make test` o `make apk` en WSL, instalar también una
  copia de Flutter **dentro de WSL** (compila, pero no tiene emulador; se instala en un
  celular por `adb` por Wi-Fi).
- JDK 17, el mismo SDK de Android y las mismas versiones de herramientas que en la tabla de
  arriba.
- Git: el repo trae `.gitattributes` con finales de línea `LF` para que los scripts de
  bash no se rompan.

Herramientas (instalables con `winget`, a confirmar nombres de paquete en el momento):
Git, GitHub CLI, Docker Desktop, JDK 17, Android Studio, Visual Studio 2022, y WSL
(`wsl --install`).
