from datetime import datetime
import mysql
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
    def obtener_todos():
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM products")
        productos = cursor.fetchall()
        db.close()
        return productos
