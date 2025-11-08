#!/usr/bin/env python3
# config.py
"""Configuración global de la aplicación ADRES"""

import os

# Directorios
OUTPUT_DIR = os.path.join(os.getcwd(), "adres_output")
DEBUG_DIR = os.path.join(os.getcwd(), "debug")

# URLs
URL = "https://www.adres.gov.co/consulte-su-eps"

# Anti-Captcha API Key
ANTICAPTCHA_API_KEY = "d057f1ebb8c4334baf6441dffb519a10"  # Reemplaza con tu API Key

# Configuración por defecto
DEFAULT_CEDULA = ""
DEFAULT_TIMEOUT = 15

# Crear directorios si no existen
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)