import mysql.connector
from config import Config

class DetallePedido:
    def __init__(self, id_detalle, id_pedido, id_producto, cantidad, precio_unitario):
        self.id_detalle = id_detalle
        self.id_pedido = id_pedido
        self.id_producto = id_producto
        self.cantidad = int(cantidad)
        self.precio_unitario = float(precio_unitario)

    @staticmethod
    def obtener_por_pedido(id_pedido):
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM detalle_pedido WHERE id_pedido=%s", (id_pedido,))
        detalles = cursor.fetchall()
        db.close()
        return detalles

    def guardar(self):
        db = Config.get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO detalle_pedido (id_pedido, id_producto, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s)
        """, (self.id_pedido, self.id_producto, self.cantidad, self.precio_unitario))
        db.commit()
        db.close()

    def actualizar(self):
        db = Config.get_db_connection()
        cursor = db.cursor()
        # Eliminamos el campo 'subtotal' del UPDATE
        cursor.execute("""
            UPDATE detalle_pedido
            SET cantidad = %s, precio_unitario = %s
            WHERE id_detalle = %s
        """, (self.cantidad, self.precio_unitario, self.id_detalle))
        db.commit()
        db.close()

    @staticmethod
    def obtener_detalle_por_id(id_detalle):
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM detalle_pedido WHERE id_detalle=%s", (id_detalle,))
        detalle = cursor.fetchone()
        db.close()
        return detalle
    
    @staticmethod
    def eliminar(id_detalle):
        conexion = Config.get_db_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute("DELETE FROM detalle_pedido WHERE id_detalle = %s", (id_detalle,))
            conexion.commit()
        except Exception as e:
            conexion.rollback()
            raise e
        finally:
            cursor.close() 
            conexion.close()
