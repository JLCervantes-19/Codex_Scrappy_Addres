#!/usr/bin/env python3
# browser_api.py
"""API para manejo del navegador Selenium"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def iniciar_navegador(headless=False):
    """
    Inicia una instancia de Chrome con Selenium
    
    Args:
        headless: Si True, ejecuta el navegador sin interfaz gráfica
    
    Returns:
        WebDriver: Instancia del navegador Chrome
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    
    if headless:
        options.add_argument("--headless")
    
    # Reducir detección de automatización
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    return driver


def cerrar_navegador(driver, delay=8):
    """
    Cierra el navegador después de un delay
    
    Args:
        driver: Instancia del WebDriver
        delay: Segundos a esperar antes de cerrar
    """
    if driver:
        print(f"Cerrando navegador en {delay} segundos...")
        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            pass
        try:
            driver.quit()
        except:
            pass


def guardar_debug(driver, prefix, debug_folder):
    """
    Guarda screenshot y código fuente para depuración
    
    Args:
        driver: Instancia del WebDriver
        prefix: Prefijo para el nombre de archivo
        debug_folder: Carpeta donde guardar los archivos
    
    Returns:
        tuple: (ruta_screenshot, ruta_html)
    """
    import os
    
    timestamp = int(time.time())
    screenshot_path = os.path.join(debug_folder, f"{prefix}_{timestamp}.png")
    html_path = os.path.join(debug_folder, f"{prefix}_{timestamp}.html")
    
    driver.save_screenshot(screenshot_path)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    return screenshot_path, html_path


def cambiar_a_nueva_ventana(driver, ventanas_anteriores, timeout=20):
    """
    Detecta y cambia a una nueva ventana del navegador
    
    Args:
        driver: Instancia del WebDriver
        ventanas_anteriores: Lista de handles de ventanas antes de la acción
        timeout: Segundos máximos a esperar
    
    Returns:
        bool: True si se encontró una nueva ventana, False si no
    """
    waited = 0
    while waited < timeout:
        time.sleep(1)
        waited += 1
        try:
            if len(driver.window_handles) > len(ventanas_anteriores):
                # Cambiar a la nueva ventana
                for h in driver.window_handles:
                    if h not in ventanas_anteriores:
                        driver.switch_to.window(h)
                        print(f"[+] Cambiado a nueva ventana después de {waited} segundos")
                        return True
        except Exception as e:
            print(f"[!] Error al verificar ventanas: {e}")
            continue
    return False


def buscar_iframe_con_contenido(driver, min_text_length=20):
    """
    Busca y cambia a un iframe que tenga contenido
    
    Args:
        driver: Instancia del WebDriver
        min_text_length: Longitud mínima de texto para considerar contenido válido
    
    Returns:
        bool: True si se encontró iframe con contenido, False si no
    """
    from selenium.webdriver.common.by import By
    
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for fr in iframes:
            driver.switch_to.frame(fr)
            body = driver.find_element(By.TAG_NAME, "body")
            if len(body.text.strip()) > min_text_length:
                return True
            driver.switch_to.default_content()
    except Exception:
        pass
    return False