import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'ui_kit_localizations_en.dart';
import 'ui_kit_localizations_es.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of UiKitLocalizations
/// returned by `UiKitLocalizations.of(context)`.
///
/// Applications need to include `UiKitLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/ui_kit_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: UiKitLocalizations.localizationsDelegates,
///   supportedLocales: UiKitLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the UiKitLocalizations.supportedLocales
/// property.
abstract class UiKitLocalizations {
  UiKitLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static UiKitLocalizations of(BuildContext context) {
    return Localizations.of<UiKitLocalizations>(context, UiKitLocalizations)!;
  }

  static const LocalizationsDelegate<UiKitLocalizations> delegate =
      _UiKitLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('es'),
  ];

  /// No description provided for @ayudaTooltip.
  ///
  /// In es, this message translates to:
  /// **'Ayuda'**
  String get ayudaTooltip;

  /// No description provided for @ayudaSinTexto.
  ///
  /// In es, this message translates to:
  /// **'Todavía no hay ayuda escrita para esta pantalla.'**
  String get ayudaSinTexto;

  /// No description provided for @cerrar.
  ///
  /// In es, this message translates to:
  /// **'Cerrar'**
  String get cerrar;

  /// No description provided for @acercaTitulo.
  ///
  /// In es, this message translates to:
  /// **'Acerca de'**
  String get acercaTitulo;

  /// No description provided for @acercaTooltip.
  ///
  /// In es, this message translates to:
  /// **'Acerca de'**
  String get acercaTooltip;

  /// No description provided for @acercaVersionDeApp.
  ///
  /// In es, this message translates to:
  /// **'Versión {version}'**
  String acercaVersionDeApp(String version);

  /// No description provided for @acercaDiagnostico.
  ///
  /// In es, this message translates to:
  /// **'Diagnóstico'**
  String get acercaDiagnostico;

  /// No description provided for @acercaVersion.
  ///
  /// In es, this message translates to:
  /// **'Versión'**
  String get acercaVersion;

  /// No description provided for @acercaCompilada.
  ///
  /// In es, this message translates to:
  /// **'Compilada'**
  String get acercaCompilada;

  /// No description provided for @acercaServidor.
  ///
  /// In es, this message translates to:
  /// **'Servidor'**
  String get acercaServidor;

  /// No description provided for @acercaEstado.
  ///
  /// In es, this message translates to:
  /// **'Estado'**
  String get acercaEstado;

  /// No description provided for @acercaVersionBackend.
  ///
  /// In es, this message translates to:
  /// **'Versión del servidor'**
  String get acercaVersionBackend;

  /// No description provided for @acercaIpDispositivo.
  ///
  /// In es, this message translates to:
  /// **'IP del dispositivo'**
  String get acercaIpDispositivo;

  /// No description provided for @acercaSinRed.
  ///
  /// In es, this message translates to:
  /// **'sin red'**
  String get acercaSinRed;

  /// No description provided for @acercaEstadoOk.
  ///
  /// In es, this message translates to:
  /// **'conectado ({ms} ms)'**
  String acercaEstadoOk(int ms);

  /// No description provided for @acercaEstadoBaseCaida.
  ///
  /// In es, this message translates to:
  /// **'el servidor responde, pero la base de datos no'**
  String get acercaEstadoBaseCaida;

  /// No description provided for @acercaEstadoSinConexion.
  ///
  /// In es, this message translates to:
  /// **'sin conexión ({motivo})'**
  String acercaEstadoSinConexion(String motivo);

  /// No description provided for @acercaEstadoRechazo.
  ///
  /// In es, this message translates to:
  /// **'El servidor respondió {status} ({mensaje})'**
  String acercaEstadoRechazo(int status, String mensaje);

  /// No description provided for @acercaEstadoRechazoSinMensaje.
  ///
  /// In es, this message translates to:
  /// **'El servidor respondió {status}'**
  String acercaEstadoRechazoSinMensaje(int status);

  /// No description provided for @acercaConsultando.
  ///
  /// In es, this message translates to:
  /// **'consultando…'**
  String get acercaConsultando;

  /// No description provided for @acercaFuentesTitulo.
  ///
  /// In es, this message translates to:
  /// **'Fuentes de datos'**
  String get acercaFuentesTitulo;

  /// No description provided for @acercaFuentesIntro.
  ///
  /// In es, this message translates to:
  /// **'{app} usa datos abiertos de estas fuentes. Gracias a quienes los mantienen.'**
  String acercaFuentesIntro(String app);

  /// No description provided for @acercaAporta.
  ///
  /// In es, this message translates to:
  /// **'Aporta: {texto}'**
  String acercaAporta(String texto);

  /// No description provided for @acercaLicencia.
  ///
  /// In es, this message translates to:
  /// **'Licencia: {texto}'**
  String acercaLicencia(String texto);

  /// No description provided for @acercaPreciosAviso.
  ///
  /// In es, this message translates to:
  /// **'Los precios los carga cada comercio; no provienen de estas fuentes.'**
  String get acercaPreciosAviso;

  /// No description provided for @acercaLicenciasLibrerias.
  ///
  /// In es, this message translates to:
  /// **'Licencias de librerías'**
  String get acercaLicenciasLibrerias;

  /// No description provided for @fuenteOffNombre.
  ///
  /// In es, this message translates to:
  /// **'Open Food Facts'**
  String get fuenteOffNombre;

  /// No description provided for @fuenteOffAporta.
  ///
  /// In es, this message translates to:
  /// **'Productos: nombre, marca y tamaño'**
  String get fuenteOffAporta;

  /// No description provided for @fuenteOffLicencia.
  ///
  /// In es, this message translates to:
  /// **'ODbL 1.0 · contenidos DbCL 1.0 · imágenes CC BY-SA 3.0'**
  String get fuenteOffLicencia;

  /// No description provided for @fuenteOffTexto.
  ///
  /// In es, this message translates to:
  /// **'Datos de productos: Open Food Facts (openfoodfacts.org), una base colaborativa disponible bajo la Open Database License (ODbL) 1.0; sus contenidos individuales, bajo la Database Contents License (DbCL) 1.0. Las imágenes de productos se publican bajo Creative Commons Atribución-CompartirIgual (CC BY-SA) 3.0 y son de sus autores; {app} solo las enlaza.'**
  String fuenteOffTexto(String app);

  /// No description provided for @fuenteSepaNombre.
  ///
  /// In es, this message translates to:
  /// **'SEPA · Precios Claros'**
  String get fuenteSepaNombre;

  /// No description provided for @fuenteSepaAporta.
  ///
  /// In es, this message translates to:
  /// **'Productos de Argentina'**
  String get fuenteSepaAporta;

  /// No description provided for @fuenteSepaLicencia.
  ///
  /// In es, this message translates to:
  /// **'CC BY 4.0'**
  String get fuenteSepaLicencia;

  /// No description provided for @fuenteSepaTexto.
  ///
  /// In es, this message translates to:
  /// **'Datos de productos de Argentina: Secretaría de Comercio de la Nación, Sistema Electrónico de Publicidad de Precios Argentinos (SEPA, «Precios Claros»), licencia Creative Commons Atribución 4.0 Internacional (CC BY 4.0). Los datos fueron normalizados y combinados por {app}.'**
  String fuenteSepaTexto(String app);

  /// No description provided for @enlaceOff.
  ///
  /// In es, this message translates to:
  /// **'Open Food Facts'**
  String get enlaceOff;

  /// No description provided for @enlaceOdbl.
  ///
  /// In es, this message translates to:
  /// **'ODbL 1.0'**
  String get enlaceOdbl;

  /// No description provided for @enlaceDbcl.
  ///
  /// In es, this message translates to:
  /// **'DbCL 1.0'**
  String get enlaceDbcl;

  /// No description provided for @enlaceCcBySa.
  ///
  /// In es, this message translates to:
  /// **'CC BY-SA 3.0'**
  String get enlaceCcBySa;

  /// No description provided for @enlaceTerminosOff.
  ///
  /// In es, this message translates to:
  /// **'Términos'**
  String get enlaceTerminosOff;

  /// No description provided for @enlaceSepa.
  ///
  /// In es, this message translates to:
  /// **'SEPA'**
  String get enlaceSepa;

  /// No description provided for @enlaceCcBy.
  ///
  /// In es, this message translates to:
  /// **'CC BY 4.0'**
  String get enlaceCcBy;
}

class _UiKitLocalizationsDelegate
    extends LocalizationsDelegate<UiKitLocalizations> {
  const _UiKitLocalizationsDelegate();

  @override
  Future<UiKitLocalizations> load(Locale locale) {
    return SynchronousFuture<UiKitLocalizations>(
      lookupUiKitLocalizations(locale),
    );
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'es'].contains(locale.languageCode);

  @override
  bool shouldReload(_UiKitLocalizationsDelegate old) => false;
}

UiKitLocalizations lookupUiKitLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return UiKitLocalizationsEn();
    case 'es':
      return UiKitLocalizationsEs();
  }

  throw FlutterError(
    'UiKitLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
