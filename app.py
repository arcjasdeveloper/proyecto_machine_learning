from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename
from models.user import User
from models.product import Product
from utils.face_recognition import recognize_face

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'  # Cambia esto por una clave secreta más segura

# Configuración de la base de datos
def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',  # Por defecto, el usuario es 'root'
        password='',  # La contraseña está vacía por defecto
        database='almacen'  # Reemplaza con el nombre de tu base de datos
    )
    return connection

# Configuración para la carga de imágenes
UPLOAD_FOLDER = 'static/img/faces'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.get_user_by_email(email)
        if user and user.password == password:  # Asegúrate de encriptar las contraseñas en producción
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciales inválidas', 'danger')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        rol = request.form['rol']

        # Manejo de la imagen del rostro
        if 'face_image' not in request.files:
            flash('No se subió ninguna imagen', 'danger')
            return redirect(url_for('register'))
        
        file = request.files['face_image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Guardar el usuario en la base de datos
            User.create_user(nombre, email, password, rol)

            flash('Usuario registrado exitosamente', 'success')
            return redirect(url_for('login'))
        else:
            flash('Formato de imagen no permitido', 'danger')
    return render_template('auth/register.html')

@app.route('/recognize', methods=['POST'])
def recognize():
    if request.method == 'POST':
        # Aquí deberías manejar la lógica para recibir la imagen y procesarla
        # Por simplicidad, asumimos que se sube una imagen y se procesa
        uploaded_file = request.files['face_image']
        if uploaded_file and allowed_file(uploaded_file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(uploaded_file.filename))
            uploaded_file.save(filepath)

            # Aquí deberías tener una lista de codificaciones de rostros conocidos
            known_face_encodings = []  # Lista de codificaciones de rostros conocidos
            known_face_names = []       # Lista de nombres de rostros conocidos

            # Lógica para reconocer la cara
            name = recognize_face(filepath, known_face_encodings, known_face_names)

            flash(f'Rostro reconocido: {name}', 'success')
            return redirect(url_for('index'))
        else:
            flash('Formato de imagen no permitido', 'danger')
    return redirect(url_for('index'))

@app.route('/products', methods=['GET'])
def list_products():
    products = Product.get_all_products()
    return render_template('products/list.html', products=products)

@app.route('/products/create', methods=['GET', 'POST'])
def create_product():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        codigo_barras = request.form['codigo_barras']
        imagen = request.form['imagen']  # Aquí deberías manejar la carga de la imagen

        Product.create_product(nombre, descripcion, categoria, codigo_barras, imagen)
        flash('Producto creado exitosamente', 'success')
        return redirect(url_for('list_products'))
    
    return render_template('products/create.html')

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.get_product_by_id(product_id)
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        codigo_barras = request.form['codigo_barras']
        imagen = request.form['imagen']  # Aquí deberías manejar la carga de la imagen

        Product.update_product(product_id, nombre, descripcion, categoria, codigo_barras, imagen)
        flash('Producto actualizado exitosamente', 'success')
        return redirect(url)
@app.route('/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    Product.delete_product(product_id)
    flash('Producto eliminado exitosamente', 'success')
    return redirect(url_for('list_products'))

if __name__ == '__main__':
    app.run(debug=True)