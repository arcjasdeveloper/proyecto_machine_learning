from config import Config

class Product:
    def __init__(self, id, nombre, descripcion, categoria, codigo_barras, imagen):
        self.id = id
        self.nombre = nombre
        self.descripcion = descripcion
        self.categoria = categoria
        self.codigo_barras = codigo_barras
        self.imagen = imagen

    @staticmethod
    def create_product(nombre, descripcion, categoria, codigo_barras, imagen):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        query = "INSERT INTO productos (nombre, descripcion, categoria, codigo_barras, imagen) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (nombre, descripcion, categoria, codigo_barras, imagen))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def get_all_products():
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos")
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        return products
    
    @staticmethod
    def obtener_todos():
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM products")
        productos = cursor.fetchall()
        db.close()
        return productos

    @staticmethod
    def get_product_by_id(product_id):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM productos WHERE id = %s", (product_id,))
        product = cursor.fetchone()
        cursor.close()
        conn.close()
        return product

    @staticmethod
    def update_product(product_id, nombre, descripcion, categoria, codigo_barras, imagen):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        query = "UPDATE productos SET nombre = %s, descripcion = %s, categoria = %s, codigo_barras = %s, imagen = %s WHERE id = %s"
        cursor.execute(query, (nombre, descripcion, categoria, codigo_barras, imagen, product_id))
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def delete_product(product_id):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM productos WHERE id = %s", (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
