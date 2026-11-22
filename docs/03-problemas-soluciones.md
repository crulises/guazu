# Doc 3 — Problemas, soluciones y decisiones

Registro de lo que falla mientras se arma el proyecto, cómo se resuelve y por qué se
toman ciertas decisiones. Sirve para **recrear el entorno en otra máquina sin tropezar
con lo mismo**. No es fuente de verdad del producto (Doc 1) ni de la arquitectura
(Doc 2): si algo acá los contradice, ganan ellos.

Formato: **Síntoma → Causa → Solución**. Cuando aparezca algo nuevo, se agrega a la
sección que corresponda con su fecha. Es mejora continua: **cada corte cierra con lo que
aprendió**.

## Cómo leer este documento

Hasta que `guazu` tenga código, casi todo lo de abajo viene de **`almacenero`**
(`/Users/urc/Documents/Projects/almacenero`, su `docs/03-problemas-soluciones.md`, a
2026-11-21). Está marcado:

- **[heredado]**: ya pasó en almacenero con el mismo stack; es probable que vuelva a pasar
  acá. Si pasa, se confirma y se quita la marca, con la fecha.
- **[guazu]**: pasó acá, con fecha.

Lista de lo que se copia de almacenero (código, Makefile, docs): `09-heredado-de-almacenero.md`.

