import face_recognition
import cv2
import numpy as np

def recognize_face(image_path, known_face_encodings, known_face_names):
    # Cargar la imagen y convertirla a una matriz de numpy
    unknown_image = face_recognition.load_image_file(image_path)
    unknown_face_encodings = face_recognition.face_encodings(unknown_image)

    # Verificar si se encontró algún rostro
    if len(unknown_face_encodings) > 0:
        unknown_face_encoding = unknown_face_encodings[0]

        # Comparar con los rostros conocidos
        matches = face_recognition.compare_faces(known_face_encodings, unknown_face_encoding)
        name = "Desconocido"

        # Si hay una coincidencia, obtener el nombre
        if True in matches:
            first_match_index = matches.index(True)
            name = known_face_names[first_match_index]

        return name
    else:
        return "No se detectó rostro"