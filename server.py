#!/usr/bin/env python3
# server.py
"""Servidor Flask para consulta ADRES via API REST"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
from threading import Thread
import json
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd
from werkzeug.utils import secure_filename

from config import URL, OUTPUT_DIR, DEBUG_DIR
from browser_api import iniciar_navegador, cerrar_navegador, guardar_debug
from form_api import escribir_en_campo, enviar_formulario, seleccionar_tipo_documento
from captcha_api import resolver_captcha, encontrar_input_captcha
from results_api import capturar_resultados, guardar_resultados

app = Flask(__name__)
CORS(app)

# Configuración de uploads
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Estado de consultas
consultas_en_progreso = {}
consultas_masivas = {}

TIPOS_DOCUMENTO_VALIDOS = ['CC', 'TI', 'CE', 'PA', 'RC', 'NU', 'AS', 'MS', 'CD', 'CN', 'SC', 'PE', 'PT']

XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _columna_a_indice(columna):
    """Convierte una referencia de columna de Excel (ej. 'AA') a índice basado en cero."""
    indice = 0
    for caracter in columna:
        if not caracter.isalpha():
            break
        indice = indice * 26 + (ord(caracter.upper()) - ord('A') + 1)
    return max(indice - 1, 0)


def _texto_shared_string(elemento):
    """Extrae el texto de un nodo <si> o inlineStr dentro del XML de Excel."""
    partes = []
    for nodo in elemento.iter():
        if nodo.tag.endswith('}t') and nodo.text:
            partes.append(nodo.text)
    return ''.join(partes)


def leer_excel_xlsx_basico(ruta):
    """Lee un archivo XLSX sin dependencias externas como openpyxl."""
    try:
        with zipfile.ZipFile(ruta) as archivo_zip:
            nombres = set(archivo_zip.namelist())

            shared_strings = []
            if 'xl/sharedStrings.xml' in nombres:
                raiz_shared = ET.fromstring(archivo_zip.read('xl/sharedStrings.xml'))
                for si in raiz_shared.findall(f'.//{{{XLSX_MAIN_NS}}}si'):
                    shared_strings.append(_texto_shared_string(si))

            workbook = ET.fromstring(archivo_zip.read('xl/workbook.xml'))
            hoja = workbook.find(f'.//{{{XLSX_MAIN_NS}}}sheet')
            if hoja is None:
                return pd.DataFrame()

            rel_id = hoja.attrib.get(f'{{{XLSX_REL_NS}}}id')
            destino_hoja = None

            try:
                rels = ET.fromstring(archivo_zip.read('xl/_rels/workbook.xml.rels'))
                for rel in rels.findall(f'{{{XLSX_REL_NS}}}Relationship'):
                    if rel.attrib.get('Id') == rel_id:
                        destino_hoja = rel.attrib.get('Target')
                        break
            except KeyError:
                pass

            if not destino_hoja:
                destino_hoja = 'worksheets/sheet1.xml'

            if not destino_hoja.startswith('xl/'):
                destino_hoja = f'xl/{destino_hoja}'

            hoja_xml = archivo_zip.read(destino_hoja)
            raiz_hoja = ET.fromstring(hoja_xml)

            datos = []
            max_columnas = 0
            for fila in raiz_hoja.findall(f'.//{{{XLSX_MAIN_NS}}}row'):
                celdas = {}
                for celda in fila.findall(f'{{{XLSX_MAIN_NS}}}c'):
                    referencia = celda.attrib.get('r', '')
                    columna = ''.join(ch for ch in referencia if ch.isalpha())
                    indice_columna = _columna_a_indice(columna) if columna else 0

                    valor = ''
                    tipo = celda.attrib.get('t')
                    if tipo == 's':
                        indice_shared = celda.find(f'{{{XLSX_MAIN_NS}}}v')
                        if indice_shared is not None and indice_shared.text:
                            try:
                                valor = shared_strings[int(indice_shared.text)]
                            except (ValueError, IndexError):
                                valor = ''
                    elif tipo == 'inlineStr':
                        inline = celda.find(f'{{{XLSX_MAIN_NS}}}is')
                        if inline is not None:
                            valor = _texto_shared_string(inline)
                    else:
                        nodo_valor = celda.find(f'{{{XLSX_MAIN_NS}}}v')
                        if nodo_valor is not None and nodo_valor.text is not None:
                            valor = nodo_valor.text

                    celdas[indice_columna] = valor
                    max_columnas = max(max_columnas, indice_columna + 1)

                fila_actual = [''] * max_columnas
                for indice, valor in celdas.items():
                    if indice >= len(fila_actual):
                        fila_actual.extend([''] * (indice + 1 - len(fila_actual)))
                    fila_actual[indice] = valor
                datos.append(fila_actual)

            if not datos:
                return pd.DataFrame()

            encabezados = [col.strip() for col in datos[0]]
            registros = []
            for fila in datos[1:]:
                registro = {}
                for indice, encabezado in enumerate(encabezados):
                    if not encabezado:
                        continue
                    valor = fila[indice] if indice < len(fila) else ''
                    registro[encabezado] = valor
                if registro:
                    registros.append(registro)

            df = pd.DataFrame(registros)
            if not df.empty:
                df = df.replace(r'^\s*$', pd.NA, regex=True)
            return df

    except (KeyError, zipfile.BadZipFile, ET.ParseError):
        pass

    return pd.DataFrame()


def cargar_excel_como_dataframe(ruta):
    """Intenta cargar un archivo Excel utilizando pandas y un lector básico como respaldo."""
    try:
        return pd.read_excel(ruta)
    except Exception as error:
        mensaje = str(error).lower()
        if ruta.lower().endswith('.xlsx') and 'openpyxl' in mensaje:
            df = leer_excel_xlsx_basico(ruta)
            if not df.empty:
                return df
        raise


def normalizar_numero_documento(valor):
    """Convierte el número de documento a una cadena solo con dígitos."""
    if valor is None:
        return ""

    import numbers

    if isinstance(valor, numbers.Number):
        try:
            return str(int(valor))
        except (ValueError, OverflowError):
            pass

    texto = str(valor).strip()
    if not texto:
        return ""

    if texto.isdigit():
        return texto

    texto_normalizado = texto.replace(" ", "").replace(",", "")
    if texto_normalizado.isdigit():
        return texto_normalizado

    try:
        numero = float(texto_normalizado)
        if numero.is_integer():
            return str(int(numero))
    except ValueError:
        pass

    solo_digitos = "".join(ch for ch in texto if ch.isdigit())
    return solo_digitos


def ejecutar_consulta_async(numero_doc, tipo_doc, consulta_id):
    """Ejecuta la consulta en background"""
    driver = None
    try:
        consultas_en_progreso[consulta_id] = {
            "estado": "iniciando",
            "progreso": 10,
            "mensaje": "Iniciando navegador..."
        }
        
        driver = iniciar_navegador(headless=False)
        driver.get(URL)
        time.sleep(2)
        
        # Seleccionar tipo de documento
        consultas_en_progreso[consulta_id] = {
            "estado": "seleccionando_tipo",
            "progreso": 20,
            "mensaje": "Seleccionando tipo de documento..."
        }
        seleccionar_tipo_documento(driver, tipo_doc)
        time.sleep(0.5)
        
        # Escribir número
        consultas_en_progreso[consulta_id] = {
            "estado": "escribiendo",
            "progreso": 30,
            "mensaje": "Escribiendo número de documento..."
        }
        escribir_en_campo(driver, numero_doc)
        
        # Resolver CAPTCHA
        consultas_en_progreso[consulta_id] = {
            "estado": "captcha",
            "progreso": 45,
            "mensaje": "Resolviendo CAPTCHA..."
        }
        captcha_value = resolver_captcha(driver)
        
        if captcha_value is None:
            consultas_en_progreso[consulta_id] = {
                "estado": "error",
                "progreso": 100,
                "mensaje": "CAPTCHA cancelado por el operador"
            }
            return
        
        # Ingresar CAPTCHA
        consultas_en_progreso[consulta_id] = {
            "estado": "ingresando_captcha",
            "progreso": 60,
            "mensaje": "Ingresando valor del CAPTCHA..."
        }
        captcha_input = encontrar_input_captcha(driver)
        if captcha_input is None:
            raise RuntimeError("No se encontró el input del CAPTCHA")
        
        try:
            captcha_input.clear()
        except:
            pass
        captcha_input.send_keys(captcha_value)
        time.sleep(0.2)
        
        # Enviar formulario
        consultas_en_progreso[consulta_id] = {
            "estado": "enviando",
            "progreso": 75,
            "mensaje": "Enviando formulario..."
        }
        ventanas_antes = enviar_formulario(driver)
        
        # Capturar resultados (OPTIMIZADO)
        consultas_en_progreso[consulta_id] = {
            "estado": "capturando",
            "progreso": 90,
            "mensaje": "Capturando resultados..."
        }
        time.sleep(2)  # Reducido de 3 a 2 segundos
        contenido_resultado = capturar_resultados(driver, ventanas_antes, timeout=15)  # Reducido de 20 a 15
        
        if not contenido_resultado:
            raise RuntimeError("No se pudo capturar el contenido de los resultados")
        
        # Guardar resultados
        nombre_archivo = f"{tipo_doc}_{numero_doc}"
        archivos, datos_json = guardar_resultados(nombre_archivo, contenido_resultado, driver)
        
        # Actualizar estado final
        enlaces_descarga = {
            clave: f"/api/descargar/{nombre_archivo}/{clave}"
            for clave in archivos.keys()
        }

        consultas_en_progreso[consulta_id] = {
            "estado": "completado",
            "progreso": 100,
            "mensaje": "Consulta completada exitosamente",
            "datos": datos_json,
            "archivos": {k: os.path.basename(v) for k, v in archivos.items()},
            "links_descarga": enlaces_descarga,
            "nombre_archivo": nombre_archivo,
            "tipo_doc": tipo_doc,
            "numero_doc": numero_doc
        }
        
    except Exception as e:
        consultas_en_progreso[consulta_id] = {
            "estado": "error",
            "progreso": 100,
            "mensaje": f"Error: {str(e)}"
        }
        
        try:
            if driver:
                guardar_debug(driver, "error", DEBUG_DIR)
        except:
            pass
    
    finally:
        if driver:
            cerrar_navegador(driver, delay=2)  # Reducido de 3 a 2


def ejecutar_consulta_masiva_async(archivo_excel, lote_id):
    """Ejecuta consultas masivas desde un archivo Excel"""
    try:
        # Leer Excel
        try:
            df = cargar_excel_como_dataframe(archivo_excel)
        except Exception as e:
            consultas_masivas[lote_id] = {
                "estado": "error",
                "mensaje": f"Error al leer el archivo Excel: {str(e)}"
            }
            return
        
        # Validar que no esté vacío
        if df.empty:
            consultas_masivas[lote_id] = {
                "estado": "error",
                "mensaje": "El archivo Excel está vacío"
            }
            return
        
        # Validar columnas
        if 'tipo_identificacion' not in df.columns or 'numero_identificacion' not in df.columns:
            consultas_masivas[lote_id] = {
                "estado": "error",
                "mensaje": "El archivo debe tener las columnas: tipo_identificacion, numero_identificacion"
            }
            return
        
        # Limpiar datos y eliminar filas vacías
        df = df.dropna(subset=['tipo_identificacion', 'numero_identificacion'])
        
        if df.empty:
            consultas_masivas[lote_id] = {
                "estado": "error",
                "mensaje": "No hay registros válidos en el archivo"
            }
            return
        
        total = len(df)
        
        consultas_masivas[lote_id] = {
            "estado": "procesando",
            "total": total,
            "procesados": 0,
            "exitosos": 0,
            "fallidos": 0,
            "resultados": []
        }
        
        # Procesar cada registro
        for idx, row in df.iterrows():
            tipo_doc = str(row['tipo_identificacion']).strip().upper()
            numero_doc = normalizar_numero_documento(row['numero_identificacion'])

            if tipo_doc not in TIPOS_DOCUMENTO_VALIDOS:
                consultas_masivas[lote_id]["fallidos"] += 1
                consultas_masivas[lote_id]["resultados"].append({
                    "tipo_doc": tipo_doc,
                    "numero_doc": str(row['numero_identificacion']).strip(),
                    "estado": "error",
                    "mensaje": "Tipo de documento inválido"
                })
                consultas_masivas[lote_id]["procesados"] = idx + 1
                continue

            if not numero_doc:
                consultas_masivas[lote_id]["fallidos"] += 1
                consultas_masivas[lote_id]["resultados"].append({
                    "tipo_doc": tipo_doc,
                    "numero_doc": str(row['numero_identificacion']).strip(),
                    "estado": "error",
                    "mensaje": "Número de documento inválido"
                })
                consultas_masivas[lote_id]["procesados"] = idx + 1
                continue

            consultas_masivas[lote_id]["mensaje"] = f"Procesando {idx+1}/{total}: {tipo_doc} {numero_doc}"

            # Ejecutar consulta individual
            consulta_id = f"{tipo_doc}_{numero_doc}_{int(time.time())}"
            ejecutar_consulta_async(numero_doc, tipo_doc, consulta_id)
            
            # Esperar a que termine
            while consulta_id in consultas_en_progreso:
                estado = consultas_en_progreso[consulta_id]
                if estado["estado"] in ["completado", "error"]:
                    break
                time.sleep(1)
            
            # Guardar resultado
            estado_final = consultas_en_progreso.get(consulta_id, {})
            resultado = {
                "tipo_doc": tipo_doc,
                "numero_doc": numero_doc,
                "estado": estado_final.get("estado"),
                "datos": estado_final.get("datos") if estado_final.get("estado") == "completado" else None,
                "links_descarga": estado_final.get("links_descarga"),
                "nombre_archivo": estado_final.get("nombre_archivo"),
                "archivos": estado_final.get("archivos")
            }
            
            consultas_masivas[lote_id]["resultados"].append(resultado)
            consultas_masivas[lote_id]["procesados"] = idx + 1
            
            if estado_final.get("estado") == "completado":
                consultas_masivas[lote_id]["exitosos"] += 1
            else:
                consultas_masivas[lote_id]["fallidos"] += 1
            
            # Limpieza
            if consulta_id in consultas_en_progreso:
                del consultas_en_progreso[consulta_id]
            
            # Pequeña pausa entre consultas
            time.sleep(1)
        
        # Guardar resultados consolidados
        consolidado_path = os.path.join(OUTPUT_DIR, f"lote_{lote_id}.json")
        with open(consolidado_path, 'w', encoding='utf-8') as f:
            json.dump(consultas_masivas[lote_id]["resultados"], f, indent=2, ensure_ascii=False)
        
        consultas_masivas[lote_id]["estado"] = "completado"
        consultas_masivas[lote_id]["mensaje"] = "Lote procesado completamente"
        consultas_masivas[lote_id]["archivo_consolidado"] = consolidado_path
        consultas_masivas[lote_id]["link_consolidado"] = f"/api/descargar-lote/{lote_id}"
        
    except Exception as e:
        consultas_masivas[lote_id] = {
            "estado": "error",
            "mensaje": f"Error procesando lote: {str(e)}"
        }


@app.route('/')
def index():
    """Sirve el archivo HTML principal"""
    return send_from_directory('.', 'index.html')


@app.route('/api/consultar', methods=['POST'])
def consultar():
    """Endpoint para iniciar una consulta individual"""
    data = request.get_json()
    numero_doc = normalizar_numero_documento(data.get('numero_doc'))
    tipo_doc = data.get('tipo_doc', 'CC').strip().upper()

    # Validar
    if not numero_doc:
        return jsonify({"error": "El número de documento debe contener solo números"}), 400
    
    if tipo_doc not in TIPOS_DOCUMENTO_VALIDOS:
        return jsonify({"error": f"Tipo de documento inválido. Valores permitidos: {TIPOS_DOCUMENTO_VALIDOS}"}), 400
    
    # Generar ID único
    consulta_id = f"{tipo_doc}_{numero_doc}_{int(time.time())}"
    
    # Iniciar consulta en background
    thread = Thread(target=ejecutar_consulta_async, args=(numero_doc, tipo_doc, consulta_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "consulta_id": consulta_id,
        "mensaje": "Consulta iniciada"
    })


@app.route('/api/consultar-lote', methods=['POST'])
def consultar_lote():
    """Endpoint para procesar un archivo Excel con múltiples consultas"""
    if 'archivo' not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    
    file = request.files['archivo']
    
    if file.filename == '':
        return jsonify({"error": "Archivo vacío"}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"error": "Solo se permiten archivos Excel (.xlsx, .xls)"}), 400
    
    # Guardar archivo
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Generar ID del lote
    lote_id = f"lote_{int(time.time())}"
    
    # Iniciar procesamiento en background
    thread = Thread(target=ejecutar_consulta_masiva_async, args=(filepath, lote_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "lote_id": lote_id,
        "mensaje": "Procesamiento de lote iniciado"
    })


@app.route('/api/estado/<consulta_id>', methods=['GET'])
def obtener_estado(consulta_id):
    """Endpoint para obtener el estado de una consulta individual"""
    estado = consultas_en_progreso.get(consulta_id)
    
    if not estado:
        return jsonify({"error": "Consulta no encontrada"}), 404
    
    return jsonify(estado)


@app.route('/api/estado-lote/<lote_id>', methods=['GET'])
def obtener_estado_lote(lote_id):
    """Endpoint para obtener el estado de un lote"""
    estado = consultas_masivas.get(lote_id)
    
    if not estado:
        return jsonify({"error": "Lote no encontrado"}), 404
    
    return jsonify(estado)


@app.route('/api/descargar/<nombre_archivo>/<tipo>', methods=['GET'])
def descargar_archivo(nombre_archivo, tipo):
    """Endpoint para descargar archivos generados"""
    extensiones = {
        'html': 'html',
        'json': 'json',
        'txt': 'txt',
        'screenshot': 'png'
    }
    
    if tipo not in extensiones:
        return jsonify({"error": "Tipo de archivo inválido"}), 400
    
    filename = f"resultado_{nombre_archivo}.{extensiones[tipo]}"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "Archivo no encontrado"}), 404
    
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/api/descargar-lote/<lote_id>', methods=['GET'])
def descargar_lote(lote_id):
    """Endpoint para descargar resultados consolidados de un lote"""
    filename = f"lote_{lote_id}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({"error": "Archivo no encontrado"}), 404
    
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/api/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    return jsonify({
        "status": "ok",
        "consultas_activas": len([c for c in consultas_en_progreso.values() if c["estado"] not in ["completado", "error"]]),
        "lotes_activos": len([l for l in consultas_masivas.values() if l["estado"] == "procesando"])
    })


if __name__ == '__main__':
    print("=" * 60)
    print("SERVIDOR ADRES - API REST")
    print("=" * 60)
    print(f"URL: http://localhost:5000")
    print(f"Documentación API:")
    print(f"  POST   /api/consultar            - Consulta individual")
    print(f"  POST   /api/consultar-lote       - Consulta masiva (Excel)")
    print(f"  GET    /api/estado/<id>          - Estado consulta individual")
    print(f"  GET    /api/estado-lote/<id>     - Estado lote")
    print(f"  GET    /api/descargar/<doc>/<tipo> - Descargar archivo")
    print(f"  GET    /api/descargar-lote/<id>  - Descargar consolidado")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)


# Handler para Vercel (añade esto al final de server.py)
def handler(request):
    from flask import request as flask_request
    with app.request_context(flask_request.environ):
        return app.full_dispatch_request()