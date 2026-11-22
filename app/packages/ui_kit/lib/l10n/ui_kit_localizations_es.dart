// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'ui_kit_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Spanish Castilian (`es`).
class UiKitLocalizationsEs extends UiKitLocalizations {
  UiKitLocalizationsEs([String locale = 'es']) : super(locale);

  @override
  String get ayudaTooltip => 'Ayuda';

  @override
  String get ayudaSinTexto =>
      'Todavía no hay ayuda escrita para esta pantalla.';

  @override
  String get cerrar => 'Cerrar';

  @override
  String get acercaTitulo => 'Acerca de';

  @override
  String get acercaTooltip => 'Acerca de';

  @override
  String acercaVersionDeApp(String version) {
    return 'Versión $version';
  }

  @override
  String get acercaDiagnostico => 'Diagnóstico';

  @override
  String get acercaVersion => 'Versión';

  @override
  String get acercaCompilada => 'Compilada';

  @override
  String get acercaServidor => 'Servidor';

  @override
  String get acercaEstado => 'Estado';

  @override
  String get acercaVersionBackend => 'Versión del servidor';

  @override
  String get acercaIpDispositivo => 'IP del dispositivo';

  @override
  String get acercaSinRed => 'sin red';

  @override
  String acercaEstadoOk(int ms) {
    return 'conectado ($ms ms)';
  }

  @override
  String get acercaEstadoBaseCaida =>
      'el servidor responde, pero la base de datos no';

  @override
  String acercaEstadoSinConexion(String motivo) {
    return 'sin conexión ($motivo)';
  }

  @override
  String acercaEstadoRechazo(int status, String mensaje) {
    return 'El servidor respondió $status ($mensaje)';
  }

  @override
  String acercaEstadoRechazoSinMensaje(int status) {
    return 'El servidor respondió $status';
  }

  @override
  String get acercaConsultando => 'consultando…';

  @override
  String get acercaFuentesTitulo => 'Fuentes de datos';

  @override
  String acercaFuentesIntro(String app) {
    return '$app usa datos abiertos de estas fuentes. Gracias a quienes los mantienen.';
  }

  @override
  String acercaAporta(String texto) {
    return 'Aporta: $texto';
  }

  @override
  String acercaLicencia(String texto) {
    return 'Licencia: $texto';
  }

  @override
  String get acercaPreciosAviso =>
      'Los precios los carga cada comercio; no provienen de estas fuentes.';

  @override
  String get acercaLicenciasLibrerias => 'Licencias de librerías';

  @override
  String get fuenteOffNombre => 'Open Food Facts';

  @override
  String get fuenteOffAporta => 'Productos: nombre, marca y tamaño';

  @override
  String get fuenteOffLicencia =>
      'ODbL 1.0 · contenidos DbCL 1.0 · imágenes CC BY-SA 3.0';

  @override
  String fuenteOffTexto(String app) {
    return 'Datos de productos: Open Food Facts (openfoodfacts.org), una base colaborativa disponible bajo la Open Database License (ODbL) 1.0; sus contenidos individuales, bajo la Database Contents License (DbCL) 1.0. Las imágenes de productos se publican bajo Creative Commons Atribución-CompartirIgual (CC BY-SA) 3.0 y son de sus autores; $app solo las enlaza.';
  }

  @override
  String get fuenteSepaNombre => 'SEPA · Precios Claros';

  @override
  String get fuenteSepaAporta => 'Productos de Argentina';

  @override
  String get fuenteSepaLicencia => 'CC BY 4.0';

  @override
  String fuenteSepaTexto(String app) {
    return 'Datos de productos de Argentina: Secretaría de Comercio de la Nación, Sistema Electrónico de Publicidad de Precios Argentinos (SEPA, «Precios Claros»), licencia Creative Commons Atribución 4.0 Internacional (CC BY 4.0). Los datos fueron normalizados y combinados por $app.';
  }

  @override
  String get enlaceOff => 'Open Food Facts';

  @override
  String get enlaceOdbl => 'ODbL 1.0';

  @override
  String get enlaceDbcl => 'DbCL 1.0';

  @override
  String get enlaceCcBySa => 'CC BY-SA 3.0';

  @override
  String get enlaceTerminosOff => 'Términos';

  @override
  String get enlaceSepa => 'SEPA';

  @override
  String get enlaceCcBy => 'CC BY 4.0';
}
