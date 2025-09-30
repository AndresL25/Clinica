from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime, timedelta
import random
import uuid
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = 'tu-clave-secreta-aqui-cambiar-en-produccion'

# Configuración
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Crear directorio de uploads si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Fisioterapeutas disponibles
FISIOTERAPEUTAS = [
    {"id": 1, "nombre": "Dr. María González", "especialidad": "Rehabilitación Motriz"},
    {"id": 2, "nombre": "Dr. Carlos Rodríguez", "especialidad": "Terapia Deportiva"}
]

def init_db():
    """Inicializar la base de datos"""
    conn = sqlite3.connect('clinica.db')
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_registro TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            telefono TEXT NOT NULL,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de síntomas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sintomas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            descripcion TEXT NOT NULL,
            intensidad INTEGER NOT NULL CHECK (intensidad >= 1 AND intensidad <= 10),
            fecha_reporte TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de fotos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nombre_archivo TEXT NOT NULL,
            descripcion TEXT,
            fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    # Tabla de citas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            fisioterapeuta_id INTEGER NOT NULL,
            fecha_cita DATETIME NOT NULL,
            estado TEXT DEFAULT 'programada',
            notas TEXT,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def allowed_file(filename):
    """Verificar si el archivo tiene una extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generar_codigo_registro():
    """Generar un código único de registro"""
    return f"REG-{uuid.uuid4().hex[:8].upper()}"

def asignar_cita_automatica(usuario_id):
    """Asignar una cita automáticamente"""
    # Lógica: asignar cita entre 3-10 días hábiles desde hoy
    dias_adelante = random.randint(3, 10)
    fecha_cita = datetime.now() + timedelta(days=dias_adelante)
    
    # Asegurar que sea día hábil (lunes a viernes)
    while fecha_cita.weekday() >= 5:  # 5=sábado, 6=domingo
        fecha_cita += timedelta(days=1)
    
    # Asignar hora entre 8:00 AM y 5:00 PM
    hora = random.randint(8, 17)
    minutos = random.choice([0, 30])
    fecha_cita = fecha_cita.replace(hour=hora, minute=minutos, second=0, microsecond=0)
    
    # Seleccionar fisioterapeuta aleatoriamente
    fisioterapeuta = random.choice(FISIOTERAPEUTAS)
    
    # Guardar cita en la base de datos
    conn = sqlite3.connect('clinica.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO citas (usuario_id, fisioterapeuta_id, fecha_cita, notas)
        VALUES (?, ?, ?, ?)
    ''', (usuario_id, fisioterapeuta['id'], fecha_cita, f"Cita inicial con {fisioterapeuta['nombre']}"))
    
    conn.commit()
    conn.close()
    
    return {
        'fecha_cita': fecha_cita.strftime('%Y-%m-%d %H:%M'),
        'fisioterapeuta': fisioterapeuta
    }

@app.route('/')
def home():
    """Página principal con interfaz web"""
    return render_template('index.html')

@app.route('/api')
def api_info():
    """Endpoint con información de la API"""
    return jsonify({
        'mensaje': 'API Clínica de Rehabilitación',
        'version': '1.0',
        'endpoints': {
            'registro': 'POST /registro',
            'consultar_usuario': 'GET /usuario/<codigo_registro>',
            'reportar_sintomas': 'POST /sintomas',
            'subir_foto': 'POST /fotos',
            'consultar_citas': 'GET /citas/<codigo_registro>',
            'ver_foto': 'GET /foto/<nombre_archivo>'
        }
    })

@app.route('/registro', methods=['GET', 'POST'])
def registrar_usuario():
    """Registrar un nuevo usuario"""
    if request.method == 'GET':
        return render_template('registro.html')
        
    try:
        # Manejar tanto JSON como form data
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Validar campos requeridos
        campos_requeridos = ['nombre', 'email', 'telefono']
        for campo in campos_requeridos:
            if not data.get(campo):
                if request.content_type == 'application/json':
                    return jsonify({'error': f'Campo {campo} es requerido'}), 400
                flash(f'Campo {campo} es requerido', 'error')
                return redirect(url_for('registrar_usuario'))
        
        # Generar código de registro único
        codigo_registro = generar_codigo_registro()
        
        # Guardar en base de datos
        conn = sqlite3.connect('clinica.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO usuarios (codigo_registro, nombre, email, telefono)
            VALUES (?, ?, ?, ?)
        ''', (codigo_registro, data['nombre'], data['email'], data['telefono']))
        
        usuario_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Asignar cita automáticamente
        cita_info = asignar_cita_automatica(usuario_id)
        
        if request.content_type == 'application/json':
            return jsonify({
                'mensaje': 'Usuario registrado exitosamente',
                'codigo_registro': codigo_registro,
                'usuario_id': usuario_id,
                'cita_asignada': cita_info
            }), 201
        else:
            flash(f'¡Registro exitoso! Tu código es: {codigo_registro}', 'success')
            return render_template('registro_exitoso.html', 
                                 codigo_registro=codigo_registro, 
                                 cita_info=cita_info)
        
    except Exception as e:
        if request.content_type == 'application/json':
            return jsonify({'error': str(e)}), 500
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('registrar_usuario'))

@app.route('/consultar')
def consultar_form():
    """Formulario para consultar usuario"""
    return render_template('consultar.html')

@app.route('/usuario/<codigo_registro>', methods=['GET'])
def consultar_usuario(codigo_registro):
    """Consultar información de un usuario"""
    try:
        conn = sqlite3.connect('clinica.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, codigo_registro, nombre, email, telefono, fecha_registro
            FROM usuarios WHERE codigo_registro = ?
        ''', (codigo_registro,))
        
        usuario = cursor.fetchone()
        if not usuario:
            if 'web' in request.args:
                flash('Usuario no encontrado', 'error')
                return redirect(url_for('consultar_form'))
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Obtener síntomas
        cursor.execute('''
            SELECT descripcion, intensidad, fecha_reporte
            FROM sintomas WHERE usuario_id = ?
            ORDER BY fecha_reporte DESC
        ''', (usuario[0],))
        sintomas = cursor.fetchall()
        
        # Obtener fotos
        cursor.execute('''
            SELECT nombre_archivo, descripcion, fecha_subida
            FROM fotos WHERE usuario_id = ?
            ORDER BY fecha_subida DESC
        ''', (usuario[0],))
        fotos = cursor.fetchall()
        
        conn.close()
        
        usuario_data = {
            'usuario': {
                'id': usuario[0],
                'codigo_registro': usuario[1],
                'nombre': usuario[2],
                'email': usuario[3],
                'telefono': usuario[4],
                'fecha_registro': usuario[5]
            },
            'sintomas': [
                {
                    'descripcion': s[0],
                    'intensidad': s[1],
                    'fecha': s[2]
                } for s in sintomas
            ],
            'fotos': [
                {
                    'archivo': f[0],
                    'descripcion': f[1],
                    'fecha': f[2],
                    'url': f'/foto/{f[0]}'
                } for f in fotos
            ]
        }
        
        if 'web' in request.args:
            return render_template('perfil_usuario.html', 
                                 usuario=usuario_data['usuario'],
                                 sintomas=usuario_data['sintomas'],
                                 fotos=usuario_data['fotos'])
        
        return jsonify(usuario_data)
        
    except Exception as e:
        if 'web' in request.args:
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('consultar_form'))
        return jsonify({'error': str(e)}), 500

@app.route('/sintomas', methods=['POST'])
def reportar_sintomas():
    """Reportar síntomas de un usuario"""
    try:
        data = request.get_json()
        
        # Validar campos
        if not data.get('codigo_registro'):
            return jsonify({'error': 'Código de registro requerido'}), 400
        if not data.get('descripcion'):
            return jsonify({'error': 'Descripción de síntomas requerida'}), 400
        
        intensidad = data.get('intensidad', 5)
        if not isinstance(intensidad, int) or intensidad < 1 or intensidad > 10:
            return jsonify({'error': 'Intensidad debe ser un número entre 1 y 10'}), 400
        
        # Buscar usuario
        conn = sqlite3.connect('clinica.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM usuarios WHERE codigo_registro = ?', (data['codigo_registro'],))
        usuario = cursor.fetchone()
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Guardar síntoma
        cursor.execute('''
            INSERT INTO sintomas (usuario_id, descripcion, intensidad)
            VALUES (?, ?, ?)
        ''', (usuario[0], data['descripcion'], intensidad))
        
        conn.commit()
        conn.close()
        
        return jsonify({'mensaje': 'Síntomas reportados exitosamente'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fotos', methods=['POST'])
def subir_foto():
    """Subir foto de un usuario"""
    try:
        # Verificar que se envió un archivo
        if 'foto' not in request.files:
            return jsonify({'error': 'No se envió ninguna foto'}), 400
        
        file = request.files['foto']
        codigo_registro = request.form.get('codigo_registro')
        descripcion = request.form.get('descripcion', '')
        
        if not codigo_registro:
            return jsonify({'error': 'Código de registro requerido'}), 400
        
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Tipo de archivo no permitido. Use: png, jpg, jpeg, gif'}), 400
        
        # Buscar usuario
        conn = sqlite3.connect('clinica.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM usuarios WHERE codigo_registro = ?', (codigo_registro,))
        usuario = cursor.fetchone()
        
        if not usuario:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Generar nombre único para el archivo
        filename = secure_filename(file.filename)
        nombre_unico = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], nombre_unico)
        
        # Guardar archivo
        file.save(filepath)
        
        # Guardar en base de datos
        cursor.execute('''
            INSERT INTO fotos (usuario_id, nombre_archivo, descripcion)
            VALUES (?, ?, ?)
        ''', (usuario[0], nombre_unico, descripcion))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'mensaje': 'Foto subida exitosamente',
            'archivo': nombre_unico,
            'url': f'/foto/{nombre_unico}'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/foto/<nombre_archivo>')
def ver_foto(nombre_archivo):
    """Ver una foto subida"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], nombre_archivo)

