import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Respuesta de `GET /v1/salud`.
class SaludBackend {
  const SaludBackend({
    required this.estado,
    required this.base,
    required this.version,
    required this.commit,
    required this.compilado,
  });

  factory SaludBackend.fromJson(Map<String, dynamic> j) => SaludBackend(
    estado: j['estado'] as String? ?? '',
    base: j['base'] as String? ?? '',
    version: j['version'] as String? ?? '',
    commit: j['commit'] as String? ?? '',
    compilado: j['compilado'] as String? ?? '',
  );

  final String estado;
  final String base;
  final String version;
  final String commit;
  final String compilado;
}

/// El servidor respondió, pero con error. Lleva la regla que explica el backend
/// (`detail.mensaje`) para mostrarla tal cual (Doc 2 §Panel, errores que explican la regla).
class ApiException implements Exception {
  ApiException(this.status, {this.codigo, this.mensaje, this.comoResolver, this.referencia});

  factory ApiException.fromResponse(http.Response r) {
    try {
      final cuerpo = jsonDecode(utf8.decode(r.bodyBytes));
      final d = cuerpo is Map ? cuerpo['detail'] : null;
      if (d is Map) {
        return ApiException(
          r.statusCode,
          codigo: d['codigo'] as String?,
          mensaje: d['mensaje'] as String?,
          comoResolver: d['como_resolver'] as String?,
          referencia: d['referencia'] as String?,
        );
      }
      if (d is String) return ApiException(r.statusCode, mensaje: d);
    } on FormatException {
      // cuerpo que no es JSON: queda solo el status
    }
    return ApiException(r.statusCode);
  }

  final int status;
  final String? codigo;
  final String? mensaje;
  final String? comoResolver;
  final String? referencia;

  @override
  String toString() => 'ApiException($status, $codigo, $mensaje)';
}

/// Cliente mínimo de la API. Las apps hablan SOLO con el backend (CLAUDE.md).
class ApiClient {
  ApiClient({
    required this.baseUrl,
    http.Client? cliente,
    this.timeout = const Duration(seconds: 20),
  }) : _http = cliente ?? http.Client();

  /// Base sin `/v1` (p. ej. `http://192.168.1.50:8100`).
  final String baseUrl;
  final Duration timeout;
  final http.Client _http;

  /// URL de la API versionada.
  Uri uri(String ruta) => Uri.parse('$baseUrl/v1$ruta');

  Future<SaludBackend> salud() async {
    final r = await _http.get(uri('/salud')).timeout(timeout);
    if (r.statusCode != 200) throw ApiException.fromResponse(r);
    return SaludBackend.fromJson(jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>);
  }

  void close() => _http.close();
}
