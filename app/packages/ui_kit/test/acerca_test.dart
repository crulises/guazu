import 'package:flutter_test/flutter_test.dart';
import 'package:guazu_core/guazu_core.dart';
import 'package:guazu_ui_kit/guazu_ui_kit.dart';
import 'package:material_ui/material_ui.dart';

Widget _app(Widget home, {Locale locale = const Locale('es')}) => MaterialApp(
  locale: locale,
  localizationsDelegates: [
    UiKitLocalizations.delegate,
    ...GlobalMaterialLocalizations.delegates,
  ],
  supportedLocales: UiKitLocalizations.supportedLocales,
  home: home,
);

Future<InfoApp> _info(EstadoServidor e) async => InfoApp(
  build: BuildInfo.actual,
  apiUrl: 'http://x:8100',
  servidor: e,
  ips: const [IpInterfaz('192.168.1.5', 'en0')],
);

AcercaScreen _pantalla(Future<InfoApp> Function() carga, [void Function(Uri)? abrir]) =>
    AcercaScreen(
      nombreApp: 'Guazú',
      build: const BuildInfo(version: '0.0.7', commit: 'abc123', compilado: '2026-11-22T10:00'),
      cargarInfo: carga,
      abrirEnlace: (u) async => abrir?.call(u),
    );

/// La lista es perezosa: en el test hay que agrandar la pantalla para que construya todo.
void _pantallaGrande(WidgetTester tester) {
  tester.view.physicalSize = const Size(900, 4000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  testWidgets('muestra versión de la app y del backend, servidor e IP', (tester) async {
    await tester.pumpWidget(_app(_pantalla(() => _info(ServidorOk(
      const Duration(milliseconds: 42),
      const SaludBackend(
        estado: 'ok', base: 'ok', version: '0.0.3', commit: 'def456', compilado: '',
      ),
    )))));
    await tester.pumpAndSettle();
    expect(find.text('Versión: 0.0.7 (abc123)'), findsOneWidget);
    expect(find.text('Servidor: http://x:8100'), findsOneWidget);
    expect(find.text('Estado: conectado (42 ms)'), findsOneWidget);
    expect(find.text('Versión del servidor: 0.0.3 (def456)'), findsOneWidget);
    expect(find.text('IP del dispositivo: 192.168.1.5 (en0)'), findsOneWidget);
  });

  testWidgets('sin conexión sigue accesible y lo dice', (tester) async {
    _pantallaGrande(tester);
    await tester.pumpWidget(_app(_pantalla(() => _info(const ServidorSinConexion('timeout')))));
    await tester.pumpAndSettle();
    expect(find.text('Estado: sin conexión (timeout)'), findsOneWidget);
    expect(find.text('Fuentes de datos'), findsOneWidget);
  });

  testWidgets('un 403 no se confunde con «sin red»', (tester) async {
    await tester.pumpWidget(_app(_pantalla(() => _info(
      ServidorRechazo(ApiException(403, mensaje: 'Acceso restringido')),
    ))));
    await tester.pumpAndSettle();
    expect(find.text('Estado: El servidor respondió 403 (Acceso restringido)'), findsOneWidget);
  });

  testWidgets('nombra a Open Food Facts y a SEPA con su licencia', (tester) async {
    _pantallaGrande(tester);
    await tester.pumpWidget(_app(_pantalla(() => _info(const ServidorSinConexion('x')))));
    await tester.pumpAndSettle();
    expect(find.textContaining('Open Database License (ODbL) 1.0'), findsOneWidget);
    expect(find.textContaining('CC BY-SA'), findsWidgets);
    expect(find.textContaining('Secretaría de Comercio de la Nación'), findsOneWidget);
    expect(find.textContaining('normalizados y combinados por Guazú'), findsOneWidget);
    expect(find.textContaining('solo las enlaza'), findsOneWidget);
  });

  testWidgets('los enlaces se abren con el callback de la app', (tester) async {
    _pantallaGrande(tester);
    final abiertos = <Uri>[];
    await tester.pumpWidget(
      _app(_pantalla(() => _info(const ServidorSinConexion('x')), abiertos.add)),
    );
    await tester.pumpAndSettle();
    final enlace = find.text('ODbL 1.0');
    await tester.ensureVisible(enlace);
    await tester.tap(enlace);
    expect(abiertos.single.toString(), 'https://opendatacommons.org/licenses/odbl/1-0/');
  });

  testWidgets('en inglés también', (tester) async {
    await tester.pumpWidget(_app(
      _pantalla(() => _info(const ServidorSinConexion('x'))),
      locale: const Locale('en'),
    ));
    await tester.pumpAndSettle();
    expect(find.text('Data sources'), findsOneWidget);
  });

  testWidgets('AyudaIcono abre el texto de la clave (título y cuerpo)', (tester) async {
    await tester.pumpWidget(_app(
      AyudaScope(
        cargar: (clave, idioma) async => '# Inicio\nAcá se explica $clave.',
        child: const Scaffold(body: AyudaIcono('inicio')),
      ),
    ));
    await tester.tap(find.byType(IconButton));
    await tester.pumpAndSettle();
    expect(find.text('Inicio'), findsOneWidget);
    expect(find.text('Acá se explica inicio.'), findsOneWidget);
  });

  testWidgets('AyudaIcono sin texto avisa que no hay ayuda', (tester) async {
    await tester.pumpWidget(_app(
      AyudaScope(
        cargar: (clave, idioma) async => null,
        child: const Scaffold(body: AyudaIcono('x')),
      ),
    ));
    await tester.tap(find.byType(IconButton));
    await tester.pumpAndSettle();
    expect(find.text('Todavía no hay ayuda escrita para esta pantalla.'), findsOneWidget);
  });

  test('TextoAyuda separa título y cuerpo', () {
    final t = TextoAyuda.parsear('# Hola\n\nCuerpo');
    expect((t.titulo, t.cuerpo), ('Hola', 'Cuerpo'));
    expect(TextoAyuda.parsear('solo cuerpo').titulo, '');
  });

}
