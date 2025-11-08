#!/usr/bin/env python3
# form_api.py
"""API para interacción con formularios web"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    StaleElementReferenceException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    NoSuchFrameException,
)
from selenium.webdriver import ActionChains
from config import DEBUG_DIR
from browser_api import guardar_debug


def _buscar_elemento_en_contexto(
    driver,
    locators,
    timeout,
    max_profundidad=6,
    _profundidad=0,
    _visitados=None,
):
    """Busca un elemento manejando iframes y tiempos de carga variables."""

    if _visitados is None:
        _visitados = set()

    if _profundidad == 0:
        limite = time.time() + timeout
        ultimo_error = None
        while time.time() < limite:
            driver.switch_to.default_content()
            try:
                elemento = _buscar_elemento_en_contexto(
                    driver,
                    locators,
                    timeout=0,
                    max_profundidad=max_profundidad,
                    _profundidad=1,
                    _visitados=set(),
                )
                if elemento:
                    try:
                        if elemento.is_displayed() and elemento.is_enabled():
                            return elemento
                    except StaleElementReferenceException as exc:
                        ultimo_error = exc
                else:
                    ultimo_error = None
            except Exception as exc:  # pylint: disable=broad-except
                ultimo_error = exc
            time.sleep(0.5)

        if ultimo_error:
            raise ultimo_error
        return None

    # En niveles recursivos no necesitamos bucle de tiempo porque el nivel 0 ya lo maneja
    for locator in locators:
        try:
            elementos = driver.find_elements(*locator)
        except Exception:  # pylint: disable=broad-except
            elementos = []

        for elemento in elementos:
            try:
                if elemento.is_displayed() and elemento.is_enabled():
                    return elemento
            except StaleElementReferenceException:
                continue

    if _profundidad >= max_profundidad:
        return None

    try:
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
    except Exception:  # pylint: disable=broad-except
        iframes = []

    for indice, iframe in enumerate(iframes):
        try:
            clave = (
                _profundidad,
                iframe.id,
                iframe.get_attribute("id"),
                iframe.get_attribute("name"),
                indice,
            )
        except StaleElementReferenceException:
            continue

        if clave in _visitados:
            continue
        _visitados.add(clave)

        try:
            driver.switch_to.frame(iframe)
        except (NoSuchFrameException, StaleElementReferenceException, ElementClickInterceptedException):
            continue
        except Exception:
            # Algunos iframes externos (como reCAPTCHA) pueden bloquear el acceso
            try:
                driver.switch_to.default_content()
            except Exception:  # pylint: disable=broad-except
                pass
            continue

        encontrado = _buscar_elemento_en_contexto(
            driver,
            locators,
            timeout=0,
            max_profundidad=max_profundidad,
            _profundidad=_profundidad + 1,
            _visitados=_visitados,
        )
        if encontrado:
            return encontrado

        try:
            driver.switch_to.parent_frame()
        except Exception:  # pylint: disable=broad-except
            driver.switch_to.default_content()

    return None


def verificar_iframe_con_elemento(driver, element_id="txtNumDoc"):
    """
    Verifica si un elemento está dentro de un iframe y cambia a él
    
    Args:
        driver: WebDriver de Selenium
        element_id: ID del elemento a buscar
    
    Returns:
        bool: True si el elemento está en un iframe y se cambió a él
    """
    driver.switch_to.default_content()

    element = _buscar_elemento_en_contexto(
        driver,
        [(By.ID, element_id)],
        timeout=5,
    )

    if element:
        return True

    driver.switch_to.default_content()
    return False


def encontrar_elemento_con_localizadores(driver, locators, timeout=30, buscar_en_iframes=True):
    """
    Intenta encontrar un elemento usando múltiples localizadores
    
    Args:
        driver: WebDriver de Selenium
        locators: Lista de tuplas (By, valor)
        timeout: Tiempo máximo de espera
    
    Returns:
        WebElement or None: Elemento encontrado o None
    """
    driver.switch_to.default_content()

    elemento = _buscar_elemento_en_contexto(
        driver,
        locators,
        timeout=timeout,
        max_profundidad=6 if buscar_en_iframes else 1,
    )

    if elemento:
        return elemento

    driver.switch_to.default_content()
    return None


def seleccionar_tipo_documento(driver, tipo_documento="CC"):
    """
    Selecciona el tipo de documento en el dropdown del formulario
    
    Args:
        driver: WebDriver de Selenium
        tipo_documento: Código del tipo de documento (CC, TI, CE, PA, etc.)
    
    Returns:
        bool: True si se seleccionó correctamente
    
    Raises:
        RuntimeError: Si no se pudo seleccionar el tipo de documento
    """
    try:
        # Verificar si está en iframe
        try:
            verificar_iframe_con_elemento(driver, "tipoDoc")
        except:
            driver.switch_to.default_content()
        
        # Intentar diferentes localizadores para el dropdown (ID CORRECTO: tipoDoc)
        locators = [
            (By.ID, "tipoDoc"),
            (By.NAME, "tipoDoc"),
            (By.XPATH, "//select[@id='tipoDoc']"),
            (By.XPATH, "//select[@name='tipoDoc']"),
            (By.CSS_SELECTOR, "select#tipoDoc"),
            (By.XPATH, "//select[contains(@class, 'txtBox')]")
        ]
        
        dropdown_element = encontrar_elemento_con_localizadores(
            driver,
            locators,
            timeout=10,
            buscar_en_iframes=True,
        )
        
        if not dropdown_element:
            raise RuntimeError("No se encontró el dropdown de tipo de documento")
        
        # Crear objeto Select y seleccionar por valor
        select = Select(dropdown_element)
        
        # Verificar que el valor existe en las opciones
        opciones_disponibles = [opt.get_attribute('value') for opt in select.options]
        if tipo_documento not in opciones_disponibles:
            raise RuntimeError(f"Tipo de documento '{tipo_documento}' no está disponible. Opciones: {opciones_disponibles}")
        
        select.select_by_value(tipo_documento)
        
        # Pequeña espera para que el cambio se procese
        time.sleep(0.5)
        
        # Verificar que se seleccionó correctamente
        selected_value = select.first_selected_option.get_attribute('value')
        
        if selected_value == tipo_documento:
            print(f"[+] Tipo de documento '{tipo_documento}' seleccionado correctamente")
            return True
        else:
            raise RuntimeError(f"No se pudo seleccionar el tipo de documento '{tipo_documento}'")
            
    except Exception as e:
        print(f"[!] Error seleccionando tipo de documento: {e}")
        raise RuntimeError(f"Error al seleccionar tipo de documento: {str(e)}")


def escribir_texto_metodo_1(driver, element, texto):
    """Método 1: Click + Clear + Send Keys"""
    try:
        element.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
    
    element.clear()
    time.sleep(0.05)
    element.send_keys(texto)
    
    valor = driver.execute_script("return arguments[0].value;", element)
    return str(valor).strip() == str(texto)


def escribir_texto_metodo_2(driver, element, texto):
    """Método 2: ActionChains"""
    ac = ActionChains(driver)
    ac.move_to_element(element).click().send_keys(texto).perform()
    
    valor = driver.execute_script("return arguments[0].value;", element)
    return str(valor).strip() == str(texto)


def escribir_texto_metodo_3(driver, element, texto):
    """Método 3: Carácter por carácter"""
    element.click()
    element.clear()
    for char in texto:
        element.send_keys(char)
        time.sleep(0.1)
    
    valor = driver.execute_script("return arguments[0].value;", element)
    return str(valor).strip() == str(texto)


def escribir_texto_metodo_4(driver, element, texto):
    """Método 4: JavaScript"""
    js = """
    arguments[0].focus();
    arguments[0].value = arguments[1];
    var ev = new Event('input', { bubbles: true });
    arguments[0].dispatchEvent(ev);
    var ev2 = new Event('change', { bubbles: true });
    arguments[0].dispatchEvent(ev2);
    return arguments[0].value;
    """
    valor = driver.execute_script(js, element, str(texto))
    return str(valor).strip() == str(texto)


def escribir_en_campo(driver, cedula, timeout=30, debug_folder=DEBUG_DIR):
    """
    Escribe la cédula en el campo del formulario usando múltiples métodos
    
    Args:
        driver: WebDriver de Selenium
        cedula: Número de cédula a escribir
        timeout: Tiempo máximo de espera
        debug_folder: Carpeta para guardar información de debug
    
    Returns:
        bool: True si se escribió correctamente
    
    Raises:
        RuntimeError: Si no se pudo escribir después de todos los intentos
    """
    import os
    os.makedirs(debug_folder, exist_ok=True)

    # Normalizar cédula (eliminar espacios y caracteres no numéricos comunes)
    cedula = str(cedula).strip()
    if not cedula.isdigit():
        cedula_filtrada = "".join(ch for ch in cedula if ch.isdigit())
        if cedula_filtrada:
            cedula = cedula_filtrada

    # Verificar si está en iframe
    if not verificar_iframe_con_elemento(driver):
        driver.switch_to.default_content()

    # Localizadores alternativos
    locators = [
        (By.ID, "txtNumDoc"),
        (By.NAME, "numeroDocumento"),
        (By.XPATH, "//input[contains(@placeholder, 'Número de documento')]"),
        (By.XPATH, "//input[contains(@id, 'NumDoc')]")
    ]

    # Encontrar el elemento
    el = encontrar_elemento_con_localizadores(
        driver,
        locators,
        timeout,
        buscar_en_iframes=True,
    )
    
    if not el:
        screenshot, html = guardar_debug(driver, "no_element_present", debug_folder)
        raise RuntimeError(f"No se encontró el campo de cédula. Captura: {screenshot}")

    # Métodos de escritura
    metodos = [
        ("click_then_send", escribir_texto_metodo_1),
        ("actionchains_send", escribir_texto_metodo_2),
        ("char_by_char", escribir_texto_metodo_3),
        ("js_set_value", escribir_texto_metodo_4)
    ]

    last_exc = None
    for nombre, metodo in metodos:
        try:
            if metodo(driver, el, cedula):
                print(f"[+] Cédula escrita correctamente usando método: {nombre}")
                return True
        except StaleElementReferenceException as e:
            last_exc = e
            try:
                el = driver.find_element(By.ID, "txtNumDoc")
            except:
                pass
        except Exception as e:
            last_exc = e
        time.sleep(0.2)

    # Si llegamos aquí, ningún método funcionó
    screenshot, html = guardar_debug(driver, "write_failed", debug_folder)
    raise RuntimeError(
        f"No se pudo escribir la cédula tras todos los intentos. "
        f"Última excepción: {last_exc}. Capturas: {screenshot}, {html}"
    )


def enviar_formulario(driver, button_id="btnConsultar"):
    """
    Hace click en el botón de envío del formulario
    
    Args:
        driver: WebDriver de Selenium
        button_id: ID del botón a clickear
    
    Returns:
        list: Lista de handles de ventanas antes del click
    """
    try:
        btn = driver.find_element(By.ID, button_id)
    except:
        try:
            btn = driver.find_element(
                By.XPATH, 
                "//input[@type='submit' and contains(@value,'Consultar')]"
            )
        except:
            # Intentar buscar cualquier botón de submit
            btn = driver.find_element(By.XPATH, "//input[@type='submit']")
    
    ventanas_antes = driver.window_handles.copy()
    btn.click()
    print("[+] Click en Consultar realizado")

    return ventanas_antes
