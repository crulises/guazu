import 'package:flutter_test/flutter_test.dart';
import 'package:guazu_core/guazu_core.dart';
import 'package:material_ui/material_ui.dart';
import 'package:negocio/app.dart';

Future<InfoApp> _info() async => InfoApp(
  build: BuildInfo.actual,
  apiUrl: 'http://x:8100',
  servidor: const ServidorSinConexion('prueba'),
  ips: const [],
);

Widget _app() => GuazuNegocioApp(
  api: ApiClient(baseUrl: 'http://x:8100'),
  cargarInfo: _info,
  abrirEnlace: (_) async {},
);

void main() {
  // Los tests corren en español; el idioma real lo da el dispositivo (es de respaldo).
  setUp(() {
    TestWidgetsFlutterBinding.ensureInitialized();
    TestWidgetsFlutterBinding.instance.platformDispatcher.localesTestValue = const [Locale('es')];
  });
  tearDown(() => TestWidgetsFlutterBinding.instance.platformDispatcher.clearLocalesTestValue());

  testWidgets('inicio con el nombre de la app, ayuda e info', (tester) async {
    await tester.pumpWidget(_app());
    await tester.pumpAndSettle();
    expect(find.text('Guazú Negocio'), findsOneWidget);
    expect(find.byIcon(Icons.help_outline), findsOneWidget);
    expect(find.byIcon(Icons.info_outline), findsOneWidget);
  });

  testWidgets('la ayuda sale del asset docs/ayuda/inicio.es.md', (tester) async {
    await tester.pumpWidget(_app());
    await tester.tap(find.byIcon(Icons.help_outline));
    await tester.pumpAndSettle();
    expect(find.text('Inicio'), findsOneWidget);
    expect(find.textContaining('Acerca de'), findsWidgets);
  });

  testWidgets('«Acerca de» abre sin conexión y muestra las fuentes de datos', (tester) async {
    await tester.pumpWidget(_app());
    await tester.tap(find.byIcon(Icons.info_outline));
    await tester.pumpAndSettle();
    expect(find.text('Estado: sin conexión (prueba)'), findsOneWidget);
    expect(find.text('Fuentes de datos'), findsOneWidget);
  });
}
