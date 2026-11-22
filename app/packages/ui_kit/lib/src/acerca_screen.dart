import 'package:guazu_core/guazu_core.dart';
import 'package:material_ui/material_ui.dart';

import '../l10n/ui_kit_localizations.dart';

/// Una fuente de datos abiertos con lo que exige su licencia (Doc 7 §Atribuciones).
/// Los textos viven en los `.arb`; si cambia uno, se cambia en el Doc 7 y en los dos idiomas.
class FuenteDatos {
  const FuenteDatos({
    required this.nombre,
    required this.aporta,
    required this.licencia,
    required this.texto,
    required this.enlaces,
  });

  final String nombre;
  final String aporta;
  final String licencia;
  final String texto;
  final List<(String, String)> enlaces;
}

/// Las fuentes que la plataforma usa (OFF y SEPA). OpenStreetMap no aplica acá.
List<FuenteDatos> fuentesDatos(UiKitLocalizations t, String app) => [
  FuenteDatos(
    nombre: t.fuenteOffNombre,
    aporta: t.fuenteOffAporta,
    licencia: t.fuenteOffLicencia,
    texto: t.fuenteOffTexto(app),
    enlaces: [
      (t.enlaceOff, 'https://openfoodfacts.org'),
      (t.enlaceOdbl, 'https://opendatacommons.org/licenses/odbl/1-0/'),
      (t.enlaceDbcl, 'https://opendatacommons.org/licenses/dbcl/1-0/'),
      (t.enlaceCcBySa, 'https://creativecommons.org/licenses/by-sa/3.0/'),
      (t.enlaceTerminosOff, 'https://world.openfoodfacts.org/terms-of-use'),
    ],
  ),
  FuenteDatos(
    nombre: t.fuenteSepaNombre,
    aporta: t.fuenteSepaAporta,
    licencia: t.fuenteSepaLicencia,
    texto: t.fuenteSepaTexto(app),
    enlaces: [
      (t.enlaceSepa, 'https://datos.produccion.gob.ar/dataset/sepa-precios'),
      (t.enlaceCcBy, 'https://creativecommons.org/licenses/by/4.0/deed.es'),
    ],
  ),
];

/// «Acerca de»: qué app es, de dónde salen los datos y con qué licencia, y diagnóstico de la
/// conexión (versión, servidor, estado, versión del backend, IP) para no adivinar. Es accesible
/// aunque no haya conexión: la tarjeta de diagnóstico muestra el fallo en vez de romper.
class AcercaScreen extends StatefulWidget {
  const AcercaScreen({
    super.key,
    required this.nombreApp,
    required this.cargarInfo,
    required this.abrirEnlace,
    this.build = BuildInfo.actual,
  });

  /// Nombre de la app que se muestra (Guazú, Guazú Negocio…): viene de la app, no del kit.
  final String nombreApp;
  final Future<InfoApp> Function() cargarInfo;
  final Future<void> Function(Uri) abrirEnlace;
  final BuildInfo build;

  @override
  State<AcercaScreen> createState() => _AcercaScreenState();
}

class _AcercaScreenState extends State<AcercaScreen> {
  late final Future<InfoApp> _info = widget.cargarInfo();

  @override
  Widget build(BuildContext context) {
    final t = UiKitLocalizations.of(context);
    final tema = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(t.acercaTitulo)),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(widget.nombreApp, style: tema.headlineMedium),
          Text(t.acercaVersionDeApp(widget.build.version), style: tema.bodyMedium),
          const SizedBox(height: 16),
          _tarjetaDiagnostico(context, t),
          const SizedBox(height: 32),
          Text(t.acercaFuentesTitulo, style: tema.titleLarge),
          const SizedBox(height: 8),
          Text(t.acercaFuentesIntro(widget.nombreApp)),
          const SizedBox(height: 8),
          for (final f in fuentesDatos(t, widget.nombreApp)) _tarjetaFuente(context, t, f),
          const SizedBox(height: 8),
          Text(t.acercaPreciosAviso),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            icon: const Icon(Icons.description_outlined),
            label: Text(t.acercaLicenciasLibrerias),
            onPressed: () => showLicensePage(
              context: context,
              applicationName: widget.nombreApp,
              applicationVersion: widget.build.version,
            ),
          ),
        ],
      ),
    );
  }

  Widget _tarjetaDiagnostico(BuildContext context, UiKitLocalizations t) {
    final estilo = Theme.of(context).textTheme.bodySmall;
    return FutureBuilder<InfoApp>(
      future: _info,
      builder: (context, snap) {
        final info = snap.data;
        final filas = <(String, String)>[
          (t.acercaVersion, '${widget.build.version} (${widget.build.commit})'),
          if (widget.build.compilado.isNotEmpty) (t.acercaCompilada, widget.build.compilado),
          if (info != null) ...[
            (t.acercaServidor, info.apiUrl),
            (t.acercaEstado, _estado(t, info.servidor)),
            if (info.servidor case ServidorOk(:final salud))
              (t.acercaVersionBackend, '${salud.version} (${salud.commit})'),
            (
              t.acercaIpDispositivo,
              info.ips.isEmpty
                  ? t.acercaSinRed
                  : info.ips.map((i) => '${i.ip} (${i.interfaz})').join(', '),
            ),
          ] else
            (t.acercaEstado, t.acercaConsultando),
        ];
        return Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(t.acercaDiagnostico, style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                for (final (nombre, valor) in filas) Text('$nombre: $valor', style: estilo),
              ],
            ),
          ),
        );
      },
    );
  }

  String _estado(UiKitLocalizations t, EstadoServidor e) => switch (e) {
    ServidorOk(:final demora, :final salud) =>
      salud.base == 'ok'
          ? t.acercaEstadoOk(demora.inMilliseconds)
          : t.acercaEstadoBaseCaida,
    ServidorSinConexion(:final motivo) => t.acercaEstadoSinConexion(motivo),
    ServidorRechazo(:final error) =>
      error.mensaje == null
          ? t.acercaEstadoRechazoSinMensaje(error.status)
          : t.acercaEstadoRechazo(error.status, error.mensaje!),
  };

  Widget _tarjetaFuente(BuildContext context, UiKitLocalizations t, FuenteDatos f) {
    final tema = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(f.nombre, style: tema.titleMedium),
            const SizedBox(height: 4),
            Text(t.acercaAporta(f.aporta), style: tema.bodySmall),
            Text(t.acercaLicencia(f.licencia), style: tema.bodySmall),
            const SizedBox(height: 8),
            Text(f.texto),
            Wrap(
              spacing: 4,
              children: [
                for (final (texto, url) in f.enlaces)
                  TextButton(
                    onPressed: () => widget.abrirEnlace(Uri.parse(url)),
                    child: Text(texto),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
