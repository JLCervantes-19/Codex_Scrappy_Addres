from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Servir el frontend
@app.route('/')
def serve_frontend():
    return send_from_directory('..', 'index.html')

# Servir archivos estáticos (CSS, JS, etc.)
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('..', filename)

# Endpoint de salud
@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "message": "Server is running"})

# Handler para Vercel
def handler(request):
    from flask import request as flask_request
    with app.request_context(flask_request.environ):
        try:
            return app.full_dispatch_request()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)