import 'package:guazu_core/guazu_core.dart';
import 'package:guazu_ui_kit/guazu_ui_kit.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'inicio_screen.dart';
import 'l10n/app_localizations.dart';

/// Abre un enlace en el navegador. En Android 11+ hace falta el intent `VIEW https` en
/// `<queries>` del manifest; si falta, tocar un enlace no hace nada (Doc 3).
Future<void> abrirEnlaceExterno(Uri uri) async {
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}

class GuazuNegocioApp extends StatelessWidget {
  const GuazuNegocioApp({
    super.key,
    required this.api,
    this.abrirEnlace = abrirEnlaceExterno,
    this.cargarInfo,
  });

  final ApiClient api;
  final Future<void> Function(Uri) abrirEnlace;

  /// Inyectable para los tests; por defecto consulta al servidor.
  final Future<InfoApp> Function()? cargarInfo;

  @override
  Widget build(BuildContext context) {
    return AyudaScope(
      cargar: cargarAyudaDeAssets,
      child: MaterialApp(
        onGenerateTitle: (context) => AppLocalizations.of(context).appNombre,
        localizationsDelegates: [
          AppLocalizations.delegate,
          UiKitLocalizations.delegate,
          ...GlobalMaterialLocalizations.delegates,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        theme: ThemeData(colorSchemeSeed: const Color(0xFF2E7D32)),
        home: InicioScreen(
          cargarInfo: cargarInfo ?? () => cargarInfoApp(api),
          abrirEnlace: abrirEnlace,
        ),
      ),
    );
  }
}
