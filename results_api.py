#!/usr/bin/env python3
# results_api.py (OPTIMIZADO)
"""API para captura y almacenamiento de resultados - VERSION OPTIMIZADA"""

import os
import time
import json
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import OUTPUT_DIR
from browser_api import cambiar_a_nueva_ventana, buscar_iframe_con_contenido


def capturar_resultados(driver, ventanas_anteriores, timeout=15):
    """
    Captura los resultados después de enviar el formulario (OPTIMIZADO)
    
    Args:
        driver: WebDriver de Selenium
        ventanas_anteriores: Lista de handles de ventanas antes del envío
        timeout: Tiempo máximo de espera (reducido a 15s)
    
    Returns:
        str: Texto del resultado capturado
    """
    # Esperar nueva ventana o iframe
    nueva_ventana = cambiar_a_nueva_ventana(driver, ventanas_anteriores, timeout)
    
    if not nueva_ventana:
        # Intentar detectar iframe con contenido
        buscar_iframe_con_contenido(driver)
    
    # OPTIMIZACIÓN: Reducir espera y usar WebDriverWait para elementos específicos
    try:
        # Esperar a que aparezca algún elemento clave de los resultados
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        # Pequeña espera adicional para asegurar que todo cargó
        time.sleep(1)
    except:
        # Si no se encuentra tabla, esperar un poco más
        time.sleep(2)
    
    # Extraer HTML completo
    try:
        page_source = driver.page_source
        return page_source
    except Exception as e:
        print(f"[!] Error capturando page_source: {e}")
        # Fallback: intentar obtener el body
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            return body_text
        except:
            return None


def parsear_html_a_json(html_content):
    """
    Parsea el HTML de resultados y extrae información estructurada
    
    Args:
        html_content: Contenido HTML de la página de resultados
    
    Returns:
        dict: Diccionario con información estructurada
    """
    resultado = {
        "exito": False,
        "informacion_basica": {},
        "datos_afiliacion": [],
        "metadatos": {}
    }
    
    try:
        # Extraer información básica
        tipo_id_match = re.search(r'TIPO DE IDENTIFICACIÓN</td><td>([^<]+)</td>', html_content)
        numero_id_match = re.search(r'NÚMERO DE IDENTIFICACION</td><td>([^<]+)</td>', html_content)
        nombres_match = re.search(r'NOMBRES</td><td>([^<]+)</td>', html_content)
        apellidos_match = re.search(r'APELLIDOS</td><td>([^<]+)</td>', html_content)
        fecha_nac_match = re.search(r'FECHA DE NACIMIENTO</td><td>([^<]+)</td>', html_content)
        departamento_match = re.search(r'DEPARTAMENTO</td><td>([^<]+)</td>', html_content)
        municipio_match = re.search(r'MUNICIPIO</td><td>([^<]+)</td>', html_content)
        
        if tipo_id_match and numero_id_match:
            resultado["exito"] = True
            resultado["informacion_basica"] = {
                "tipo_identificacion": tipo_id_match.group(1).strip(),
                "numero_identificacion": numero_id_match.group(1).strip(),
                "nombres": nombres_match.group(1).strip() if nombres_match else "",
                "apellidos": apellidos_match.group(1).strip() if apellidos_match else "",
                "fecha_nacimiento": fecha_nac_match.group(1).strip() if fecha_nac_match else "",
                "departamento": departamento_match.group(1).strip() if departamento_match else "",
                "municipio": municipio_match.group(1).strip() if municipio_match else ""
            }
        
        # Extraer datos de afiliación
        afiliacion_pattern = r'<tr class="DataGrid_(?:Item|AlternatingItem)" align="center">\s*<td>([^<]+)</td><td>([^<]+)</td><td>([^<]+)</td><td>([^<]+)</td><td>([^<]+)</td><td>([^<]+)</td>'
        afiliaciones = re.finditer(afiliacion_pattern, html_content)
        
        for match in afiliaciones:
            afiliacion = {
                "estado": match.group(1).strip(),
                "entidad": match.group(2).strip(),
                "regimen": match.group(3).strip(),
                "fecha_afiliacion": match.group(4).strip(),
                "fecha_finalizacion": match.group(5).strip(),
                "tipo_afiliado": match.group(6).strip()
            }
            resultado["datos_afiliacion"].append(afiliacion)
        
        # Extraer metadatos
        fecha_impresion_match = re.search(r'Fecha de Impresión:.*?<span[^>]*>([^<]+)</span>', html_content)
        estacion_match = re.search(r'Estación de origen:.*?<span[^>]*>([^<]+)</span>', html_content)
        
        resultado["metadatos"] = {
            "fecha_consulta": fecha_impresion_match.group(1).strip() if fecha_impresion_match else "",
            "estacion": estacion_match.group(1).strip() if estacion_match else ""
        }
        
    except Exception as e:
        print(f"[!] Error parseando HTML: {e}")
        resultado["error"] = str(e)
    
    return resultado


