from datetime import datetime
import uuid
from config import Config

class Pedidos:
    contador = 0
    def __init__(self, id_pedido=None, nombre_cliente=None, tipo_documento=None, dni=None, ruc=None, estado_pedido=None, total_pedido=None, direccion_envio=None, metodo_pago=None, id_vendedor=None, observaciones=None, codigo=None, fecha_pedido=None):
        self.id_pedido = id_pedido
        self.nombre_cliente = nombre_cliente
        self.tipo_documento = tipo_documento
        self.dni = dni
        self.ruc = ruc
        self.estado_pedido = estado_pedido
        self.total_pedido = total_pedido
        self.direccion_envio = direccion_envio
        self.metodo_pago = metodo_pago
        self.id_vendedor = id_vendedor
        self.observaciones = observaciones
        self.codigo = codigo 
        self.fecha_pedido = fecha_pedido or datetime.now()

    @staticmethod
    def obtener_todos():
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, GROUP_CONCAT(pr.name SEPARATOR ', ') AS productos
            FROM pedidos p
            LEFT JOIN detalle_pedido dp ON p.id_pedido = dp.id_pedido
            LEFT JOIN products pr ON dp.id_producto = pr.id
            GROUP BY p.id_pedido
        """)
        pedidos = cursor.fetchall()
        db.close()
        return pedidos

    @staticmethod
    def obtener_productos_por_pedido(id_pedido):
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT pr.name
            FROM detalle_pedido dp
            JOIN products pr ON dp.id_producto = pr.id
            WHERE dp.id_pedido = %s
        """, (id_pedido,))
        productos = cursor.fetchall()
        db.close()
        return productos

    def guardar(self):
        db = Config.get_db_connection()
        cursor = db.cursor()
        print(f"Guardando pedido: {self.nombre_cliente}, {self.total_pedido}, {self.fecha_pedido}")  # Depuración
        try:
            if self.tipo_documento == 'dni':
                cursor.execute("""
                    INSERT INTO pedidos (codigo, nombre_cliente, tipo_documento, dni, estado_pedido, total_pedido, direccion_envio, metodo_pago, id_vendedor, observaciones, fecha_pedido)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.codigo, self.nombre_cliente, self.tipo_documento, self.dni, self.estado_pedido, self.total_pedido, self.direccion_envio, self.metodo_pago, self.id_vendedor, self.observaciones, self.fecha_pedido))
            elif self.tipo_documento == 'ruc':
                cursor.execute("""
                    INSERT INTO pedidos (codigo, nombre_cliente, tipo_documento, ruc, estado_pedido, total_pedido, direccion_envio, metodo_pago, id_vendedor, observaciones, fecha_pedido)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.codigo, self.nombre_cliente, self.tipo_documento, self.ruc, self.estado_pedido, self.total_pedido, self.direccion_envio, self.metodo_pago, self.id_vendedor, self.observaciones, self.fecha_pedido))

            db.commit()
            print("Pedido guardado exitosamente.")
        except Exception as e:
            print(f"Error al guardar el pedido: {e}")
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def obtener_por_id(id_pedido):
        db = Config.get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pedidos WHERE id_pedido=%s", (id_pedido,))
        pedido = cursor.fetchone()
        db.close()
        return pedido

    def actualizar(self):
        db = Config.get_db_connection()
        cursor = db.cursor()

        if self.tipo_documento == 'dni':
            cursor.execute("""
                UPDATE pedidos
                SET nombre_cliente=%s, tipo_documento=%s, dni=%s, estado_pedido=%s, total_pedido=%s, direccion_envio=%s, metodo_pago=%s, id_vendedor=%s, observaciones=%s
                WHERE id_pedido=%s
            """, (self.nombre_cliente, self.tipo_documento, self.dni, self.estado_pedido, self.total_pedido, self.direccion_envio, self.metodo_pago, self.id_vendedor, self.observaciones, self.id_pedido))

        elif self.tipo_documento == 'ruc':
            cursor.execute("""
                UPDATE pedidos
                SET nombre_cliente=%s, tipo_documento=%s, ruc=%s, estado_pedido=%s, total_pedido=%s, direccion_envio=%s, metodo_pago=%s, id_vendedor=%s, observaciones=%s
                WHERE id_pedido=%s
            """, (self.nombre_cliente, self.tipo_documento, self.ruc, self.estado_pedido, self.total_pedido, self.direccion_envio, self.metodo_pago, self.id_vendedor, self.observaciones, self.id_pedido))

        db.commit()
        db.close()

    @staticmethod
    def eliminar(id_pedido):
        db = Config.get_db_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM pedidos WHERE id_pedido=%s", (id_pedido,))
        db.commit()
        db.close()
