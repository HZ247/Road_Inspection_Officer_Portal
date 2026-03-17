from flask import Flask, send_from_directory
from flask_cors import CORS
import os

from server.database import init_db
from server.routes.auth       import auth_bp
from server.routes.attendance import attendance_bp
from server.routes.inspection import inspection_bp
from server.routes.material   import material_bp
from server.routes.admin      import admin_bp

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
CLIENT_DIR = os.path.join(BASE_DIR, 'client')
UPLOAD_DIR = os.path.join(BASE_DIR, 'server', 'uploads')

app = Flask(__name__, static_folder=CLIENT_DIR, static_url_path='')
CORS(app)

app.register_blueprint(auth_bp,        url_prefix='/api/auth')
app.register_blueprint(attendance_bp,  url_prefix='/api/attendance')
app.register_blueprint(inspection_bp,  url_prefix='/api/inspection')
app.register_blueprint(material_bp,    url_prefix='/api/material')
app.register_blueprint(admin_bp,       url_prefix='/api/admin')

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/')
def index():
    return send_from_directory(CLIENT_DIR, 'login.html')

@app.route('/<path:path>')
def serve_static(path):
    full_path = os.path.join(CLIENT_DIR, path)
    if os.path.isfile(full_path):
        return send_from_directory(CLIENT_DIR, path)
    return send_from_directory(CLIENT_DIR, 'login.html')

if __name__ == '__main__':
    print('\n🚀 FVO Server starting...')
    init_db()
    print('   Open browser → http://localhost:5000\n')
    app.run(debug=True, port=5000)