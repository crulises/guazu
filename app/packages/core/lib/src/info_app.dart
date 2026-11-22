import 'dart:async';
import 'dart:io';

import 'api_client.dart';
import 'build_info.dart';

/// Estado del servidor visto desde la app. Es estructura, no texto: la interfaz lo traduce
/// con sus `.arb` (ningún texto fijo en código).
sealed class EstadoServidor {
  const EstadoServidor();
}

/// Respondió bien; `demora` es lo que tardó.
class ServidorOk extends EstadoServidor {
  const ServidorOk(this.demora, this.salud);
  final Duration demora;
  final SaludBackend salud;
}

/// No hubo respuesta: red, IP cambiada, firewall, servidor caído.
class ServidorSinConexion extends EstadoServidor {
  const ServidorSinConexion(this.motivo);
  final String motivo;
}

/// Hubo respuesta, pero con error (por ejemplo 403): no es lo mismo que «sin red».
class ServidorRechazo extends EstadoServidor {
  const ServidorRechazo(this.error);
  final ApiException error;
}

class IpInterfaz {
  const IpInterfaz(this.ip, this.interfaz);
  final String ip;
  final String interfaz;
}

/// Todo lo que muestra «Acerca de» para diagnosticar sin adivinar (Doc 2 §Versionado).
class InfoApp {
  const InfoApp({
    required this.build,
    required this.apiUrl,
    required this.servidor,
    required this.ips,
  });

  final BuildInfo build;
  final String apiUrl;
  final EstadoServidor servidor;
  final List<IpInterfaz> ips;
}

/// IPv4 del dispositivo por interfaz. Inyectable para los tests.
typedef ListarIps = Future<List<IpInterfaz>> Function();

Future<List<IpInterfaz>> ipsDelDispositivo() async {
  try {
    final interfaces = await NetworkInterface.list(
      type: InternetAddressType.IPv4,
      includeLoopback: false,
    );
    return [
      for (final i in interfaces)
        for (final a in i.addresses) IpInterfaz(a.address, i.name),
    ];
  } on Object {
    return const [];
  }
}

/// Junta la información de la app. No lanza: un fallo de red es un dato, no un error.
Future<InfoApp> cargarInfoApp(
  ApiClient api, {
  BuildInfo build = BuildInfo.actual,
  ListarIps ips = ipsDelDispositivo,
}) async {
  final reloj = Stopwatch()..start();
  EstadoServidor estado;
  try {
    final salud = await api.salud();
    estado = ServidorOk(reloj.elapsed, salud);
  } on ApiException catch (e) {
    estado = ServidorRechazo(e);
  } on TimeoutException {
    estado = const ServidorSinConexion('timeout');
  } on Object catch (e) {
    estado = ServidorSinConexion(e.toString());
  }
  return InfoApp(
    build: build,
    apiUrl: api.baseUrl,
    servidor: estado,
    ips: await ips(),
  );
}
