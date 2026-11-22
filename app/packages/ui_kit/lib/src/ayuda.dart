import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../l10n/ui_kit_localizations.dart';

/// Carga el texto de ayuda de una clave. Los textos viven en `app/apps/<app>/docs/ayuda/`
/// (`<clave>.<idioma>.md`, primera línea `# Título`); nunca en el código (CLAUDE.md).
typedef CargarAyuda = Future<String?> Function(String clave, Locale idioma);

/// Texto de ayuda ya separado en título y cuerpo.
class TextoAyuda {
  const TextoAyuda(this.titulo, this.cuerpo);

  /// `# Título` en la primera línea; el resto es el cuerpo. Sin título, queda vacío.
  factory TextoAyuda.parsear(String md) {
    final lineas = md.trim().split('\n');
    if (lineas.isNotEmpty && lineas.first.startsWith('# ')) {
      return TextoAyuda(lineas.first.substring(2).trim(), lineas.skip(1).join('\n').trim());
    }
    return TextoAyuda('', md.trim());
  }

  final String titulo;
  final String cuerpo;
}

/// Lee la ayuda de los assets de la app (`docs/ayuda/<clave>.<idioma>.md`), con el español
/// como respaldo.
Future<String?> cargarAyudaDeAssets(String clave, Locale idioma) async {
  for (final lang in {idioma.languageCode, 'es'}) {
    try {
      return await rootBundle.loadString('docs/ayuda/$clave.$lang.md');
    } on Object {
      continue;
    }
  }
  return null;
}

/// Entrega a los iconos de ayuda de abajo cómo cargar el texto.
class AyudaScope extends InheritedWidget {
  const AyudaScope({super.key, required this.cargar, required super.child});

  final CargarAyuda cargar;

  static CargarAyuda of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AyudaScope>()?.cargar ?? cargarAyudaDeAssets;

  @override
  bool updateShouldNotify(AyudaScope old) => cargar != old.cargar;
}

/// Icono de ayuda de un flujo no obvio (D30). Abre el texto de `clave`.
class AyudaIcono extends StatelessWidget {
  const AyudaIcono(this.clave, {super.key});

  final String clave;

  @override
  Widget build(BuildContext context) {
    final t = UiKitLocalizations.of(context);
    return IconButton(
      icon: const Icon(Icons.help_outline),
      tooltip: t.ayudaTooltip,
      onPressed: () => showDialog<void>(
        context: context,
        builder: (_) => _DialogoAyuda(clave: clave, cargar: AyudaScope.of(context)),
      ),
    );
  }
}

class _DialogoAyuda extends StatelessWidget {
  const _DialogoAyuda({required this.clave, required this.cargar});

  final String clave;
  final CargarAyuda cargar;

  @override
  Widget build(BuildContext context) {
    final t = UiKitLocalizations.of(context);
    return FutureBuilder<String?>(
      future: cargar(clave, Localizations.localeOf(context)),
      builder: (context, snap) {
        final texto = snap.data == null ? null : TextoAyuda.parsear(snap.data!);
        return AlertDialog(
          title: texto == null || texto.titulo.isEmpty ? null : Text(texto.titulo),
          content: SingleChildScrollView(
            child: Text(snap.connectionState != ConnectionState.done
                ? ''
                : (texto?.cuerpo ?? t.ayudaSinTexto)),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(t.cerrar)),
          ],
        );
      },
    );
  }
}
