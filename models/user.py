from config import Config

class User:
    def __init__(self, id, nombre, email, password, rol):
        self.id = id
        self.nombre = nombre
        self.email = email
        self.password = password
        self.rol = rol

    @staticmethod
    def get_user_by_email(email):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            return User(*user_data)
        return None

    @staticmethod
    def create_user(nombre, email, password, rol):
        conn = Config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (%s, %s, %s, %s)", 
                       (nombre, email, password, rol))
        conn.commit()
        cursor.close()
        conn.close()
