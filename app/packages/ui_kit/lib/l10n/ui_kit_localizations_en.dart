// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'ui_kit_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class UiKitLocalizationsEn extends UiKitLocalizations {
  UiKitLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get ayudaTooltip => 'Help';

  @override
  String get ayudaSinTexto => 'There is no help written for this screen yet.';

  @override
  String get cerrar => 'Close';

  @override
  String get acercaTitulo => 'About';

  @override
  String get acercaTooltip => 'About';

  @override
  String acercaVersionDeApp(String version) {
    return 'Version $version';
  }

  @override
  String get acercaDiagnostico => 'Diagnostics';

  @override
  String get acercaVersion => 'Version';

  @override
  String get acercaCompilada => 'Built';

  @override
  String get acercaServidor => 'Server';

  @override
  String get acercaEstado => 'Status';

  @override
  String get acercaVersionBackend => 'Server version';

  @override
  String get acercaIpDispositivo => 'Device IP';

  @override
  String get acercaSinRed => 'no network';

  @override
  String acercaEstadoOk(int ms) {
    return 'connected ($ms ms)';
  }

  @override
  String get acercaEstadoBaseCaida =>
      'the server answers, but the database does not';

  @override
  String acercaEstadoSinConexion(String motivo) {
    return 'no connection ($motivo)';
  }

  @override
  String acercaEstadoRechazo(int status, String mensaje) {
    return 'The server answered $status ($mensaje)';
  }

  @override
  String acercaEstadoRechazoSinMensaje(int status) {
    return 'The server answered $status';
  }

  @override
  String get acercaConsultando => 'checking…';

  @override
  String get acercaFuentesTitulo => 'Data sources';

  @override
  String acercaFuentesIntro(String app) {
    return '$app uses open data from these sources. Thanks to those who maintain them.';
  }

  @override
  String acercaAporta(String texto) {
    return 'Provides: $texto';
  }

  @override
  String acercaLicencia(String texto) {
    return 'License: $texto';
  }

  @override
  String get acercaPreciosAviso =>
      'Prices are entered by each store; they do not come from these sources.';

  @override
  String get acercaLicenciasLibrerias => 'Library licenses';

  @override
  String get fuenteOffNombre => 'Open Food Facts';

  @override
  String get fuenteOffAporta => 'Products: name, brand and size';

  @override
  String get fuenteOffLicencia =>
      'ODbL 1.0 · DbCL 1.0 contents · CC BY-SA 3.0 images';

  @override
  String fuenteOffTexto(String app) {
    return 'Product data: Open Food Facts (openfoodfacts.org), a collaborative database available under the Open Database License (ODbL) 1.0; its individual contents under the Database Contents License (DbCL) 1.0. Product images are published under Creative Commons Attribution-ShareAlike (CC BY-SA) 3.0 and belong to their authors; $app only links to them.';
  }

  @override
  String get fuenteSepaNombre => 'SEPA · Precios Claros';

  @override
  String get fuenteSepaAporta => 'Products from Argentina';

  @override
  String get fuenteSepaLicencia => 'CC BY 4.0';

  @override
  String fuenteSepaTexto(String app) {
    return 'Product data from Argentina: Secretaría de Comercio de la Nación, Sistema Electrónico de Publicidad de Precios Argentinos (SEPA, “Precios Claros”), Creative Commons Attribution 4.0 International (CC BY 4.0). The data was normalized and combined by $app.';
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
  String get enlaceTerminosOff => 'Terms';

  @override
  String get enlaceSepa => 'SEPA';

  @override
  String get enlaceCcBy => 'CC BY 4.0';
}
