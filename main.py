#!/usr/bin/env python3
# main.py
"""Script principal para consulta ADRES con resolución de CAPTCHA"""

import time
from config import URL, DEFAULT_CEDULA, OUTPUT_DIR, DEBUG_DIR
from browser_api import iniciar_navegador, cerrar_navegador, guardar_debug
from form_api import escribir_en_campo, enviar_formulario
from captcha_api import resolver_captcha, encontrar_input_captcha
from results_api import capturar_resultados, guardar_resultados, imprimir_resultado_consola


def ejecutar_consulta_adres(cedula):
    """
    Ejecuta la consulta completa en ADRES
    
    Args:
        cedula: Número de cédula a consultar
    
    Returns:
        dict or None: Diccionario con datos parseados o None si falla
    """
    driver = None
    try:
        # 1. Iniciar navegador
        print("[1/6] Iniciando navegador...")
        driver = iniciar_navegador(headless=False)
        driver.get(URL)
        time.sleep(2)

        # 2. Escribir cédula
        print("[2/6] Escribiendo cédula en el formulario...")
        escribir_en_campo(driver, cedula)

        # 3. Resolver CAPTCHA
        print("[3/6] Resolviendo CAPTCHA...")
        captcha_value = resolver_captcha(driver)
        
        if captcha_value is None:
            print("[!] CAPTCHA cancelado por el operador. Abortando.")
            return None

        # 4. Ingresar CAPTCHA
        print("[4/6] Ingresando valor del CAPTCHA...")
        captcha_input = encontrar_input_captcha(driver)
        
        if captcha_input is None:
            screenshot, html = guardar_debug(driver, "no_captcha_input", DEBUG_DIR)
            raise RuntimeError(f"No se encontró el input del CAPTCHA. Captura: {screenshot}")

        try:
            captcha_input.clear()
        except:
            pass
        captcha_input.send_keys(captcha_value)
        time.sleep(0.2)

        # 5. Enviar formulario
        print("[5/6] Enviando formulario...")
        ventanas_antes = enviar_formulario(driver)

        # 6. Capturar resultados
        print("[6/6] Capturando resultados...")
        time.sleep(3)  # Esperar a que cargue la nueva ventana
        
        contenido_resultado = capturar_resultados(driver, ventanas_antes, timeout=20)
        
        if not contenido_resultado:
            raise RuntimeError("No se pudo capturar el contenido de los resultados")
        
        # Guardar resultados en múltiples formatos
        archivos, datos_json = guardar_resultados(cedula, contenido_resultado, driver)
        
        # Mostrar resultado en consola
        imprimir_resultado_consola(datos_json)
        
        print("\n✓ Consulta completada exitosamente")
        print(f"✓ Archivos generados:")
        for tipo, ruta in archivos.items():
            print(f"  - {tipo.upper()}: {ruta}")
        
        return datos_json

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        
        # Guardar información de debug
        try:
            screenshot, html = guardar_debug(driver, "error", DEBUG_DIR)
            print(f"[i] Capturas de debug guardadas: {screenshot}, {html}")
        except:
            pass
        
        return None
    
    finally:
        # Cerrar navegador
        if driver:
            cerrar_navegador(driver, delay=5)  # Reducido a 5 segundos


def validar_cedula(cedula):
    """
    Valida que la cédula sea un número válido
    
    Args:
        cedula: Número de cédula a validar
    
    Returns:
        bool: True si es válida, False si no
    """
    return cedula and cedula.strip().isdigit()


def main():
    """Función principal"""
    print("=" * 60)
    print("CONSULTA EPS - ADRES (human-in-the-loop)")
    print("=" * 60)
    print()
    
    # Solicitar cédula
    cedula = input(
        f"Ingresa número de cédula (Enter para usar ejemplo 1006881471): "
    ).strip()
    
    if not cedula:
        cedula = "1006881471"
        print(f"Usando cédula de ejemplo: {cedula}")
    
    # Validar cédula
    if not validar_cedula(cedula):
        print("✗ La cédula debe contener solo números. Abortando.")
        return

    print()
    # Ejecutar consulta
    resultado = ejecutar_consulta_adres(cedula)
    
    # Mostrar resultado final
    print()
    print("=" * 60)
    if resultado and resultado.get("exito"):
        print(f"✓ Consulta completada exitosamente")
        print(f"  Revisa la carpeta '{OUTPUT_DIR}' para ver los resultados.")
        print(f"  📄 JSON disponible: resultado_{cedula}.json")
    else:
        print(f"✗ La consulta no pudo completarse")
        print(f"  Revisa la carpeta '{DEBUG_DIR}' para más información.")
    print("=" * 60)


if __name__ == "__main__":
    main()