- [Armar el entorno](#armar-el-entorno)
- [Android y Flutter](#android-y-flutter)
- [Proyecto Flutter](#proyecto-flutter)
- [Backend, auth y Supabase](#backend-auth-y-supabase)
- [Docker y varios proyectos en la misma máquina](#docker-y-varios-proyectos-en-la-misma-máquina)
- [Tests](#tests)
- [CI](#ci)
- [Git y GitHub](#git-y-github)
- [Probar en emulador y en celular](#probar-en-emulador-y-en-celular)
- [Escáner de códigos](#escáner-de-códigos)
- [ETL y catálogo](#etl-y-catálogo)
- [Normalizador de catálogo](#normalizador-de-catálogo)
- [Despliegue: Fly.io, Supabase y dominio](#despliegue-flyio-supabase-y-dominio)
- [Backup y ensayo de salida](#backup-y-ensayo-de-salida)
- [Abuso y límites de uso](#abuso-y-límites-de-uso)
- [Específicos de guazu](#específicos-de-guazu)
- [Decisiones de diseño heredadas](#decisiones-de-diseño-heredadas)

El paso a paso para armar la máquina está en `06-setup-entorno.md`.

---

## Armar el entorno

### Flutter muy viejo **[heredado]**
- **Síntoma:** `flutter doctor` mostraba 3.3.7 y paquetes como `mobile_scanner` exigen uno
  bastante más nuevo. `flutter upgrade` se negó con *"Your flutter checkout has local
  changes"*.
- **Causa:** el único cambio era `tool_state`, un archivo de estado de la herramienta.
- **Solución:** `flutter upgrade --force` es seguro en ese caso; antes mirar `git status`
  dentro de la carpeta de Flutter.
- **Moraleja:** **actualizar Flutter antes de crear los proyectos**, no después (ver
  «`android/` generado por un Flutter viejo»).

### No hay Android SDK ni emulador **[heredado]**
- **Síntoma:** `Unable to locate Android SDK`.
- **Solución:** sin Android Studio, por línea de comandos: `brew install --cask
  android-commandlinetools` deja el SDK en `/opt/homebrew/share/android-commandlinetools`;
  `flutter config --android-sdk` apunta ahí.

### `sdkmanager` pide Java 17 **[heredado]**
- **Síntoma:** el Java activo era el 8 (instalado con sdkman) y `sdkmanager` se negaba.
- **Solución:** `brew install openjdk@17` y usarlo por `JAVA_HOME` solo para estos
  comandos; para Gradle, `flutter config --jdk-dir /opt/homebrew/opt/openjdk@17`.
- **Nota:** esta máquina (la Mac actual) todavía tiene Java 8 como predeterminado.

### Flutter exige componentes que no se instalaron **[heredado]**
- **Síntoma:** *"Flutter requires Android SDK 36 and the Android BuildTools 28.0.3"*.
- **Solución:** además del SDK 35 de la imagen, `platforms;android-36` y `build-tools;28.0.3`.
  Instalar lo que pida el `flutter doctor` de turno.

### Las descargas grandes se cortan **[heredado]**
- **Síntoma:** `sdkmanager` o Gradle fallan con *"Operation timed out"* (imagen del
  emulador ~1,5 GB, distribución de Gradle, NDK). Una vez la Mac hibernó y el proceso
  quedó colgado sin avanzar.
- **Solución:** reintentar en bucle y **evitar que la Mac hiberne**:
  ```bash
  for i in 1 2 3 4 5 6; do sdkmanager --install "<paquete>" && break; done
  ```
  Si la carpeta no crece, matar el proceso y relanzarlo.

### Gradle se cuelga bajando el NDK **[heredado]**
- **Síntoma:** el build se queda en *"Downloading android-ndk-r28c…"*.
- **Solución:** instalarlo antes con `sdkmanager "ndk;28.2.13676358"` y recién después
  compilar. El primer build de una app lleva varios minutos por esto.

### `avdmanager` imprime un error pero el emulador se crea **[heredado]**
- **Síntoma:** `Could not load devices from …/devices.xml`.
- **Causa:** aviso inofensivo. **Solución:** ignorarlo y confirmar con `avdmanager list avd`.

### Con la máquina cargada, todo anda lento **[heredado]**
- **Síntoma:** emulador + Docker + Gradle a la vez; `adb` tarda y `adb shell input text`
  pierde caracteres.
- **Solución:** `./gradlew --stop` para liberar daemons; para teclear números mandar una
  tecla por dígito (`input keyevent KEYCODE_7`).

### Xcode, CocoaPods e iOS **[guazu]**
- Hoy la Mac actual tiene solo las herramientas de línea de comandos (sin Xcode, CocoaPods
  ni Node). El plan de preparación de iOS está en `06-setup-entorno.md`. Lo que se aprenda
  al instalarlo se anota acá.

---

## Android y Flutter

*(Ver también «Armar el entorno».)*

### `android/` generado por un Flutter viejo no compila **[heredado]**
- **Síntoma:** *"You are applying Flutter's app_plugin_loader Gradle plugin imperatively …
  not possible anymore"*.
- **Causa:** el proyecto se creó con Flutter 3.3.7 y después se actualizó Flutter.
- **Solución:** borrar y regenerar `android/` (`flutter create --platforms=android --org
  <org> --project-name <nombre> .`), y reaplicar lo propio (`INTERNET`, cleartext de debug).

### `pubspec.yaml` con Dart 2 **[heredado]**
- **Síntoma:** `sdk: '>=2.18.4 <3.0.0'` no resuelve con Dart 3.14.
- **Solución:** `sdk: ^3.14.0` y subir `cupertino_icons` y `flutter_lints`. Con un proyecto
  nuevo no pasa.

### `package:flutter/material.dart` está deprecado **[heredado]**
- **Síntoma:** `flutter analyze` marca `deprecated_member_use`; `make lint` falla.
- **Solución:** `flutter pub add material_ui` y usar `package:material_ui/material_ui.dart`.
  **No mezclar** ambos imports en un mismo test: los widget tests fallaron hasta unificarlos.

### Parámetros nombrados privados **[heredado]**
- Dart 3.12+ permite `required this._api` (el nombre público queda `api:`); es lo que
  sugiere el lint `prefer_initializing_formals`.

### `setState(() => _x = unFuture())` **[heredado]**
- **Síntoma:** *"setState() callback argument returned a Future"*. Un widget test lo atajó.
- **Solución:** cuerpo con llaves: `setState(() { _x = unFuture(); });`.

### Decimales en JSON **[heredado, aplica distinto acá]**
- En almacenero el backend serializaba `Decimal` como string y el precio viajaba como
  string. **Acá el dinero va en centavos enteros** (Doc 2 §Dinero), así que no aplica; sí
  sigue valiendo no usar `double` para plata.

### Mapa de la app y `flutter_map` **[heredado, condicional]**
- Solo si se agrega un mapa (p. ej. para dibujar el polígono de una sucursal): `Path` es de
  `flutter_map`, para dibujar con `Canvas` usar `ui.Path`; un mapa dentro de un `ListView`
  se pelea con el scroll; en tests, buscar carteles por `ValueKey` y agrandar la pantalla.
- Las **teselas públicas de OpenStreetMap no son para uso masivo**; sirven para el grupo
  cerrado. Antes de abrir la app hay que decidir proveedor (ver `revisar/`).

---

## Backend, auth y Supabase

### «Token inválido» con un token real del auth local **[heredado]**
- **Síntoma:** el token de `/auth/v1/signup` siempre daba 401 en el backend.
- **Causa:** el Supabase CLI 3.x firma los JWT con **ES256** (clave asimétrica, JWKS) y el
  backend solo validaba HS256. Los tests no lo detectaron porque firmaban sus propios tokens.
- **Diagnóstico:** decodificar el header del token (`{"alg":"ES256","kid":…}`).
- **Solución:** mirar el `alg`: ES256/RS256 contra `JWKS_URL` (con caché), HS256 con
  `JWT_SECRET`. Requiere `PyJWT[crypto]`.
- **Lección:** al menos un test de auth debe usar un token del proveedor real.

### El cliente no pide la sesión anónima directo al auth **[heredado]**
- **Decisión:** la regla es que Flutter habla solo con el backend; la sesión anónima
  necesita GoTrue, así que el backend la **proxea** (`POST /v1/auth/anonymous` y
  `/v1/auth/refresh`). Requiere `AUTH_URL` y `AUTH_API_KEY` (la `ANON_KEY`).

### `AUTH_API_KEY` queda vacía en `.env` **[heredado]**
- **Síntoma:** `/v1/auth/anonymous` → 503 *"auth no configurada"*.
- **Causa:** `supabase status -o env` dentro de `make` imprimió JSON y el `sed` no halló
  `ANON_KEY`; además un `.env` viejo no tenía la línea.
- **Solución:** pedir `-o json`, parsear con `python3`, y reemplazar la línea o agregarla.
  `make up` ya lo hace solo.

### El backend en Docker no ve `127.0.0.1` **[heredado]**
- **Solución:** en `docker-compose.yml`, `DATABASE_URL`, `AUTH_URL` y `JWKS_URL` apuntan a
  `host.docker.internal`; fuera de Docker valen los defaults con `127.0.0.1`.

### Probar a mano con Swagger **[heredado]**
- `curl -X POST localhost:8000/v1/auth/anonymous` y *Authorize* en `/docs`. Los tokens
  vencen en 1 h.

### `ruff` se queja de `Depends()` (B008) **[heredado]**
- Es el idioma normal de FastAPI: se ignora `B008` en `backend/pyproject.toml`.

### `$1` sin tipo en sentencias con asyncpg **[heredado]**
- **Síntoma:** `could not determine data type of parameter $1` (o `AmbiguousParameterError`;
  en una vez, **todos los endpoints dieron 500**).
- **Causa:** el mismo parámetro usado con tipos distintos (`$1` como `uuid` y dentro de un
  `case when $4 then $1 end`), o dentro de un `select`/`case`.
- **Solución:** castear explícito (`$1::uuid`, `$4::boolean`, `$1::text`).

### asyncpg no ejecuta varias sentencias con parámetros **[heredado]**
- **Síntoma:** `cannot insert multiple commands into a prepared statement` en un test que
  hace `select set_config(...); update ...`.
- **Solución:** un helper que abre la transacción y ejecuta las sentencias por separado.
  `set_config(..., true)` solo vale dentro de la transacción.

### Triggers de protección con variable de sesión **[heredado, decisión]**
- Una columna sensible (rol, karma) solo cambia dentro de una transacción que haga
  `select set_config('app.<algo>_write','on', true)`. La API pública no tiene camino para
  escribirla; se asigna por SQL o por un target del Makefile. **Acá se usa para**: roles y
  membresías, la auditoría inmutable y los campos bloqueados del catálogo.

### Reiniciar el backend tras migrar **[heredado]**
- **Síntoma:** usuarios nuevos con una columna nueva en `NULL`, o una feature nueva que no
  hace nada desde el celular.
- **Causa:** un contenedor del backend viejo (otra imagen) corriendo contra la base ya
  migrada, o el APK nuevo contra un servidor viejo.
- **Solución:** `docker compose up -d --build backend` después de cada migración o cambio
  de backend; comprobar con `docker exec <contenedor> ls app/services`.

### Cuenta dada de baja: 403, no 401 **[heredado, no aplica todavía]**
- La app interpreta 401 como «sesión perdida» y crea otra cuenta anónima; por eso la baja
  responde 403 con un código. Aplica si acá se agrega baja de cuentas (clientes con deuda
  vetados, por ejemplo).

---

## Docker y varios proyectos en la misma máquina

> Importante: **`almacenero` y `guazu` van a convivir en la misma Mac.** Este es el
> problema más probable del corte 0.

### `make up` falla con «port is already allocated» **[heredado]**
- **Síntoma:** `Bind for 0.0.0.0:8000 failed: port is already allocated`; un `make down`
  seguido de `make up` da lo mismo.
- **Causa:** Docker Compose nombraba el proyecto por la **carpeta**; checkout principal y
  worktrees eran proyectos distintos con los mismos puertos. `supabase stop` es global,
  `docker compose down` solo baja el proyecto de su carpeta.
- **Solución:** `docker-compose.yml` fija `name: <proyecto>`. Un solo proyecto, sin importar
  la carpeta.
- **Diagnóstico:**
  ```bash
  docker compose ls -a
  docker ps -a --format '{{.Names}}\t{{.Ports}}\t{{.Status}}' | grep -v supabase
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  ```

### Dos proyectos de Supabase CLI en la misma máquina **[guazu, a resolver en el corte 0]**
- **Riesgo:** el Supabase CLI local usa los puertos 54321 a 54324 y el `id` del proyecto
  en `supabase/config.toml`; el backend usa 8000 y el panel 8080. Con almacenero levantado,
  guazu choca.
- **Decisión:** guazu usa **otros puertos** desde el principio (Supabase `55321`+, backend
  `8100`, panel `8180`), un `name: guazu` en el compose y un `project_id` propio en
  `config.toml`. Así los dos proyectos pueden estar arriba a la vez. Se confirma y se
  documenta acá al hacer el corte 0.

### El Supabase local es uno solo y lo comparten los worktrees **[heredado]**
- **Síntoma:** `make migrate` falla con *Remote migration versions not found in local
  migrations directory*.
- **Causa:** otra rama ya aplicó una migración que esta no tiene.
- **Solución:** aplicar a mano la migración propia (`psql "$DATABASE_URL" -f …` y un
  `insert` en `supabase_migrations.schema_migrations`), o traer la otra rama. En CI (base
  vacía) no pasa.

### Un worktree nuevo no trae `.env` ni `.venv` **[heredado]**
- **Síntoma:** `make test` falla con `backend/.venv/bin/python: No such file or directory`.
- **Causa:** `.env` y `.venv` están ignorados por git.
- **Solución:** copiar `.env` del checkout principal y correr `make venv`.

### Docker Desktop con poca memoria **[heredado]**
- **Síntoma:** «… isn't responding» (ANR) y todo lentísimo con emulador + Supabase +
  Gradle a la vez. Docker de la Mac (8 GB) + emulador (5-6 GB) agotan la memoria.
- **Solución:** darle ≥ 8 GB a Docker en un equipo de 16 GB o más; parar los contenedores
  de Supabase que no se usan (`studio`, `analytics`, `vector`, `edge_runtime`, `pg_meta`,
  `realtime`, `inbucket`: el backend solo necesita `db`, `auth` y `kong`), con
  `supabase start -x <nombre>`; arrancar el emulador con `-memory 3072`.
- La **Mac nueva, más potente**, debería aliviar esto.

---

## Tests

### Tests contra Postgres real **[heredado]**
- `make test` corre pytest contra el Postgres del Supabase CLI con el seed aplicado. Sin
  Docker no corren. Decisión del stack: **sin mocks de base**.

### Un test pasa solo y falla en la suite con 429 **[heredado]**
- **Causa:** el rate limit por IP vive en memoria y el `TestClient` es siempre la misma IP.
- **Solución:** fixture `autouse` en `conftest.py` que reinicia el limitador en cada test.

### Los tests ensucian la base **[heredado]**
- Datos de prueba con **prefijo reconocible** (`79999…` para EAN, `test-…` para nombres) y
  limpieza al terminar; nombres con **sufijo aleatorio** para evitar colisiones con corridas
  anteriores que fallaron a mitad de camino.
- **No contar filas totales** de tablas solo-agregar (auditoría): filtrar por id de entidad.
- Si el borrado falla por clave foránea, limpiar primero las filas hijas.

### Widget tests de Flutter **[heredado]**
- Un widget test atajó un bug que en el emulador habría crasheado: los widget tests valen la
  pena. La UI recibe **funciones** (`AppDeps`) en lugar de repositorios, así los tests usan
  un backend falso sin red.
- La lista es perezosa: en el test hay que agrandar la pantalla para que construya las filas.

### Casos de prueba de dinero e impuestos **[guazu]**
- Los casos del cálculo de precio y de la conversión Monotributo ↔ RI se **fijan como datos**
  (entrada → salida exacta) y los valida el contador (`validar-profesional/contador.md`).

---

## CI

### `make up` falla en GitHub Actions **[heredado]**
- **Síntoma:** `failed to parse config: 'db.migrations' has invalid keys: enabled`.
- **Causa:** `supabase/setup-cli` instalaba `latest`, distinto del CLI local.
- **Solución:** fijar la versión en el workflow (`version: 3.1.0`) igual que en local.
  **Al subir el CLI local, subir también esa versión.**
- Si el CI de `main` falla desde el principio, nadie se entera hasta mirar la pestaña
  Actions: mirarlo con el primer push.

---

## Git y GitHub

### `gh` no estaba logueado con la cuenta correcta **[heredado]**
- **Solución:** `gh auth login` (navegador, HTTPS); verificar **con qué cuenta** estás
  logueado en el navegador; confirmar con `gh auth status`. Si Git usa credenciales de otra
  cuenta, borrar la entrada de `github.com` del llavero o `gh auth setup-git`.

### El commit sale con un email que no es el de la cuenta **[heredado]**
- **Causa:** `user.email` de Git de otro contexto (trabajo).
- **Solución (solo en el repo):** `git config user.email "<id>+<usuario>@users.noreply.github.com"`,
  `git config user.name "<usuario>"` y, si todavía no se subió,
  `git commit --amend --reset-author --no-edit`. El id sale de `gh api user --jq .id`.
- **Esto vale en la otra Mac y en Windows**: configurarlo antes del primer commit.

### Repo público: nada sensible **[heredado]**
- `.env` ignorado; `.env.example` solo con valores de desarrollo local. No documentar
  emails, tokens ni datos personales. Un **backup tiene datos de personas**: nunca al repo.

### PRs apilados **[heredado]**
- Al mergear el primero, GitHub reapunta el siguiente a `main` solo.

### Finales de línea entre Mac y Windows **[guazu]**
- `.gitattributes` fija `LF` para que los scripts de bash no se rompan en Windows.

---

## Probar en emulador y en celular

### Emulador **[heredado]**
- **La app abre y se queda en el splash:** en debug la primera vez tarda 20-30 s.
- **`am start` → *Activity class … does not exist*** justo tras bootear: transitorio.
- **El escáner muestra una escena pixelada:** es la cámara virtual. Abre y pide permiso,
  pero **no lee códigos de barras**: para escanear de verdad hace falta un celular.
- **Desde el emulador el backend es `http://10.0.2.2:<puerto>`.**
- **Ubicación:** `adb emu geo fix <longitud> <latitud>` (¡primero longitud!).
- **Con poca RAM** Google Play Services también se cuelga al pedir ubicación.
- **`monkey -p <paquete> 1` no abre la app:** el `applicationId` no coincide con el nombre
  del paquete de `MainActivity`. Tocar el ícono en el launcher.
- **Windows (Intel):** el emulador debe usar imagen `x86_64`, no `arm64-v8a`. **[guazu, sin
  verificar]**

### Celular real **[heredado]**
- **`10.0.2.2` no existe en un celular.** `make apk` compila contra la IP de la máquina en
  la red (`LAN_IP=…` para forzarla).
- **HTTP sin TLS** solo en el build *debug*; el release exige HTTPS.
- **Para que conecte:** mismo Wi-Fi, backend arriba, y tres trampas: la IP cambia (hay que
  recompilar), el firewall de macOS puede bloquear a Docker y las redes de invitados aíslan
  los dispositivos.
- **Instalar:** `adb install -r app-debug.apk` o pasar el archivo y permitir «instalar apps
  desconocidas» (Play Protect avisa).

### «No pudimos conectar con el servidor» con el backend sano **[heredado]**
- **Causa que pasó dos veces:** un APK **viejo** instalado (todos se llaman `app-debug.apk`).
  Un APK anterior a un cambio de backend no manda un dato nuevo, el backend contesta 403 y
  la app mostraba el mismo cartel que «sin red».
- **Solución:** una **pantalla «Acerca de» con versión, commit, servidor, estado de
  `/v1/health` e IP del celular**, y que el error diga «El servidor respondió 403 (…)» cuando
  hay respuesta. Leer eso antes de adivinar.
- **Cómo separar las causas (de barato a caro):** (1) ¿la versión es la que acabás de
  compilar?; (2) «sin conexión»: red, aislamiento de clientes, IP cambiada, firewall;
  (3) «respondió error N»: el backend (`docker compose logs backend`).
- **Probar la red sin el celular:** `curl http://<ip>:<puerto>/v1/health` desde otra máquina.
- **Ver la URL compilada en un APK:** `strings` de `assets/flutter_assets/kernel_blob.bin`.
- **Aplica acá en las dos apps** (Cliente y Negocio): incluir versión y servidor en «Acerca de».

### La app ya tenía una sesión guardada **[heredado]**
- Un cambio de acceso (p. ej. invitaciones) no se nota si la app ya tiene sesión. Para
  probar un alta nueva: borrar los datos de la app o desinstalarla.

### Servidor dormido (Fly.io) **[heredado]**
- El backend se apaga solo sin tráfico; el primer pedido espera el arranque en frío (varios
  segundos). La app espera cada intento `API_TIMEOUT_S` (20 por defecto, se cambia al
  compilar), muestra «Despertando servidor…» si pasan 4 s y reintenta con backoff **solo lo
  que se puede repetir sin efectos** (GET y refresh). Un POST (como cargar un precio) no se
  reintenta solo: podría duplicarse.
- **Acá**: con operaciones de lote e idempotencia (Doc 2 §Operaciones en lote), un POST **sí**
  se puede reintentar si lleva clave de idempotencia. A confirmar al implementarlo.

---

## Escáner de códigos

### Qué usa almacenero (probado en celular real) **[heredado]**
- Paquete `mobile_scanner` (`^7.5.0`) con los formatos `ean13`, `ean8`, `upcA` y `upcE`,
  `DetectionSpeed.noDuplicates`, y `errorBuilder` que ofrece ingresar el código a mano.
- La app solo valida que el código tenga **8 a 14 dígitos**; el **backend** hace el relleno
  (UPC-A de 12 dígitos → EAN-13 con un `0`) antes de buscar. Se hace en un solo lugar.
- **Entrada manual de EAN junto al escáner:** plan B si falla la cámara o el permiso, y
  permite probar sin celular.
- El escaneo real está probado en celular; **no hay tests automáticos de la cámara**.
- **Pendiente heredado:** medir qué entrega `mobile_scanner` para UPC-A (si el valor llega
  de 12 o de 13 dígitos). Se mide en un celular real en el corte 6 y se anota acá.
- **En iOS** se debe declarar el permiso de cámara en `Info.plist`.

### Un EAN de ejemplo con dígito verificador inválido **[heredado]**
- El EAN `7791234567890` del seed de almacenero tiene dígito inválido: funciona como carga
  manual, pero un ETL nunca lo empareja. **Acá los seeds deben usar EAN válidos.**

---

## ETL y catálogo

*(Diseño y decisiones: `07-catalogo.md`.)*

### El volcado completo de OFF pesa 13,6 GB en JSONL **[heredado]**
- Plan inicial: «varios GB». El JSONL pesa 13,6 GB y el dump de MongoDB 16,6 GB, pero el **CSV
  pesa 1,5 GB** y trae las columnas que usamos.
- **Solución:** leer el CSV en streaming. Medir con `curl -sIL <url> | grep -i content-length`
  antes de bajar nada. La muestra de 30 MB se baja por rango.

### Un `.csv.gz` truncado rompe el ETL **[heredado]**
- **Síntoma:** `EOFError: Compressed file ended before the end-of-stream marker`.
- **Solución:** el lector atrapa el error y termina; la última fila cortada se descarta.

### El volcado completo de OFF trae caracteres NUL; los CSV de SEPA, BOM y NUL **[heredado]**
- **Síntoma:** `_csv.Error: line contains NUL` a los 60 s con el volcado completo (la muestra
  de 30 MB andaba bien).
- **Solución:** filtrar `\0` línea por línea antes del lector CSV; en SEPA, abrir con
  `utf-8-sig` (9 de 16 archivos empiezan con BOM).
- **Moraleja:** probar con el volcado completo antes de dar por bueno un ETL.

### Las descargas de SEPA se cortan **[heredado]**
- **Síntoma:** `curl: (18) Transferred a partial file`; zips truncados («End-of-central-
  directory signature not found»).
- **Solución:** reintentar y validar con `unzip -tq`; el servidor no admite reanudar.

### SEPA: zip interno roto y «1 unidad» **[heredado]**
- **Síntoma:** `BadZipFile` a mitad de la carga y 813 conflictos falsos de tamaño contra OFF
  (tras el arreglo, 157 reales).
- **Causa:** el zip diario trae un zip de comercio vacío (0 bytes); SEPA pone la **cantidad de
  envases** («1 UNI») en la presentación.
- **Solución:** saltar y contar los zips inválidos; no tomar «1 u» como tamaño y no comparar
  tamaños de familias distintas (masa, volumen, unidades).

### EAN-8 y UPC-A en el volcado de OFF **[heredado]**
- OFF rellena con ceros hasta 13 dígitos; el escáner entrega 8 o 12. `normalizar_ean` devuelve
  `0 + UPC-A`, recupera los EAN-8 `00000xxxxxxxx` y descarta los de balanza (empiezan con 2)
  y los de dígito verificador inválido.

### Filas con menos columnas que la cabecera **[heredado]**
- **Síntoma:** `AttributeError: 'NoneType' ... strip` al leer un CSV de SEPA.
- **Causa:** `csv.DictReader` rellena con `None`.
- **Solución:** leer cada campo con `(fila.get(k) or "")`.

### Una dependencia solo del ETL **[heredado]**
- **Síntoma:** `ModuleNotFoundError: osmium`.
- **Solución:** `pip install -e "backend[dev,etl]"` (un `make venv` nuevo ya lo hace). Los
  extras pesados del ETL **no** van en la imagen del backend.

### Decisiones del ETL **[heredado, aplicadas acá]**
- Prioridad `manual > sepa > off`. Un ETL por fuente sobre una capa común; fusión por lotes
  en SQL con `COPY` a tabla temporal, no fila por fila.
- Lo que resuelve una persona se **bloquea con un trigger**; los ETL ni lo intentan.
- Los desacuerdos no se reabren una vez vistos (`unique` sobre el desacuerdo completo).
- Los ETL no tienen CI contra datos reales: los tests usan un CSV generado y la base local.
- Medido con el volcado completo: 4,08 M productos, 2,4 GB, 14 min de carga, solo 14 040
  argentinos: por eso **solo SEPA + OFF de Argentina y vecinos**.

### SEPA no trae imágenes **[heredado, impacta al escáner]**
- 74 024 de los 78 025 productos de SEPA **no tienen imagen**; en total el 68,6 % del
  catálogo no la tiene. **El escáner del cliente muestra imagen:** hace falta una imagen de
  reemplazo y, más adelante, fotos propias del negocio (ver `07-catalogo.md` §Imágenes).

---

## Normalizador de catálogo

*(Diseño: `07-catalogo.md`; origen: Doc 7 y cortes 13 y 14 de almacenero.)*

### El medidor tarda demasiado **[heredado]**
- **Síntoma:** más de 2 minutos para 134 mil productos.
- **Causa:** se reconstruía por llamada el conjunto de claves de marca (O(1 600) por producto).
- **Solución:** cachear con `lru_cache`; ahora ~10 s. **En una función que se llama millones de
  veces no se arma nada a partir del diccionario global.**

### `750 cm3` no se leía como tamaño **[heredado]**
- **Causa:** el patrón de unidades era `[a-zA-Z]+` y `cm3` tiene un dígito.
- **Solución:** `[a-zA-Z]+[0-9]?`. Afectaba también al campo de SEPA.

### Nombres que quedaban en una palabra o perdían «Pvc» **[heredado]**
- **Causa:** la «marca» de SEPA a veces trae la palabra del producto y `Pvc`/`Pet` también es
  un material.
- **Solución:** la marca no se saca del nombre si lo deja en menos de 2 palabras; las palabras
  de envase sueltas solo se sacan cuando el nombre trae también un tamaño.

### El campo de tamaño de SEPA miente **[heredado]**
- ~1 000 casos: coma corrida (`1.5 g` con el nombre en `1.5 kg`), `1 g` imposible, `100 l` por
  `1 l`. Si campo y nombre difieren por una potencia de diez, o el campo es ≤ 1 g/ml, gana el
  nombre (`tamano_campo_corregido`); el resto queda `dudoso`.

### El normalizador no era idempotente **[heredado]**
- **Síntoma:** volver a pasarlo por el catálogo ya normalizado cambiaba cientos de filas.
- **Causa:** casos reales que los tests no cubrían (dos sufijos de SEPA, la marca repetida en
  el nombre, `oBLEAS`, `c/c/a`, …) y motivos que salen de comparar con el dato crudo y no se
  ven en un nombre ya limpio.
- **Solución:** arreglar esos casos y que los motivos «pegajosos» viajen con la fila.
- **Cómo chequearlo:** correr la re-normalización dos veces; la segunda debe decir
  «Cambiarían: 0». Comparar `normalizar(normalizar(x))` con `normalizar(x)` sobre el crudo.

### `ruff format` reformateó archivos ajenos **[heredado]**
- **Causa:** se corrió el `ruff` del sistema, no el del venv, sin la configuración del proyecto.
- **Solución:** usar siempre `make lint`.

### Un producto `descartado` no se encuentra **[heredado, a propósito]**
- Es la decisión del dueño de almacenero: hasta que alguien lo complete, la búsqueda
  contesta «no encontrado». **Acá** esto debe **no bloquear** al negocio: ver `07-catalogo.md`.

---

## Despliegue: Fly.io, Supabase y dominio

*(Guía completa de almacenero: su `docs/06-deploy.md`, en el PR #19 abierto. Costos en `costos.md`.)*

### Supabase solo no alcanza **[heredado]**
- Da Postgres, Auth y Storage, pero el backend FastAPI es una imagen Docker y necesita un host
  de contenedores (Fly.io).

### Conexión a la base desde el backend **[heredado]**
- La conexión **directa** de Supabase suele ser solo IPv6; el *pooler* en modo transacción
  (puerto **6543**) **rompe los prepared statements de asyncpg**. Usar el **session pooler
  (5432)**. Es también la que sirve para `pg_dump`.
- **Síntoma de equivocarse:** errores de *prepared statement*; `connection refused`/timeouts.
  También revisar que la contraseña esté codificada en la URL.

### Supabase gratis se pausa y no hace backups **[heredado]**
- El plan gratuito **pausa el proyecto tras 1 semana sin actividad**: el backend falla y la app
  dice «no pudimos conectar». Se reactiva desde el dashboard. Con uso diario no se pausa; para
  épocas muertas, un `curl` periódico a `/v1/health`.
- **No hace backups automáticos**: por eso existe `make backup` (ver abajo).

### Fly.io **[heredado]**
- `auto_stop_machines`: la máquina se apaga sin tráfico y arranca con el primer pedido.
  Cuesta centavos. **No pedir IPv4 dedicada** (cuesta aparte). Región `gru` (São Paulo), la más
  cercana a Argentina y a Supabase `sa-east-1`.
- Los secretos van con `fly secrets`, nunca en la imagen ni en el repo.
- El `HEALTHCHECK` usa `python -c` porque la imagen `slim` no trae `curl`.
- El backend corre con usuario no root y escucha en `$PORT`.

### Dominio con Cloudflare y Fly **[heredado]**
- **El orden importa:** CNAME **solo DNS (nube gris)** → `fly certs add` → verificar
  «Issued» → recién después el proxy (nube naranja) con SSL **Full (strict)**. Con el proxy
  puesto antes, la verificación del certificado puede fallar.
- Con proxy naranja el rate limit necesita `PROXY_HOPS=2` (Fly + Cloudflare); con nube gris, 1.
- **Un solo nivel de subdominio** (`guazu-api.crulises.dev`, no `api.guazu.crulises.dev`): los
  certificados comodín y el proxy gratuito de Cloudflare cubren un nivel.
- **CORS:** el panel web solo puede llamar al backend si su origen exacto (con `https://`, sin
  `/` final) está en `CORS_ORIGINS`. La app móvil no usa CORS.
- Nunca poner Cloudflare Access delante de la API: rompería la app del celular.
- Activar renovación automática y 2FA en el registrador del dominio.

### `applicationId` y keystore **[heredado, decisión pendiente acá]**
- Una vez publicado, el `applicationId` **no se puede cambiar**; Android lo trata como otra
  app, así que cambiarlo después hace perder sesiones. Almacenero lo cambió antes del primer
  release a `dev.crulises.almacenero` (dominio **que controlás**, invertido).
- **Acá, decidido (D50, 2026-11-21)**: `dev.crulises.guazu.cliente` y `dev.crulises.guazu.negocio`.
  Se había pensado `ar.guazu.*`, pero `guazu.ar` no es un dominio tuyo.
- La **keystore** firma las actualizaciones: si se pierde, no se puede actualizar la app.
  Guardarla **fuera del repo y con copia** (gestor de contraseñas). Mismo cuidado para la clave
  del Play Store y de Apple.
- El release **exige HTTPS** (el permiso de HTTP sin cifrar existe solo en el manifest de debug).
- Cambiar de `applicationId` obliga a **desinstalar** la versión vieja de cada celular de prueba.

### Panel web de plataforma **[heredado]**
- `nginx-unprivileged` (puerto 8080) sirviendo archivos estáticos bajo `/admin/`. La URL del
  backend no está en el código: nginx escribe `/admin/config.js` al arrancar con `API_URL`.
- **Redirects relativos** (`absolute_redirect off`): detrás de Fly nginx no conoce su nombre ni
  el `https` público.
- **«No puedo conectar con el backend»** o error de CORS al abrir el panel desde otra máquina:
  agregar el origen a `CORS_ORIGINS` y reiniciar.
- **Gotchas de Alpine.js:** `x-model.debounce` junto con `@input` dispara con el valor viejo
  (usar `x-model` plano y `@input.debounce.400ms`); en un handler, leer lo que haga falta de la
  ficha **antes** de cerrarla.
- Esta máquina no tiene `node`: el JS del panel no se chequea con `node --check`, se prueba en
  el navegador.
- Login del panel: email y contraseña de GoTrue, solo para el rol de plataforma. Un usuario
  anónimo promovido **no** entra (no tiene credenciales). Crear el admin: un target del
  Makefile; si el email ya existe, GoTrue responde el signup sin sesión y el CLI cae a iniciar
  sesión con la contraseña.

---

## Backup y ensayo de salida

*(Se hace el ensayo con la versión mínima viable: `revisar/ensayo-de-salida.md`.)*

### `make backup` y `make restore-test` **[heredado]**
- `pg_dump` (formato custom, solo el esquema `public`) a `backups/<proyecto>-<fecha>.dump` más
  un `.conteos` con las filas de las tablas clave. `backups/` está **ignorado por git**.
- `restore-test` crea una base temporal en el mismo servidor, restaura ahí el último dump,
  compara conteos y la borra, **también si falla**. Nunca escribe en la base real.
- Copiar el `.dump` **fuera de la máquina**: un backup en el mismo disco no es un backup.

### `pg_restore` falla con `unrecognized configuration parameter "transaction_timeout"` **[heredado]**
- **Causa:** el `pg_dump` de la Mac es 17 y escribe un `SET` que los servidores 15 y 16 no
  conocen.
- **Solución:** filtrar esa línea al restaurar.

### `schema "public" already exists` al restaurar **[heredado]**
- **Causa:** el dump incluye `CREATE SCHEMA public` y toda base nueva ya lo tiene. **Solución:**
  filtrar esa línea.
- Las **extensiones** (`postgis`, `pg_trgm`, `unaccent`) **no** vienen en un dump de
  `--schema=public`: crearlas antes de restaurar (o correr primero las migraciones).

### `permission denied for table spatial_ref_sys` **[heredado]**
- **Causa:** es una tabla de PostGIS con otro dueño. **Solución:** `--exclude-table=spatial_ref_sys`.

### Lo que el backup NO cubre **[heredado]**
- **`auth.users` de Supabase Auth** (cuentas y contraseñas) y los **secretos**. Para auth, la
  salida es autoalojar GoTrue (Doc 2 §Portabilidad). `pg_dump` debe ser de versión **igual o
  mayor** que el servidor.
- **Antes de un backup de producción**, verificar que los conteos impresos son los de producción
  y no los de la base local (si falta `.env.prod`, el target caería en `.env.example`).

---

## Abuso y límites de uso

### El rate limit por IP detrás de un proxy **[heredado]**
- **Síntoma:** o frena a todos o no frena a nadie.
- **Causa:** sin `PROXY_HOPS` se usa la IP del socket, que detrás de un proxy es la del proxy.
- **Solución:** `PROXY_HOPS=<cantidad de proxies confiables>`; se toma la IP desde la **derecha**
  de `X-Forwarded-For`. Con un valor de más, el cliente puede falsificar su IP.

### El rate limit por IP detrás de Docker Desktop **[heredado]**
- **Síntoma:** el celular recibe 429 casi sin usarlo; en el log todos los pedidos vienen de
  `192.168.65.1`.
- **Causa:** Docker Desktop (Mac) enmascara el origen: celular, `curl` y tests llegan con la
  misma IP, y el cupo por IP pasa a ser **uno para todos**.
- **Solución en desarrollo:** subir el cupo en el seed; para vaciar el contador,
  `docker restart <backend>` (vive en memoria). En producción, con la IP real, el cupo vuelve a
  ser por persona.

### `/v1/auth/anonymous` sin límite **[heredado]**
- Cualquiera podría crear usuarios en bucle. **Acá**, antes de abrir el escáner al público, hay
  que tener rate limit por IP en el alta anónima y en la lectura de precios (Doc 2 §Abuso).
  En almacenero se resolvió con PINs de invitación de un solo uso, cupo por IP y límites por
  usuario. Para un escáner público abierto, el cupo por IP y por sesión es lo mínimo.

### Dispositivo asociado a una cuenta **[heredado, opcional]**
- Almacenero usa `ANDROID_ID` (solo se guarda el hash) para frenar altas nuevas tras una baja.
  Es relevante si acá se veta a clientes con deuda; no es de la v0.1.

---

## Específicos de guazu

### Setup de la Mac nueva (2026-11-22) **[guazu]**
- Mac Apple Silicon, macOS 27.2, 36 GB de RAM, Xcode 27.2 ya instalado. Guion de `06-setup-entorno.md`
  seguido sin cambios; todo bajó sin cortes.
- **Flutter 3.50.0 desde git** (`git clone --depth 1 --branch 3.50.0`) en `~/development/flutter`. `flutter doctor`
  marca `[!] Flutter` por «unknown channel» (`[user-branch]`): es esperable con un clon por tag, no es un error.
- **Chrome** en rojo en `flutter doctor`: la web está fuera de alcance.
- `avdmanager create avd` imprime el error de `devices.xml` y crea el AVD igual (ya conocido).
- **Docker Desktop** arrancó con ~7,7 GB: subirlo a >= 8 GB (Settings > Resources) antes del primer `make up`. El
  comando `docker` no está en el PATH hasta que Docker Desktop termina de configurarse; sirve
  `/Applications/Docker.app/Contents/Resources/bin/docker`.
- `brew install supabase/tap/supabase` trae la **3.2.0**, pero el CI fija la **3.1.0**. Solución aplicada: `brew uninstall
  supabase` y copiar a `/opt/homebrew/bin/supabase` el binario de `supabase_3.1.0_darwin_arm64.tar.gz` del release
  de GitHub (sha256 verificado contra `checksums.txt`). Ya no lo gestiona brew, así que no se actualiza solo.
- **Docker fuera del PATH:** se agregó `/Applications/Docker.app/Contents/Resources/bin` al PATH en `~/.zshrc`
  (sin sudo). En esta versión de Docker Desktop la memoria se cambia en Settings > VM resources (quedó en 16 GB).
- `libpq` de brew es la 19 (el doc mencionaba la 17): sirve, `pg_dump` solo debe ser >= al servidor.
- El `git config` global usó el email personal, no el noreply de GitHub: ajustar por repo.

---

## Decisiones de diseño heredadas

Vigentes acá salvo que el Doc 2 diga otra cosa:

- **Auth anónima vía backend** (el cliente no conoce al proveedor de auth).
- **`usuarios.auth_id` sin FK a `auth.users`**: el esquema no depende del schema `auth` de
  Supabase y es portable.
- **Variables sin nombre de proveedor**: `JWT_SECRET`, `JWKS_URL`, `AUTH_URL`, `DATABASE_URL`.
- **Sesión en almacenamiento cifrado** (`flutter_secure_storage`); renovación automática y un
  reintento ante 401. Un solo `AuthedApi` para las llamadas autenticadas.
- **Permisos por capacidad, no por rol**: los endpoints piden una capacidad; el mapa de
  permisos se puede mover a tablas sin tocar endpoints. (Acá ya nace con tablas, Doc 2.)
- **Valores por defecto en código** para la configuración: si falta una clave en la base, el
  backend usa un default seguro.
- **La frescura, los umbrales y cálculos los hace el backend**, no la app.
- **`GET` del producto** devuelve datos con fecha ISO 8601 y la app los formatea.
- **Pantalla «Acerca de»** con versión, servidor, estado y licencias de datos, accesible aunque
  no haya conexión.
- **El filtro por radio y las reglas de negocio viven en el backend.**
- **Seeds mínimos; datos grandes nunca al repo.**
