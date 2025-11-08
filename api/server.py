# Wrapper para Vercel: importa la app Flask desde el archivo raíz `server.py`
# Vercel ejecutará esta aplicación como función serverless.

from server import app

# Algunas plataformas (incluido vercel/python) esperan que el archivo exponga
# una variable `app` que sea una instancia de Flask. Como ya la tenemos en
# `server.py`, simplemente la re-exportamos aquí.

# No ejecutar app.run() en este archivo; Vercel lo lanzará.


# Para compatibilidad con herramientas de testing locales, dejamos una
# ruta simple.
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
