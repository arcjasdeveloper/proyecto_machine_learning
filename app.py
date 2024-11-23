import base64
import dlib
from datetime import datetime
from io import BytesIO
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import mysql.connector
import os
import face_recognition
from werkzeug.utils import secure_filename
from models.Pedidos import Pedidos
from models.Detalles_Pedido import DetallePedido

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'warehouse'
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


UPLOAD_FOLDER = 'static/uploads/faces'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/uploads/products', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def decode_image(image_data):
    image_data = image_data.split(",")[1]
    image = Image.open(BytesIO(base64.b64decode(image_data)))
    return np.array(image)


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')
@app.route('/settings')
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('settings.html',
                         user_name=session['user_name'],
                         user_role=session['user_role'],
                         user_image=get_user_image(session['user_id']))
@app.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute('SELECT role FROM users WHERE id = %s', (session['user_id'],))
        current_user = cursor.fetchone()
        cursor.execute('''
            SELECT 
                u.*,
                MAX(l.login_time) as last_login
            FROM users u
            LEFT JOIN login_history l ON u.id = l.user_id
            GROUP BY u.id
            ORDER BY u.name
        ''')
        users = cursor.fetchall()

        # Procesar las fechas y rutas de imágenes
        for user in users:
            user['created_at'] = user['created_at'].strftime('%d/%m/%Y %H:%M')
            if user['last_login']:
                user['last_login'] = user['last_login'].strftime('%d/%m/%Y %H:%M')
            # Convertir la ruta de la imagen a relativa
            if user['face_image_path']:
                user['face_image_path'] = user['face_image_path'].replace('static/', '')

        return render_template('users.html', users=users)

    except mysql.connector.Error as err:
        flash(f'Error al obtener usuarios: {err}', 'error')
        return redirect(url_for('dashboard'))
    finally:
        conn.close()


@app.route('/api/users', methods=['POST'])
def create_user():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verificar si es administrador
        cursor.execute('SELECT role FROM users WHERE id = %s', (session['user_id'],))
        if cursor.fetchone()['role'] != 'admin':
            return jsonify({'success': False, 'message': 'No autorizado'}), 403

        data = request.get_json()
        required_fields = ['name', 'email', 'password', 'role']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Faltan campos requeridos'}), 400

        cursor.execute('SELECT id FROM users WHERE email = %s', (data['email'],))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'El email ya está registrado'}), 400

        cursor.execute('''
            INSERT INTO users (name, email, password, role, active, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        ''', (data['name'], data['email'], data['password'], data['role'], data.get('active', 1)))

        conn.commit()
        return jsonify({'success': True, 'message': 'Usuario creado exitosamente'})

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method != 'GET' or user_id != session['user_id']:
            cursor.execute('SELECT role FROM users WHERE id = %s', (session['user_id'],))
            if cursor.fetchone()['role'] != 'admin':
                return jsonify({'success': False, 'message': 'No autorizado'}), 403

        if request.method == 'GET':
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            if user:
                del user['password']
                del user['face_encoding']
                return jsonify(user)
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404

        elif request.method == 'PUT':
            data = request.get_json()

            if data.get('role') == 'user' or not data.get('active', True):
                cursor.execute('SELECT COUNT(*) as admin_count FROM users WHERE role = "admin" AND active = 1')
                if cursor.fetchone()['admin_count'] <= 1:
                    return jsonify({'success': False,
                                    'message': 'No se puede modificar el último administrador activo'}), 400

            update_fields = []
            params = []
            for field in ['name', 'email', 'role']:
                if field in data:
                    update_fields.append(f'{field} = %s')
                    params.append(data[field])

            if 'password' in data and data['password']:
                update_fields.append('password = %s')
                params.append(data['password'])

            if 'active' in data:
                update_fields.append('active = %s')
                params.append(data['active'])

            params.append(user_id)

            query = f'''
                UPDATE users 
                SET {', '.join(update_fields)}
                WHERE id = %s
            '''

            cursor.execute(query, params)
            conn.commit()

            return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente'})

        elif request.method == 'DELETE':
            cursor.execute('''
                SELECT COUNT(*) as admin_count 
                FROM users 
                WHERE role = 'admin' AND active = 1 AND id != %s
            ''', (user_id,))

            if cursor.fetchone()['admin_count'] == 0:
                return jsonify({'success': False,
                                'message': 'No se puede eliminar el último administrador'}), 400

            cursor.execute('UPDATE users SET active = 0 WHERE id = %s', (user_id,))
            conn.commit()

            return jsonify({'success': True, 'message': 'Usuario desactivado exitosamente'})

    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': str(err)}), 500
    finally:
        conn.close()
