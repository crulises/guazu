import 'package:flutter/widgets.dart';
import 'package:guazu_core/guazu_core.dart';

import 'app.dart';

/// Servidor al que habla la app. `make apk-negocio` lo fija con `--dart-define=API_URL=...`
/// (el emulador ve al host en 10.0.2.2; un celular necesita la IP de la máquina).
const _apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8100');
const _timeoutSegundos = int.fromEnvironment('API_TIMEOUT_S', defaultValue: 20);

void main() {
  runApp(
    GuazuNegocioApp(
      api: ApiClient(baseUrl: _apiUrl, timeout: const Duration(seconds: _timeoutSegundos)),
    ),
  );
}
