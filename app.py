from flask import Flask, render_template, request, redirect, url_for, Response, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import os
import numpy as np
import imutils
from datetime import datetime

# ------------------------------------------------------
# CONFIGURACIÓN FLASK + BASE DE DATOS
# ------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Cambia por una segura
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)  # ✅ Solo una vez

# ------------------------------------------------------
# LOGIN MANAGER
# ------------------------------------------------------
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin):
    def __init__(self, id):
        self.id = id


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


# ------------------------------------------------------
# MODELOS
# ------------------------------------------------------
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Persona(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(50))
    rubro = db.Column(db.String(100))


class LogAcceso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona.id'), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    exito = db.Column(db.Boolean, default=False)


# ------------------------------------------------------
# CONFIGURACIÓN DE ROSTROS Y MODELOS
# ------------------------------------------------------
DATA_PATH = './Data'
MODEL_PATH = './modeloLBPHFace.xml'
os.makedirs(DATA_PATH, exist_ok=True)

face_recognizer = cv2.face.LBPHFaceRecognizer_create()
people_list = []

def entrenar_modelo():
    """Entrena el modelo LBPH."""
    global face_recognizer, people_list
    people_list = os.listdir(DATA_PATH)
    labels, faces_data = [], []
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

    if not faces_data:
        print("No hay datos para entrenar.")
        return

    face_recognizer.train(faces_data, np.array(labels))
    face_recognizer.write(MODEL_PATH)
    people_list = [n for n in people_list if os.path.isdir(os.path.join(DATA_PATH, n))]
    print("✅ Modelo entrenado y guardado.")


if os.path.exists(MODEL_PATH):
    face_recognizer.read(MODEL_PATH)
    people_list = os.listdir(DATA_PATH)

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)


def gen_frames_reconocimiento():
    """Genera frames de video con detección facial en tiempo real"""
    global cap, face_recognizer, people_list
    face_classif = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    if not cap.isOpened():
        cap.open(0, cv2.CAP_DSHOW)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ No se pudo leer la cámara")
            break

        frame = imutils.resize(frame, width=640)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        aux_frame = gray.copy()

        faces = face_classif.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            rostro = aux_frame[y:y+h, x:x+w]
            rostro = cv2.resize(rostro, (150, 150), interpolation=cv2.INTER_CUBIC)
            result = face_recognizer.predict(rostro)

            if result[1] < 70:
                name = people_list[result[0]] if len(people_list) > result[0] else "Desconocido"
                color = (0, 255, 0)
                texto = f"{name} ({result[1]:.0f})"
            else:
                color = (0, 0, 255)
                texto = "Desconocido"

            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.putText(frame, texto, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Codificar el frame y enviarlo como respuesta
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')



# ------------------------------------------------------
# RUTAS
# ------------------------------------------------------
@app.route('/')
@login_required
def index():
    return render_template('index.html')


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


@app.route('/registrarse', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        rubro = request.form['rubro']

        if not (nombre and telefono and rubro):
            flash('Todos los campos son obligatorios')
            return redirect(request.url)

        if Persona.query.filter_by(nombre=nombre).first():
            flash('Persona ya registrada')
            return redirect(request.url)

        person_path = os.path.join(DATA_PATH, nombre)
        os.makedirs(person_path, exist_ok=True)

        session['pending_registro'] = {'nombre': nombre, 'telefono': telefono, 'rubro': rubro}
        return redirect(url_for('captura_rostro'))

    return render_template('registrarse.html')


@app.route('/captura_rostro', methods=['GET', 'POST'])
@login_required
def captura_rostro():
    if request.method == 'POST':
        data = request.get_json()
        img_b64 = data.get('image')
        if not img_b64:
            return jsonify({'message': 'No se recibió imagen'}), 400

        # Guardar imagen
        img_data = base64.b64decode(img_b64.split(',')[1])
        filename = f"rostros/{current_user.id}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_data)

        return jsonify({'message': 'Rostro capturado correctamente'})

    return render_template('captura_rostro.html', nombre=current_user.nombre)



@app.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if Admin.query.filter_by(username=username).first():
            flash('Ese usuario ya existe.')
            return redirect(url_for('register_admin'))

        new_admin = Admin(username=username)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()

        flash('Administrador registrado correctamente.')
        return redirect(url_for('login'))

    return render_template('register_admin.html')


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
