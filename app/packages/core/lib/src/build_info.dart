/// Datos de la compilación, fijados por `make apk-*` con `--dart-define`.
class BuildInfo {
  const BuildInfo({
    required this.version,
    required this.commit,
    required this.compilado,
  });

  final String version;
  final String commit;

  /// Hora de compilación en ISO 8601 (sin zona), o vacío si no se informó.
  final String compilado;

  static const actual = BuildInfo(
    version: String.fromEnvironment('APP_VERSION', defaultValue: '0.0.0-dev'),
    commit: String.fromEnvironment('APP_COMMIT', defaultValue: 'local'),
    compilado: String.fromEnvironment('APP_BUILT_AT'),
  );
}