def get_user_image(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT face_image_path FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return os.path.basename(user['face_image_path']) if user and user['face_image_path'] else 'default.jpg'

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        if 'face_image_data' not in request.form or not request.form['face_image_data']:
            flash('No facial image provided', 'error')
            return redirect(request.url)

        face_image_data = request.form['face_image_data']
        image_data = base64.b64decode(face_image_data.split(",")[1])
        image = Image.open(BytesIO(image_data))

        # Save image file
        filename = secure_filename(f"{email}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)

        # Process face recognition
        image_np = np.array(image)
        face_locations = face_recognition.face_locations(image_np)

        if not face_locations:
            os.remove(filepath)
            flash('No face detected in the image', 'error')
            return redirect(request.url)

        face_encoding = face_recognition.face_encodings(image_np, face_locations)[0]

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (name, email, password, role, face_encoding, face_image_path)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, email, password, role, ','.join(map(str, face_encoding)), filepath))
            conn.commit()
            flash('Registration successful', 'success')
            return redirect(url_for('login_page'))
        except mysql.connector.Error as err:
            flash(f'Registration error: {err}', 'error')
            if os.path.exists(filepath):
                os.remove(filepath)
            return redirect(request.url)
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@app.route('/face_login', methods=['POST'])
def face_login():
    face_image_data = request.form['face_image_data']
    image_np = decode_image(face_image_data)

    face_locations = face_recognition.face_locations(image_np)
    if not face_locations:
        return jsonify({
            'success': False,
            'face_detected': False,
            'message': 'No se detectó rostro'
        })

    login_encoding = face_recognition.face_encodings(image_np, face_locations)[0]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE face_encoding IS NOT NULL')
    users = cursor.fetchall()
    conn.close()

    for user in users:
        stored_encoding = np.array([float(x) for x in user['face_encoding'].split(',')])
        if face_recognition.compare_faces([stored_encoding], login_encoding, tolerance=0.6)[0]:
            # Guardar datos en la sesión
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['user_image'] = os.path.basename(user['face_image_path']) if user[
                'face_image_path'] else 'default.jpg'

            return jsonify({
                'success': True,
                'redirect': url_for('dashboard'),
                'message': 'Login exitoso'
            })

    return jsonify({
        'success': False,
        'face_detected': True,
        'match': False,
        'message': 'Rostro no reconocido'
    })


