import 'package:flutter_test/flutter_test.dart';
import 'package:guazu_scanner/guazu_scanner.dart';

void main() {
  test('acepta de 8 a 14 dígitos', () {
    for (final n in ['12345678', '036000291452', '7790070410021', '07790070410021']) {
      expect(esEanPlausible(n), isTrue, reason: n);
    }
  });

  test('rechaza lo que no es un EAN', () {
    for (final n in ['', '1234567', '123456789012345', '77900704100a1', '7790 0704']) {
      expect(esEanPlausible(n), isFalse, reason: n);
    }
  });

  test('soloDigitos limpia espacios y guiones', () {
    expect(soloDigitos(' 779-0070 410021 '), '7790070410021');
  });
}
