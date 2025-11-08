#!/usr/bin/env python3
# captcha_api.py
"""API para captura y resolución de CAPTCHA"""

import io
import os
import base64
import requests
from PIL import Image
from config import ANTICAPTCHA_API_KEY, OUTPUT_DIR
from gui import CaptchaGUI


def capturar_captcha(driver, element, save_path):
    """
    Captura un elemento CAPTCHA como imagen
    
    Args:
        driver: WebDriver de Selenium
        element: Elemento web que contiene el CAPTCHA
        save_path: Ruta donde guardar la imagen
    
    Returns:
        str: Ruta del archivo guardado
    """
    png = element.screenshot_as_png
    image = Image.open(io.BytesIO(png))
    image.save(save_path)
    return save_path


def resolver_captcha_automatico(captcha_path):
    """
    Intenta resolver el CAPTCHA usando Anti-Captcha API directamente
    
    Args:
        captcha_path: Ruta de la imagen del CAPTCHA
    
    Returns:
        str or None: Texto del CAPTCHA resuelto o None si falla
    """
    try:
        # Leer imagen y convertir a base64
        with open(captcha_path, 'rb') as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Crear tarea en Anti-Captcha
        create_task_url = "https://api.anti-captcha.com/createTask"
        
        task_data = {
            "clientKey": ANTICAPTCHA_API_KEY,
            "task": {
                "type": "ImageToTextTask",
                "body": image_base64,
                "phrase": False,
                "case": False,
                "numeric": 1,  # Solo números
                "math": False,
                "minLength": 0,
                "maxLength": 0
            }
        }
        
        # Enviar solicitud
        print("[+] Enviando CAPTCHA a Anti-Captcha API...")
        response = requests.post(create_task_url, json=task_data, timeout=30)
        result = response.json()
        
        if result.get("errorId") != 0:
            print(f"[!] Error al crear tarea: {result.get('errorDescription')}")
            return None
        
        task_id = result.get("taskId")
        print(f"[+] Tarea creada con ID: {task_id}")
        
        # Esperar resultado
        get_result_url = "https://api.anti-captcha.com/getTaskResult"
        
        import time
        for i in range(30):  # Intentar por 30 segundos
            time.sleep(2)
            
            result_data = {
                "clientKey": ANTICAPTCHA_API_KEY,
                "taskId": task_id
            }
            
            response = requests.post(get_result_url, json=result_data, timeout=10)
            result = response.json()
            
            if result.get("status") == "ready":
                captcha_text = result.get("solution", {}).get("text")
                if captcha_text:
                    print(f"[+] ✓ CAPTCHA resuelto automáticamente: {captcha_text}")
                    return captcha_text
            
            print(f"[*] Esperando resultado... ({i+1}/30)")
        
        print("[!] Timeout esperando resultado del CAPTCHA")
        return None
            
    except Exception as e:
        print(f"[!] Excepción al usar Anti-Captcha: {e}")
        return None


def resolver_captcha_manual(captcha_path):
    """
    Muestra GUI para que el humano resuelva el CAPTCHA
    
    Args:
        captcha_path: Ruta de la imagen del CAPTCHA
    
    Returns:
        str or None: Texto del CAPTCHA ingresado o None si se cancela
    """
    captcha_value_container = {"value": None}
    
    def on_submit(val):
        captcha_value_container["value"] = val

    gui = CaptchaGUI(captcha_path, on_submit)
    gui.show()
    
    return captcha_value_container["value"]


def resolver_captcha(driver, captcha_element_id="Capcha_CaptchaImageUP"):
    """
    Resuelve el CAPTCHA (automático o manual)
    
    Args:
        driver: WebDriver de Selenium
        captcha_element_id: ID del elemento CAPTCHA
    
    Returns:
        str or None: Texto del CAPTCHA resuelto o None si se cancela
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    wait = WebDriverWait(driver, 15)
    
    # Capturar imagen del CAPTCHA
    captcha_img = wait.until(EC.presence_of_element_located((By.ID, captcha_element_id)))
    captcha_path = os.path.join(OUTPUT_DIR, "captcha_temp.png")
    capturar_captcha(driver, captcha_img, captcha_path)
    print(f"[+] CAPTCHA guardado en: {captcha_path}")
    
    # Intentar resolver automáticamente
    captcha_value = resolver_captcha_automatico(captcha_path)
    
    # Si falla, resolver manualmente
    if not captcha_value:
        print("[!] Resolución automática falló. Mostrando GUI...")
        captcha_value = resolver_captcha_manual(captcha_path)
    
    if captcha_value is None:
        print("[!] Operador canceló la resolución del CAPTCHA.")
    
    return captcha_value


def encontrar_input_captcha(driver):
    """
    Encuentra el campo de entrada del CAPTCHA
    
    Args:
        driver: WebDriver de Selenium
    
    Returns:
        WebElement or None: Elemento del input o None si no se encuentra
    """
    from selenium.webdriver.common.by import By
    
    try:
        return driver.find_element(By.ID, "Capcha_CaptchaTextBox")
    except:
        # Fallback: buscar primer input visible que no sea txtNumDoc
        inputs = driver.find_elements(
            By.XPATH, 
            "//input[@type='text' or @type='tel' or @type='number']"
        )
        for inp in inputs:
            if inp.get_attribute("id") != "txtNumDoc" and inp.is_displayed():
                return inp
    return None