def guardar_resultados(nombre_archivo, contenido_resultado, driver, output_dir=OUTPUT_DIR):
    """
    Guarda los resultados en archivos (HTML, TXT, JSON, PNG)
    
    Args:
        nombre_archivo: Nombre base para los archivos (ej: "CC_1234567890")
        contenido_resultado: Contenido HTML/texto del resultado
        driver: WebDriver para capturar screenshot
        output_dir: Directorio donde guardar los archivos
    
    Returns:
        tuple: (dict de archivos, dict de datos JSON)
    """
    archivos = {}
    
    # Guardar HTML completo
    html_path = os.path.join(output_dir, f"resultado_{nombre_archivo}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(contenido_resultado)
    archivos["html"] = html_path
    print(f"[+] HTML guardado en: {html_path}")
    
    # Parsear y guardar JSON
    datos_json = parsear_html_a_json(contenido_resultado)
    json_path = os.path.join(output_dir, f"resultado_{nombre_archivo}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(datos_json, f, indent=2, ensure_ascii=False)
    archivos["json"] = json_path
    print(f"[+] JSON guardado en: {json_path}")
    
    # Guardar texto plano
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        txt_path = os.path.join(output_dir, f"resultado_{nombre_archivo}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(body_text)
        archivos["txt"] = txt_path
        print(f"[+] TXT guardado en: {txt_path}")
    except:
        pass

    # Guardar screenshot
    screenshot_path = os.path.join(output_dir, f"resultado_{nombre_archivo}.png")
    driver.save_screenshot(screenshot_path)
    archivos["screenshot"] = screenshot_path
    print(f"[+] Screenshot guardado en: {screenshot_path}")
    
    return archivos, datos_json


def imprimir_resultado_consola(datos_json):
    """
    Imprime el resultado en formato legible en consola
    
    Args:
        datos_json: Diccionario con datos parseados
    """
    if not datos_json.get("exito"):
        print("\n❌ No se pudo extraer información del resultado")
        return
    
    print("\n" + "="*60)
    print("📋 INFORMACIÓN BÁSICA")
    print("="*60)
    
    basica = datos_json.get("informacion_basica", {})
    print(f"Tipo ID:       {basica.get('tipo_identificacion', 'N/A')}")
    print(f"Número ID:     {basica.get('numero_identificacion', 'N/A')}")
    print(f"Nombres:       {basica.get('nombres', 'N/A')}")
    print(f"Apellidos:     {basica.get('apellidos', 'N/A')}")
    print(f"F. Nacimiento: {basica.get('fecha_nacimiento', 'N/A')}")
    print(f"Departamento:  {basica.get('departamento', 'N/A')}")
    print(f"Municipio:     {basica.get('municipio', 'N/A')}")
    
    print("\n" + "="*60)
    print("🏥 DATOS DE AFILIACIÓN")
    print("="*60)
    
    for idx, afiliacion in enumerate(datos_json.get("datos_afiliacion", []), 1):
        print(f"\n➤ Afiliación #{idx}")
        print(f"  Estado:           {afiliacion.get('estado', 'N/A')}")
        print(f"  Entidad:          {afiliacion.get('entidad', 'N/A')}")
        print(f"  Régimen:          {afiliacion.get('regimen', 'N/A')}")
        print(f"  Fecha Afiliación: {afiliacion.get('fecha_afiliacion', 'N/A')}")
        print(f"  Fecha Fin:        {afiliacion.get('fecha_finalizacion', 'N/A')}")
        print(f"  Tipo Afiliado:    {afiliacion.get('tipo_afiliado', 'N/A')}")
    
    metadatos = datos_json.get("metadatos", {})
    if metadatos.get("fecha_consulta"):
        print("\n" + "-"*60)
        print(f"📅 Fecha consulta: {metadatos.get('fecha_consulta')}")
        print(f"💻 Estación:       {metadatos.get('estacion')}")
    
    print("="*60 + "\n")