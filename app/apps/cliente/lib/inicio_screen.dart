import 'package:guazu_core/guazu_core.dart';
import 'package:guazu_ui_kit/guazu_ui_kit.dart';
import 'package:material_ui/material_ui.dart';

import 'l10n/app_localizations.dart';

/// Inicio vacío del esqueleto: idioma, ayuda y «Acerca de» funcionando. La barra lleva el
/// icono de información también cuando falla la conexión: «Acerca de» sirve para diagnosticar.
class InicioScreen extends StatelessWidget {
  const InicioScreen({super.key, required this.cargarInfo, required this.abrirEnlace});

  final Future<InfoApp> Function() cargarInfo;
  final Future<void> Function(Uri) abrirEnlace;

  @override
  Widget build(BuildContext context) {
    final t = AppLocalizations.of(context);
    final kit = UiKitLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text(t.appNombre),
        actions: [
          const AyudaIcono('inicio'),
          IconButton(
            icon: const Icon(Icons.info_outline),
            tooltip: kit.acercaTooltip,
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => AcercaScreen(
                  nombreApp: t.appNombre,
                  cargarInfo: cargarInfo,
                  abrirEnlace: abrirEnlace,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Center(child: Text(t.inicioMensaje)),
    );
  }
}
