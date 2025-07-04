import os
import cv2
import base64
from PIL import Image
from io import BytesIO
from flask import Flask, request, redirect, url_for, flash, jsonify, render_template
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import face_recognition
import numpy as np
import traceback

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static', 'known_faces')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.getcwd(), 'expositores.db')
app.secret_key = 'clave_secreta'
db = SQLAlchemy(app)

class Expositor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    empresa = db.Column(db.String(100))
    imagen_path = db.Column(db.String(200), nullable=False)
    face_encoding = db.Column(db.PickleType, nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

@app.route('/')
def index():
    return redirect(url_for('recognize_page'))

@app.route('/recognize')
def recognize_page():
    return render_template('recognize.html')

@app.route('/testcam')
def testcam():
    return render_template('testcam.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            email = request.form['email']
            empresa = request.form['empresa']

            if Expositor.query.filter_by(email=email).first():
                flash('Este email ya está registrado', 'error')
                return redirect(request.url)

            biometric_data = request.form.get('foto')
            if not biometric_data:
                flash('No se recibió imagen base64', 'error')
                return redirect(request.url)

            if 'base64,' in biometric_data:
                biometric_data = biometric_data.split('base64,')[1]

            image_data = base64.b64decode(biometric_data)
            image = Image.open(BytesIO(image_data)).convert('RGB')

            filename = f"{email}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)

            img_bgr = cv2.imread(filepath)
            if img_bgr is None:
                flash('Error al leer la imagen. Intente con otra.', 'error')
                return redirect(request.url)

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            face_encodings = face_recognition.face_encodings(img_rgb)

            if not face_encodings:
                os.remove(filepath)
                flash('No se detectó rostro', 'error')
                return redirect(request.url)

            nuevo_expositor = Expositor(
                nombre=nombre,
                email=email,
                empresa=empresa,
                imagen_path=filepath,
                face_encoding=face_encodings[0]
            )
            db.session.add(nuevo_expositor)
            db.session.commit()

            flash(f'Registro exitoso para {nombre}', 'success')
            return redirect(url_for('register'))

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('register.html')

@app.route('/recognize', methods=['POST'])
def recognize():
    print("📸 Solicitud recibida en /recognize")

    if 'foto' not in request.files:
        return jsonify({'acceso': False, 'error': 'No se recibió imagen'}), 400

    file = request.files['foto']
    if file.filename == '':
        return jsonify({'acceso': False, 'error': 'Archivo vacío'}), 400

    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_face.jpg')
    file.save(temp_path)

    try:
        img_bgr = cv2.imread(temp_path)
        if img_bgr is None:
            raise ValueError('No se pudo leer la imagen con OpenCV')

        if len(img_bgr.shape) != 3 or img_bgr.shape[2] != 3:
            raise ValueError('La imagen no tiene 3 canales (RGB)')

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        unknown_encoding = face_recognition.face_encodings(img_rgb)

        if not unknown_encoding:
            raise ValueError('No se detectó un rostro en la imagen')

        expositores = Expositor.query.all()
        for expositor in expositores:
            match = face_recognition.compare_faces([np.array(expositor.face_encoding)], unknown_encoding[0])[0]
            if match:
                return jsonify({
                    'acceso': True,
                    'nombre': expositor.nombre,
                    'empresa': expositor.empresa
                })

        return jsonify({'acceso': False, 'mensaje': 'No reconocido'}), 200

    except Exception as e:
        return jsonify({'acceso': False, 'error': str(e)}), 500

    finally:
        try:
            os.remove(temp_path)
        except Exception as cleanup_error:
            print(f"⚠️ Error al eliminar el archivo temporal: {cleanup_error}")




@app.route('/lista_expositores')
def lista_expositores():
    expositores = Expositor.query.all()
    return render_template('expositores.html', expositores=expositores)


@app.route('/expositor/<int:id>/eliminar', methods=['POST'])
def eliminar_expositor(id):
    expositor = Expositor.query.get_or_404(id)
    try:
        if os.path.exists(expositor.imagen_path):
            os.remove(expositor.imagen_path)
        db.session.delete(expositor)
        db.session.commit()
        flash('Expositor eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error eliminando expositor: {str(e)}', 'error')
    return redirect(url_for('lista_expositores'))

@app.route('/expositor/<int:id>/editar', methods=['GET', 'POST'])
def editar_expositor(id):
    expositor = Expositor.query.get_or_404(id)
    if request.method == 'POST':
        try:
            expositor.nombre = request.form['nombre']
            expositor.empresa = request.form['empresa']
            db.session.commit()
            flash('Datos actualizados correctamente', 'success')
            return redirect(url_for('lista_expositores'))
        except Exception as e:
            flash(f'Error actualizando datos: {str(e)}', 'error')
    return render_template('editar_expositor.html', expositor=expositor)

@app.route('/upload', methods=['GET', 'POST'])
def upload_test():
    if request.method == 'POST':
        file = request.files['foto']
        file.save('static/test.jpg')
        return "Guardado"
    return '''<form method="POST" enctype="multipart/form-data">
                <input type="file" name="foto">
                <button type="submit">Subir</button>
              </form>'''

@app.route('/test_db')
def test_db():
    try:
        count = Expositor.query.count()
        return f"Total de registros: {count}"
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