@app.route('/citas/<codigo_registro>', methods=['GET'])
def consultar_citas(codigo_registro):
    """Consultar citas de un usuario"""
    try:
        conn = sqlite3.connect('clinica.db')
        cursor = conn.cursor()
        
        # Buscar usuario
        cursor.execute('SELECT id, nombre FROM usuarios WHERE codigo_registro = ?', (codigo_registro,))
        usuario = cursor.fetchone()
        
        if not usuario:
            if 'web' in request.args:
                flash('Usuario no encontrado', 'error')
                return redirect(url_for('consultar_form'))
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Obtener citas
        cursor.execute('''
            SELECT id, fisioterapeuta_id, fecha_cita, estado, notas, fecha_creacion
            FROM citas WHERE usuario_id = ?
            ORDER BY fecha_cita ASC
        ''', (usuario[0],))
        
        citas_db = cursor.fetchall()
        conn.close()
        
        # Formatear citas con información del fisioterapeuta
        citas = []
        for cita in citas_db:
            fisioterapeuta = next((f for f in FISIOTERAPEUTAS if f['id'] == cita[1]), None)
            citas.append({
                'id': cita[0],
                'fecha_cita': cita[2],
                'estado': cita[3],
                'notas': cita[4],
                'fecha_creacion': cita[5],
                'fisioterapeuta': fisioterapeuta
            })
        
        citas_data = {
            'usuario': {
                'codigo_registro': codigo_registro,
                'nombre': usuario[1]
            },
            'citas': citas,
            'total_citas': len(citas)
        }
        
        if 'web' in request.args:
            return render_template('citas_usuario.html', 
                                 usuario=citas_data['usuario'],
                                 citas=citas_data['citas'],
                                 total_citas=citas_data['total_citas'])
        
        return jsonify(citas_data)
        
    except Exception as e:
        if 'web' in request.args:
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('consultar_form'))
        return jsonify({'error': str(e)}), 500

@app.route('/fisioterapeutas', methods=['GET'])
def listar_fisioterapeutas():
    """Listar fisioterapeutas disponibles"""
    return jsonify({'fisioterapeutas': FISIOTERAPEUTAS})

if __name__ == '__main__':
    init_db()  # Crear tablas si no existen
    app.run(debug=True)