@app.route('/traditional_login', methods=['POST'])
def traditional_login():
    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        # Guardar datos en la sesión
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        # Guardar la imagen en la sesión
        session['user_image'] = os.path.basename(user['face_image_path']) if user['face_image_path'] else 'default.jpg'

        flash('Login successful', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid credentials', 'error')
        return redirect(url_for('login_page'))

@app.before_request
def load_user_data():
    if 'user_id' in session and ('user_name' not in session or 'user_image' not in session):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT name, role, face_image_path 
                FROM users 
                WHERE id = %s
            ''', (session['user_id'],))
            user = cursor.fetchone()
            if user:
                session['user_name'] = user['name']
                session['user_role'] = user['role']
                session['user_image'] = os.path.basename(user['face_image_path']) if user['face_image_path'] else 'default.jpg'
        except Exception as e:
            print(f"Error loading user data: {e}")
        finally:
            if 'conn' in locals():
                conn.close()
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get user data
    cursor.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
    user = cursor.fetchone()

    # Get statistics
    cursor.execute('SELECT COUNT(*) as total FROM products WHERE active = true')
    total_products = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM users')
    total_users = cursor.fetchone()['total']

    # Get low stock products
    cursor.execute('SELECT * FROM low_stock_products LIMIT 5')
    low_stock_products = cursor.fetchall()

    # Get recent products
    cursor.execute('''
        SELECT p.*, c.name as category_name 
        FROM products p 
        JOIN categories c ON p.category_id = c.id 
        WHERE p.active = true
        ORDER BY p.created_at DESC 
        LIMIT 5
    ''')
    recent_products = cursor.fetchall()

    # Get inventory value
    cursor.execute('SELECT * FROM inventory_value')
    inventory_stats = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html',
                           user_name=user['name'],
                           user_role=user['role'],
                           user_image=os.path.basename(user['face_image_path']),
                           total_products=total_products,
                           total_users=total_users,
                           low_stock_products=low_stock_products,
                           recent_products=recent_products,
                           inventory_stats=inventory_stats)


@app.route('/products', methods=['GET'])
def list_products():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', '')
        category_id = request.args.get('category_id', '')
        sort_by = request.args.get('sort_by', 'name')
        order = request.args.get('order', 'asc')

        query = '''
            SELECT 
                p.*,
                c.name as category_name,
                COALESCE(SUM(CASE WHEN m.movement_type = 'in' THEN m.quantity ELSE -m.quantity END), 0) as current_stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN inventory_movements m ON p.id = m.product_id
        '''
        count_query = 'SELECT COUNT(*) as total FROM products p'
        where_clauses = ['p.active = true']
        params = []

        if search:
            where_clauses.append('(p.name LIKE %s OR p.code LIKE %s OR p.description LIKE %s)')
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])

        if category_id:
            where_clauses.append('p.category_id = %s')
            params.append(category_id)

        if where_clauses:
            query += ' WHERE ' + ' AND '.join(where_clauses)
            count_query += ' WHERE ' + ' AND '.join(where_clauses)

        query += ' GROUP BY p.id'

        valid_sort_columns = ['name', 'code', 'current_stock', 'purchase_price', 'sale_price', 'created_at']
        if sort_by not in valid_sort_columns:
            sort_by = 'name'

        order = 'asc' if order.lower() != 'desc' else 'desc'
        query += f' ORDER BY {sort_by} {order}'

        offset = (page - 1) * per_page
        query += ' LIMIT %s OFFSET %s'
        params.extend([per_page, offset])

        cursor.execute(count_query, params[:-2])
        total_products = cursor.fetchone()['total']

        cursor.execute(query, params)
        products = cursor.fetchall()

        total_pages = (total_products + per_page - 1) // per_page

        cursor.execute('SELECT id, name FROM categories WHERE active = true ORDER BY name')
        categories = cursor.fetchall()

        cursor.execute('''
            SELECT 
                COUNT(*) as total_products,
                SUM(CASE WHEN stock <= minimum_stock THEN 1 ELSE 0 END) as low_stock_count,
                SUM(stock * purchase_price) as total_inventory_value
            FROM products 
            WHERE active = true
        ''')
        stats = cursor.fetchone()

        for product in products:
            product['stock_status'] = 'low' if product['current_stock'] <= product['minimum_stock'] else 'normal'

            if product['purchase_price'] > 0:
                product['profit_margin'] = ((product['sale_price'] - product['purchase_price']) / product[
                    'purchase_price']) * 100
            else:
                product['profit_margin'] = 0

            product['created_at'] = product['created_at'].strftime('%d/%m/%Y %H:%M')
            if product['updated_at']:
                product['updated_at'] = product['updated_at'].strftime('%d/%m/%Y %H:%M')

        return render_template('products/list.html',
                               products=products,
                               categories=categories,
                               stats=stats,
                               pagination={
                                   'page': page,
                                   'per_page': per_page,
                                   'total_pages': total_pages,
                                   'total_products': total_products
                               },
                               filters={
                                   'search': search,
                                   'category_id': category_id,
                                   'sort_by': sort_by,
                                   'order': order
                               })

    except mysql.connector.Error as err:
        flash(f'Error al obtener los productos: {err}', 'error')
        return redirect(url_for('dashboard'))

    finally:
        conn.close()


@app.route('/api/products/search', methods=['GET'])
def search_products():
    """API endpoint para búsqueda en tiempo real de productos"""
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    try:
        search = request.args.get('q', '')
        category_id = request.args.get('category_id', '')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = '''
            SELECT 
                p.id, p.code, p.name, p.stock, p.minimum_stock,
                c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.active = true
        '''
        params = []

        if search:
            query += ' AND (p.name LIKE %s OR p.code LIKE %s)'
            search_param = f'%{search}%'
            params.extend([search_param, search_param])

        if category_id:
            query += ' AND p.category_id = %s'
            params.append(category_id)

        query += ' LIMIT 10'  # Limitar resultados para mejor rendimiento

        cursor.execute(query, params)
        products = cursor.fetchall()

        return jsonify({
            'results': products
        })

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        conn.close()


@app.route('/api/products/export', methods=['GET'])
def export_products():
    #Endpoint para exportar productos a Excel
    if 'user_id' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    try:
        import pandas as pd
        from io import BytesIO

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Obtener todos los productos con sus categorías
        cursor.execute('''
            SELECT 
                p.code, p.name, c.name as category, p.description,
                p.stock, p.minimum_stock, p.purchase_price, p.sale_price,
                p.created_at, p.updated_at,
                CASE WHEN p.active THEN 'Activo' ELSE 'Inactivo' END as status
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.name
        ''')
        products = cursor.fetchall()

        # Crear DataFrame
        df = pd.DataFrame(products)

        # Crear archivo Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Productos', index=False)

            # Dar formato al archivo
            workbook = writer.book
            worksheet = writer.sheets['Productos']

            # Formatos
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4B5563',
                'font_color': 'white'
            })

            # Aplicar formatos
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'productos_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        conn.close()

@app.route('/products/create', methods=['GET', 'POST'])
def create_product():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            code = request.form['code']
            name = request.form['name']
            description = request.form.get('description', '')
            category_id = int(request.form['category_id'])
            purchase_price = float(request.form['purchase_price'])
            sale_price = float(request.form['sale_price'])
            stock = int(request.form['stock'])
            minimum_stock = int(request.form['minimum_stock'])

            # Procesar imagen si existe
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(
                        f"product_{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file.filename.rsplit('.', 1)[1].lower()}")
                    filepath = os.path.join('static/uploads/products', filename)

                    # Asegurar que el directorio existe
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)

                    # Guardar y optimizar imagen
                    image = Image.open(file)
                    image.thumbnail((800, 800))  # Redimensionar si es muy grande
                    image.save(filepath, quality=85, optimize=True)
                    image_path = filepath

            conn = get_db_connection()
            cursor = conn.cursor()

            # Verificar si el código ya existe
            cursor.execute('SELECT id FROM products WHERE code = %s', (code,))
            if cursor.fetchone():
                flash('El código del producto ya existe', 'error')
                return redirect(request.url)

            # Insertar el producto
            cursor.execute('''
                INSERT INTO products (code, name, description, category_id, 
                                    purchase_price, sale_price, stock, 
                                    minimum_stock, image, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ''', (code, name, description, category_id, purchase_price,
                  sale_price, stock, minimum_stock, image_path))

            # Registrar el movimiento inicial de stock
            product_id = cursor.lastrowid
            if stock > 0:
                cursor.execute('''
                    INSERT INTO inventory_movements (product_id, movement_type, 
                                                   quantity, user_id, description)
                    VALUES (%s, 'in', %s, %s, %s)
                ''', (product_id, stock, session['user_id'], 'Stock inicial'))

            conn.commit()
            flash('Producto creado exitosamente', 'success')
            return redirect(url_for('list_products'))

        except mysql.connector.Error as err:
            flash(f'Error al crear el producto: {err}', 'error')
            return redirect(request.url)

        except Exception as e:
            flash(f'Error inesperado: {e}', 'error')
            return redirect(request.url)

        finally:
            conn.close()

    # GET request - mostrar formulario
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT id, name FROM categories WHERE active = true ORDER BY name')
    categories = cursor.fetchall()
    conn.close()

    return render_template('products/create.html', categories=categories)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

from datetime import datetime
import uuid

# Ruta para listar pedidos
@app.route('/listar_pedidos', methods=['GET'])
def listar_pedidos():
    pedidos = Pedidos.obtener_todos()  # Obtener todos los pedidos
    return render_template('Pedidos/listar_pedidos.html', pedidos=pedidos)

# Ruta para crear nuevo pedido
@app.route('/pedidos/nuevo', methods=['GET', 'POST'])
def nuevo_pedido():
    if request.method == 'POST':
        nombre_cliente = request.form['nombre_cliente']
        codigo_pedido = request.form['codigo']
        tipo_documento = request.form['tipo_documento']
        dni = request.form['dni'] if tipo_documento == 'dni' else None
        ruc = request.form['ruc'] if tipo_documento == 'ruc' else None
        estado_pedido = request.form['estado_pedido']
        total_pedido = float(request.form['total_pedido'])
        direccion_envio = request.form['direccion_envio']
        metodo_pago = request.form['metodo_pago']
        id_vendedor = int(request.form['id_vendedor'])
        observaciones = request.form['observaciones']

        # Generar el código automáticamente si no se pasa
        #codigo = str(uuid.uuid4())[:5]
        fecha_pedido = datetime.now()  # Obtener la fecha actual

        # Crear el objeto de pedido
        pedido = Pedidos(nombre_cliente=nombre_cliente, tipo_documento=tipo_documento, dni=dni, ruc=ruc, estado_pedido=estado_pedido, total_pedido=total_pedido, direccion_envio=direccion_envio, metodo_pago=metodo_pago,
            id_vendedor=id_vendedor, observaciones=observaciones, codigo=codigo_pedido, fecha_pedido=fecha_pedido
        )
        pedido.guardar()

        flash('Pedido creado exitosamente')
        return redirect(url_for('listar_pedidos'))  

    return render_template('Pedidos/nuevo_pedido.html')

@app.route('/pedidos/editar/<int:id_pedido>', methods=['GET', 'POST'])
def editar_pedido(id_pedido):
    # Obtener el pedido actual por su ID
    pedido_actual = Pedidos.obtener_por_id(id_pedido)
    if not pedido_actual:
        return "Pedido no encontrado", 404

    if request.method == 'POST':
        # Obtener los datos del formulario
        nombre_cliente = request.form.get('nombre_cliente')
        tipo_documento = request.form.get('tipo_documento')
        dni = request.form.get('dni') if tipo_documento == 'dni' else None
        ruc = request.form.get('ruc') if tipo_documento == 'ruc' else None
        estado_pedido = request.form.get('estado_pedido')
        total_pedido = request.form.get('total_pedido')
        direccion_envio = request.form.get('direccion_envio')
        metodo_pago = request.form.get('metodo_pago')
        id_vendedor = request.form.get('id_vendedor')
        observaciones = request.form.get('observaciones')

        # Validar los datos ingresados
        if not nombre_cliente or not tipo_documento or not estado_pedido or not total_pedido or not direccion_envio or not metodo_pago or not id_vendedor:
            flash("Todos los campos son obligatorios", "error")
            return redirect(request.url)

        try:
            # Convertir datos donde sea necesario
            total_pedido = float(total_pedido)
            id_vendedor = int(id_vendedor)

            # Crear un objeto con los datos actualizados
            pedido = Pedidos(
                id_pedido=id_pedido,
                nombre_cliente=nombre_cliente,
                tipo_documento=tipo_documento,
                dni=dni,
                ruc=ruc,
                estado_pedido=estado_pedido,
                total_pedido=total_pedido,
                direccion_envio=direccion_envio,
                metodo_pago=metodo_pago,
                id_vendedor=id_vendedor,
                observaciones=observaciones
            )

            # Llamar al método actualizar() sobre la instancia del pedido
            pedido.actualizar()

            flash("Pedido actualizado exitosamente", "success")
            return redirect(url_for('listar_pedidos'))  # Redirigir a la lista de pedidos

        except ValueError:
            flash("Total del pedido y Vendedor deben ser valores numéricos válidos", "error")
            return redirect(request.url)

    return render_template('Pedidos/editar_pedido.html', pedido=pedido_actual)



# Ruta para eliminar pedido
@app.route('/pedidos/eliminar/<int:id_pedido>')
def eliminar_pedido(id_pedido):
    Pedidos.eliminar(id_pedido)
    flash('Pedido eliminado exitosamente')
    return redirect(url_for('listar_pedidos'))

# Ruta para listar los detalles del pedido
@app.route('/detalle_pedido/<int:id_pedido>', methods=['GET'])
def listar_detalles(id_pedido):
    detalles = DetallePedido.obtener_por_pedido(id_pedido)
    return render_template('Detalles_Pedido/listar_detalles.html', detalles=detalles, id_pedido=id_pedido)


# Ruta para agregar un nuevo detalle de pedido
@app.route('/detalle_pedido/nuevo/<int:id_pedido>', methods=['GET', 'POST'])
def nuevo_detalle(id_pedido):
    if request.method == 'POST':
        id_producto = request.form['id_producto']
        cantidad = request.form['cantidad']
        precio_unitario = request.form['precio_unitario']
        
        # Crear el detalle del pedido
        detalle = DetallePedido(id_detalle=None, id_pedido=id_pedido, id_producto=id_producto, cantidad=cantidad, precio_unitario=precio_unitario)
        detalle.guardar()
        
        flash('Detalle de pedido creado exitosamente')
        
        # Redirigir a la lista de detalles con el id_pedido
        return redirect(url_for('listar_detalles', id_pedido=id_pedido))
    
    return render_template('Detalles_Pedido/nuevo_detalle.html', id_pedido=id_pedido)

# Ruta para editar un detalle de pedido
@app.route('/detalle_pedido/editar/<int:id_detalle>', methods=['GET', 'POST'])
def editar_detalle(id_detalle):
    # Obtener el detalle actual por su ID
    detalle_actual = DetallePedido.obtener_detalle_por_id(id_detalle)
    if not detalle_actual:
        return "Detalle no encontrado", 404

    if request.method == 'POST':
        # Obtener datos del formulario
        cantidad = request.form.get('cantidad')
        precio_unitario = request.form.get('precio_unitario')

        # Validar los datos ingresados
        if not cantidad or not precio_unitario:
            flash("Todos los campos son obligatorios", "error")
            return redirect(request.url)

        try:
            cantidad = int(cantidad)
            precio_unitario = float(precio_unitario)

            # Crear un objeto con los datos actualizados
            detalle = DetallePedido(
                id_detalle=id_detalle,
                id_pedido=detalle_actual['id_pedido'], 
                id_producto=detalle_actual['id_producto'], 
                cantidad=cantidad,
                precio_unitario=precio_unitario
            )
            detalle.actualizar()
            flash("Detalle actualizado exitosamente", "success")
            return redirect(f"/detalle_pedido/{detalle_actual['id_pedido']}") 
        except ValueError:
            flash("Cantidad y precio deben ser números válidos", "error")
            return redirect(request.url)

    return render_template('Detalles_Pedido/editar_detalle.html', detalle=detalle_actual)

# Ruta para eliminar un detalle de pedido
@app.route('/detalle_pedido/eliminar/<int:id_detalle>')
def eliminar_detalle(id_detalle):
    DetallePedido.eliminar(id_detalle) 
    flash('Detalle del pedido eliminado exitosamente') 
    return redirect(url_for('listar_detalles', id_pedido=request.args.get('id_pedido')))

if __name__ == '__main__':
    app.run(debug=True)