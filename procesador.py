import sys
from typing import Dict, Final

# Tabla de traducción optimizada para normalizar caracteres acentuados y diéresis
ACCENT_TRANS_TABLE: Final[Dict[int, int]] = str.maketrans("áéíóúü", "aeiouu")
VOWELS: Final[tuple[str, ...]] = ("a", "e", "i", "o", "u")


def contar_vocales(texto: str) -> Dict[str, int]:
    """Cuenta la cantidad de vocales (incluyendo acentuadas y diéresis) en un texto.

    Utiliza operaciones nativas en C (str.translate y str.count) para maximizar
    el rendimiento.

    Args:
        texto (str): La cadena de texto a analizar.

    Returns:
        Dict[str, int]: Diccionario con el conteo individual por vocal y el total.

    Raises:
        TypeError: Si el parámetro proporcionado no es una cadena de texto.
        RuntimeError: Si ocurre un error inesperado al procesar la cadena.
    """
    if not isinstance(texto, str):
        raise TypeError("El argumento proporcionado debe ser de tipo 'str'.")

    try:
        # Paso 1: Normalización en C (minúsculas + reemplazo de tildes)
        texto_limpio: str = texto.lower().translate(ACCENT_TRANS_TABLE)

        # Paso 2: Conteo optimizado usando métodos C subyacentes
        conteo: Dict[str, int] = {vocal: texto_limpio.count(vocal) for vocal in VOWELS}
        conteo["total"] = sum(conteo.values())

        return conteo

    except Exception as e:
        raise RuntimeError(f"Error inesperado al procesar el texto: {e}") from e


if __name__ == "__main__":
    try:
        print("=== PRUEBAS DE CONTEO DE VOCALES (REFACTORIZADO) ===\n")

        # Prueba 1: Texto simple
        texto1: str = "Hola Mundo desde Python"
        resultado1: Dict[str, int] = contar_vocales(texto1)
        print(f"Texto: '{texto1}'")
        print(f"Resultado: {resultado1}\n")

        # Prueba 2: Texto con acentos, diéresis y mayúsculas
        texto2: str = "¡El Murciélago y el Pingüino comen más Ámbar!"
        resultado2: Dict[str, int] = contar_vocales(texto2)
        print(f"Texto: '{texto2}'")
        print(f"Resultado: {resultado2}\n")

        # Prueba 3: Texto sin vocales
        texto3: str = "1234567890!@#$%^&*()"
        resultado3: Dict[str, int] = contar_vocales(texto3)
        print(f"Texto: '{texto3}'")
        print(f"Resultado: {resultado3}\n")

        # Prueba 4: Captura de excepción controlada (tipo de dato inválido)
        print("Probando manejo de errores con un tipo de dato incorrecto...")
        try:
            contar_vocales(12345)  # type: ignore
        except TypeError as e:
            print(f"Excepción capturada correctamente: {e}\n")

    except Exception as e:
        print(f"Error crítico durante la ejecución: {e}", file=sys.stderr)