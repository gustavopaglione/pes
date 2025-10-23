from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import os
import numpy as np
import imutils
from datetime import datetime
from database import db  # Asumiendo que db está en database.py; si no, usa el de models
from models import Admin, Persona, LogAcceso  # Importa tus modelos

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Cambia por una segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/reconocimiento'  # Ajusta
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Rutas de datos (Data/)
DATA_PATH = './Data'
MODEL_PATH = './modeloLBPHFace.xml'
os.makedirs(DATA_PATH, exist_ok=True)

# Variables globales para el reconocedor (se actualiza después de entrenar)
face_recognizer = cv2.face.LBPHFaceRecognizer_create()
people_list = []  # Lista de nombres de carpetas/personas

def entrenar_modelo():
    """Ejecuta el entrenamiento basado en entrenandoRF.py"""
    global face_recognizer, people_list
    people_list = os.listdir(DATA_PATH)
    labels = []
    faces_data = []
    label = 0

    for name_dir in people_list:
        person_path = os.path.join(DATA_PATH, name_dir)
        if not os.path.isdir(person_path):
            continue
        for filename in os.listdir(person_path):
            if filename.endswith('.jpg'):
                img_path = os.path.join(person_path, filename)
                img = cv2.imread(img_path, 0)
                if img is not None:
                    faces_data.append(img)
                    labels.append(label)
        label += 1

    if len(faces_data) == 0:
        print("No hay datos para entrenar.")
        return

    print("Entrenando modelo...")
    face_recognizer.train(faces_data, np.array(labels))
    face_recognizer.write(MODEL_PATH)
    print("Modelo guardado en", MODEL_PATH)
    # Actualiza lista global
    people_list = [name for name in people_list if os.path.isdir(os.path.join(DATA_PATH, name))]

# Inicializar modelo al inicio
if os.path.exists(MODEL_PATH):
    face_recognizer.read(MODEL_PATH)
    people_list = os.listdir(DATA_PATH)

# Cargar cámara global para reconocimiento
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

def gen_frames_reconocimiento():
    """Genera frames para video feed con reconocimiento (basado en reconocimientoFacial.py)"""
    global face_recognizer, people_list
    face_classif = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = imutils.resize(frame, width=640)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aux_frame = gray.copy()

        faces = face_classif.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            rostro = aux_frame[y:y+h, x:x+w]
            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            result = face_recognizer.predict(rostro)

            # Dibujar confianza
            cv2.putText(frame, str(result[1]), (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

            if result[1] < 70:  # Umbral LBPH como en tu script
                name = people_list[result[0]]
                cv2.putText(frame, name, (x, y-25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

                # Loggear acceso exitoso y simular barrera
                persona = Persona.query.filter_by(nombre=name).first()
                if persona:
                    log = LogAcceso(persona_id=persona.id, exito=True)
                    db.session.add(log)
                    db.session.commit()
                    print(f"Acceso concedido para {name}. Barrera abierta!")  # Aquí integra hardware, e.g., GPIO.output(18, True)
            else:
                cv2.putText(frame, 'Desconocido', (x, y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

                # Loggear fallo
                log = LogAcceso(exito=False)
                db.session.add(log)
                db.session.commit()
                print("Acceso denegado: Desconocido.")

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
@login_required
def index():
    return render_template('index.html')  # Página principal con video feed

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(gen_frames_reconocimiento(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            user = User(admin.id)
            login_user(user)
            return redirect(url_for('index'))
        flash('Credenciales inválidas')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        rubro = request.form['rubro']

        if not (nombre and telefono and rubro):
            flash('Todos los campos son obligatorios')
            return redirect(request.url)

        # Verificar si ya existe
        if Persona.query.filter_by(nombre=nombre).first():
            flash('Persona ya registrada')
            return redirect(request.url)

        # Crear carpeta para la persona
        person_path = os.path.join(DATA_PATH, nombre)
        os.makedirs(person_path, exist_ok=True)

        # Redirigir a captura (pasar datos en session)
        session['pending_registro'] = {'nombre': nombre, 'telefono': telefono, 'rubro': rubro}
        return redirect(url_for('captura_rostro'))

    return render_template('register.html')


@app.route('/captura_rostro', methods=['GET', 'POST'])
@login_required
def captura_rostro():
    if 'pending_registro' not in session:
        flash('Sesión de registro expirada')
        return redirect(url_for('register'))

    if request.method == 'POST':
        # Recibir imágenes base64 del JS y guardar
        images_base64 = request.form.getlist('images[]')  # Lista de base64
        nombre = session['pending_registro']['nombre']
        person_path = os.path.join(DATA_PATH, nombre)
        count = 0

        for img_b64 in images_base64:
            # Decodificar base64 a imagen
            import base64
            img_data = base64.b64decode(img_b64.split(',')[1])  # Remover header
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
            
            if len(faces) > 0:
                # Tomar el primer rostro, redimensionar y guardar (como en capturadoRostros.py)
                (x, y, w, h) = faces[0]
                rostro = gray[y:y+h, x:x+w]
                rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
                cv2.imwrite(os.path.join(person_path, f'rostro_{count}.jpg'), rostro)
                count += 1

        if count < 50:  # Mínimo imágenes para buen entrenamiento
            flash('No se capturaron suficientes rostros válidos. Intenta de nuevo.')
            session.pop('pending_registro')
            return redirect(url_for('register'))

        # Guardar en DB
        persona = Persona(nombre=nombre, telefono=session['pending_registro']['telefono'], rubro=session['pending_registro']['rubro'])
        db.session.add(persona)
        db.session.commit()

        # Entrenar modelo
        entrenar_modelo()

        session.pop('pending_registro')
        flash(f'Feriantes {nombre} registrado correctamente. Modelo actualizado.')
        return redirect(url_for('index'))

    return render_template('captura_rostro.html', nombre=session['pending_registro']['nombre'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')  # Para acceso remoto si necesitas