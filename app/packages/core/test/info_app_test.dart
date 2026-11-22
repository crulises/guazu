import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:guazu_core/guazu_core.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

ApiClient _api(MockClient c) => ApiClient(baseUrl: 'http://x:8100', cliente: c);

Future<List<IpInterfaz>> _sinIps() async => const [IpInterfaz('192.168.1.5', 'en0')];

void main() {
  test('salud ok: informa versión del backend y demora', () async {
    final api = _api(MockClient((r) async {
      expect(r.url.toString(), 'http://x:8100/v1/salud');
      return http.Response(
        jsonEncode({
          'estado': 'ok',
          'base': 'ok',
          'version': '0.0.7',
          'commit': 'abc123',
          'compilado': '2026-11-22T10:00',
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    }));
    final info = await cargarInfoApp(api, ips: _sinIps);
    final s = info.servidor as ServidorOk;
    expect(s.salud.version, '0.0.7');
    expect(info.ips.single.interfaz, 'en0');
  });

  test('403 con regla: es rechazo, no «sin red», y conserva el mensaje', () async {
    final api = _api(MockClient((r) async => http.Response(
          jsonEncode({
            'detail': {'codigo': 'dato_invalido', 'mensaje': 'No permitido'},
          }),
          403,
          headers: {'content-type': 'application/json'},
        )));
    final info = await cargarInfoApp(api, ips: _sinIps);
    final s = info.servidor as ServidorRechazo;
    expect(s.error.status, 403);
    expect(s.error.mensaje, 'No permitido');
  });

  test('error de red: sin conexión, sin lanzar', () async {
    final api = _api(MockClient((r) async => throw http.ClientException('sin ruta')));
    final info = await cargarInfoApp(api, ips: _sinIps);
    expect(info.servidor, isA<ServidorSinConexion>());
  });

  test('500 con cuerpo que no es JSON no rompe', () async {
    final api = _api(MockClient((r) async => http.Response('<html>', 500)));
    final info = await cargarInfoApp(api, ips: _sinIps);
    expect((info.servidor as ServidorRechazo).error.status, 500);
  });
}
