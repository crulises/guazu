/// Escaneo y entrada de EAN. La cámara (`mobile_scanner`) llega en el corte 6.
library;

/// La app solo valida el formato: 8 a 14 dígitos. La normalización (UPC-A a EAN-13, dígito
/// verificador GS1) vive en un solo lugar: el backend (Doc 7, D47).
bool esEanPlausible(String entrada) => RegExp(r'^\d{8,14}$').hasMatch(entrada.trim());

/// Deja solo los dígitos (el lector y el teclado pueden traer espacios o guiones).
String soloDigitos(String entrada) => entrada.replaceAll(RegExp(r'\D'), '');
