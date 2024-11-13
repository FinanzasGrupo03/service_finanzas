from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import random
import uuid
import mysql.connector
from datetime import datetime
from mysql.connector import Error

app = Flask(__name__)


# Configuración de la base de datos MySQL
DATABASE_CONFIG = {
    'host': 'autorack.proxy.rlwy.net',
    'port': 26256,
    'user': 'root',
    'password': 'JrmuNrdqrVIiDlpAjOgNgeqBpudjqXbp',
    'database': 'railway'
}

# Función para conectar a la base de datos con manejo de errores
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        return conn
    except Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Función para inicializar las tablas
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        # Crear tabla boletas_libres si no existe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS boletas_libres (
                id INT AUTO_INCREMENT PRIMARY KEY,
                boleta_id VARCHAR(255),
                nombre VARCHAR(255),
                dni VARCHAR(20),
                empresa VARCHAR(255),
                ruc VARCHAR(20),
                fecha_emision DATE,
                fecha_vencimiento DATE,
                importe FLOAT,
                tipo_moneda VARCHAR(10)
            )
        ''')

        # Crear tabla boletas si no existe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS boletas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                boleta_id VARCHAR(255),
                banco_id VARCHAR(255),
                nombre VARCHAR(255),
                dni VARCHAR(20),
                empresa VARCHAR(255),
                ruc VARCHAR(20),
                fecha_emision DATE,
                fecha_vencimiento DATE,
                importe FLOAT,
                tea_compensatoria FLOAT,
                dias_calculados INT,
                te_compensatoria FLOAT,
                tasa_descuento FLOAT,
                valor_neto FLOAT,
                comision_estudios FLOAT,
                comision_activacion FLOAT,
                seguro_desgravamen FLOAT,
                costos_adicionales FLOAT,
                valor_recibido FLOAT,
                tcea FLOAT,
                tef_cartera FLOAT,
                tea_cartera FLOAT,
                tipo_moneda VARCHAR(10)
            )
        ''')

        # Crear tabla usuarios si no existe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INT AUTO_INCREMENT PRIMARY KEY,
                usuario VARCHAR(50) UNIQUE NOT NULL,
                contraseña VARCHAR(255) NOT NULL,
                nombres VARCHAR(100),
                apellidos VARCHAR(100),
                correo VARCHAR(100) UNIQUE
            )
        ''')

        conn.commit()
        cursor.close()
        conn.close()
        print("Tablas inicializadas correctamente.")
    else:
        print("No se pudo conectar a la base de datos para inicializar las tablas.")

# Inicializar la base de datos
init_db()

# Ruta para registrar un usuario
@app.route('/registrarte', methods=['POST'])
def registrarte():
    data = request.json
    usuario = data.get('usuario')
    contraseña = generate_password_hash(data.get('contraseña'))  # Encriptar la contraseña
    nombres = data.get('nombres')
    apellidos = data.get('apellidos')
    correo = data.get('correo')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO usuarios (usuario, contraseña, nombres, apellidos, correo)
                VALUES (%s, %s, %s, %s, %s)
            ''', (usuario, contraseña, nombres, apellidos, correo))
            conn.commit()
            return jsonify({"mensaje": "Usuario registrado exitosamente"}), 201
        except mysql.connector.IntegrityError:
            conn.rollback()
            return jsonify({"error": "El usuario o correo ya existe"}), 400
        finally:
            cursor.close()
            conn.close()
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500

# Ruta para iniciar sesión
@app.route('/iniciar_sesion', methods=['POST'])
def iniciar_sesion():
    data = request.json
    usuario = data.get('usuario')
    contraseña = data.get('contraseña')

    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['contraseña'], contraseña):
            return jsonify({"mensaje": "Inicio de sesión exitoso"}), 200
        else:
            return jsonify({"error": "Usuario o contraseña incorrectos"}), 401
    else:
        return jsonify({"error": "Error de conexión con la base de datos"}), 500

# Función para convertir fecha de DD/MM/YYYY a YYYY-MM-DD
def convertir_fecha(fecha):
    return datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")

# Funciones para cálculos
def generar_tea(banco_id):
    if banco_id == "BCP":
        return round(random.uniform(15, 25), 2) / 100
    elif banco_id == "Interbank":
        return round(random.uniform(18, 28), 2) / 100
    elif banco_id == "BBVA":
        return round(random.uniform(20, 30), 2) / 100
    else:
        return None

def calcular_dias(fecha_emision, fecha_vencimiento):
    fecha_emision = datetime.strptime(fecha_emision, "%d/%m/%Y")
    fecha_vencimiento = datetime.strptime(fecha_vencimiento, "%d/%m/%Y")
    return (fecha_vencimiento - fecha_emision).days

def calcular_te(tea_compensatoria, dias_calculados):
    if dias_calculados == 0:
        return 0
    return ((1 + tea_compensatoria) ** (dias_calculados / 360) - 1)

def calcular_tasa_descuento(te_compensatoria):
    return te_compensatoria / (1 + te_compensatoria)

def calcular_valor_neto(importe, tasa_descuento):
    return importe * (1 - tasa_descuento)

def calcular_costos_adicionales(banco_id, importe):
    if banco_id == "BCP":
        comision_estudios = 50.00
        comision_activacion = 30.00
        seguro_desgravamen = importe * 0.015
    elif banco_id == "Interbank":
        comision_estudios = 45.00
        comision_activacion = 35.00
        seguro_desgravamen = importe * 0.017
    elif banco_id == "BBVA":
        comision_estudios = 55.00
        comision_activacion = 25.00
        seguro_desgravamen = importe * 0.016
    else:
        return None, None, None, None
    
    return comision_estudios, comision_activacion, seguro_desgravamen, comision_estudios + comision_activacion + seguro_desgravamen

def calcular_tcea(valor_nominal, valor_recibido, dias_calculados):
    if dias_calculados == 0:
        return 0
    return ((valor_nominal / valor_recibido) ** (360 / dias_calculados)) - 1

def calcular_tef_y_tea_cartera(importe, valor_recibido, dias_calculados):
    if valor_recibido == 0:
        return 0, 0
    tef_cartera = (importe / valor_recibido) - 1
    tea_cartera = ((1 + tef_cartera) ** (360 / dias_calculados)) - 1
    return tef_cartera, tea_cartera

# Endpoint para crear una boleta libre
@app.route('/crear_boleta_libre', methods=['POST'])
def crear_boleta_libre():
    data = request.json
    nombre = data.get("nombre")
    dni = data.get("dni")
    empresa = data.get("empresa")
    ruc = data.get("ruc")
    fecha_emision = convertir_fecha(data.get("fecha_emision"))
    fecha_vencimiento = convertir_fecha(data.get("fecha_vencimiento"))
    importe = data.get("importe")
    tipo_moneda = data.get("tipo_moneda")

    # Crear boleta libre
    conn = get_db_connection()
    cursor = conn.cursor()
    boleta_id = f"libre_{uuid.uuid4()}"
    cursor.execute('''
        INSERT INTO boletas_libres (boleta_id, nombre, dni, empresa, ruc, fecha_emision, fecha_vencimiento, importe, tipo_moneda)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (boleta_id, nombre, dni, empresa, ruc, fecha_emision, fecha_vencimiento, importe, tipo_moneda))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Boleta libre creada exitosamente", "boleta_id": boleta_id}), 201

# Endpoint para ver boletas sin asignar
@app.route('/boletas_libres', methods=['GET'])
def obtener_boletas_libres():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM boletas_libres")
    boletas = cursor.fetchall()
    cursor.close()
    conn.close()

    if not boletas:
        return jsonify({"message": "No se encontraron boletas libres"}), 404

    return jsonify({"boletas_libres": boletas}), 200

# Endpoint para procesar múltiples boletas
@app.route('/procesar_boletas', methods=['POST'])
def procesar_boletas():
    data = request.json
    resultados = []

    if "boletas" not in data:
        return jsonify({"error": "Datos incompletos"}), 400

    for boleta_data in data["boletas"]:
        tea_compensatoria = generar_tea(boleta_data["banco_id"])
        if tea_compensatoria is None:
            continue

        boleta_id = f"{boleta_data['banco_id']}_{uuid.uuid4()}"
        dias_calculados = calcular_dias(boleta_data["fecha_emision"], boleta_data["fecha_vencimiento"])
        te_compensatoria = calcular_te(tea_compensatoria, dias_calculados)
        tasa_descuento = calcular_tasa_descuento(te_compensatoria)
        valor_neto = calcular_valor_neto(boleta_data["importe"], tasa_descuento)
        comision_estudios, comision_activacion, seguro_desgravamen, costos_adicionales = calcular_costos_adicionales(boleta_data["banco_id"], boleta_data["importe"])
        valor_recibido = valor_neto - costos_adicionales
        tcea = calcular_tcea(boleta_data["importe"], valor_recibido, dias_calculados)
        tef_cartera, tea_cartera = calcular_tef_y_tea_cartera(boleta_data["importe"], valor_recibido, dias_calculados)

        fecha_emision = convertir_fecha(boleta_data["fecha_emision"])
        fecha_vencimiento = convertir_fecha(boleta_data["fecha_vencimiento"])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO boletas (boleta_id, banco_id, nombre, dni, empresa, ruc, fecha_emision, fecha_vencimiento, importe, tea_compensatoria, dias_calculados, te_compensatoria, tasa_descuento, valor_neto, comision_estudios, comision_activacion, seguro_desgravamen, costos_adicionales, valor_recibido, tcea, tef_cartera, tea_cartera, tipo_moneda)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            boleta_id, boleta_data["banco_id"], boleta_data["nombre"], boleta_data["dni"],
            boleta_data["empresa"], boleta_data["ruc"], fecha_emision, fecha_vencimiento,
            boleta_data["importe"], tea_compensatoria, dias_calculados, te_compensatoria, tasa_descuento, valor_neto,
            comision_estudios, comision_activacion, seguro_desgravamen, costos_adicionales,
            valor_recibido, tcea, tef_cartera, tea_cartera, boleta_data["tipo_moneda"]
        ))
        conn.commit()
        cursor.close()
        conn.close()

        resultados.append({
            "Boleta ID": boleta_id,
            "Banco ID": boleta_data["banco_id"],
            "TEA (Tasa Efectiva Anual Compensatoria)": round(tea_compensatoria * 100, 2),
            "Dias Calculados": dias_calculados,
            "TE (Tasa Efectiva Compensatoria)": round(te_compensatoria * 100, 6),
            "Tasa de Descuento": round(tasa_descuento * 100, 6),
            "Valor Neto": round(valor_neto, 2),
            "Comisión de Estudios": round(comision_estudios, 2),
            "Comisión de Activación": round(comision_activacion, 2),
            "Seguro de Desgravamen": round(seguro_desgravamen, 2),
            "Costos Adicionales": round(costos_adicionales, 2),
            "Valor Recibido": round(valor_recibido, 2),
            "TCEA": round(tcea * 100, 2),
            "TEF (Tasa Efectiva Cartera)": round(tef_cartera * 100, 6),
            "TEA Cartera (Tasa Efectiva Anual Cartera)": round(tea_cartera * 100, 6)
        })

    return jsonify({"message": "Boletas procesadas exitosamente", "boletas": resultados}), 200

# Endpoint para ver boletas de un banco específico en una moneda específica
@app.route('/boletas/<banco_id>/<tipo_moneda>', methods=['GET'])
def obtener_boletas_por_banco_y_moneda(banco_id, tipo_moneda):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM boletas WHERE banco_id = %s AND tipo_moneda = %s", (banco_id, tipo_moneda))
    boletas = cursor.fetchall()
    cursor.close()
    conn.close()

    if not boletas:
        return jsonify({"message": f"No se encontraron boletas para el banco {banco_id} en {tipo_moneda}"}), 404

    return jsonify({"boletas": boletas}), 200

# Endpoint para asignar una boleta libre a un banco
@app.route('/asignar_boleta', methods=['POST'])
def asignar_boleta():
    data = request.json
    boleta_id = data.get("boleta_id")
    banco_id = data.get("banco_id")

    # Validar banco_id
    if banco_id not in ["BCP", "Interbank", "BBVA"]:
        return jsonify({"error": "Banco no válido. Debe ser uno de: BCP, Interbank, BBVA"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener la boleta libre
    cursor.execute("SELECT * FROM boletas_libres WHERE boleta_id = %s", (boleta_id,))
    boleta = cursor.fetchone()
    if not boleta:
        cursor.close()
        conn.close()
        return jsonify({"error": "Boleta no encontrada o ya asignada"}), 404

    # Calcular los valores financieros
    tea_compensatoria = generar_tea(banco_id)
    dias_calculados = calcular_dias(boleta["fecha_emision"].strftime("%d/%m/%Y"), boleta["fecha_vencimiento"].strftime("%d/%m/%Y"))
    te_compensatoria = calcular_te(tea_compensatoria, dias_calculados)
    tasa_descuento = calcular_tasa_descuento(te_compensatoria)
    valor_neto = calcular_valor_neto(boleta["importe"], tasa_descuento)
    comision_estudios, comision_activacion, seguro_desgravamen, costos_adicionales = calcular_costos_adicionales(banco_id, boleta["importe"])
    valor_recibido = valor_neto - costos_adicionales
    tcea = calcular_tcea(boleta["importe"], valor_recibido, dias_calculados)
    tef_cartera, tea_cartera = calcular_tef_y_tea_cartera(boleta["importe"], valor_recibido, dias_calculados)

    # Mover la boleta de boletas_libres a boletas
    cursor.execute('''
        INSERT INTO boletas (boleta_id, banco_id, nombre, dni, empresa, ruc, fecha_emision, fecha_vencimiento, importe, tea_compensatoria, dias_calculados, te_compensatoria, tasa_descuento, valor_neto, comision_estudios, comision_activacion, seguro_desgravamen, costos_adicionales, valor_recibido, tcea, tef_cartera, tea_cartera, tipo_moneda)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ''', (
        boleta["boleta_id"], banco_id, boleta["nombre"], boleta["dni"], boleta["empresa"], boleta["ruc"],
        boleta["fecha_emision"], boleta["fecha_vencimiento"], boleta["importe"], tea_compensatoria,
        dias_calculados, te_compensatoria, tasa_descuento, valor_neto, comision_estudios,
        comision_activacion, seguro_desgravamen, costos_adicionales, valor_recibido, tcea,
        tef_cartera, tea_cartera, boleta["tipo_moneda"]
    ))

    # Eliminar de boletas_libres
    cursor.execute("DELETE FROM boletas_libres WHERE boleta_id = %s", (boleta_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": f"Boleta {boleta_id} asignada al banco {banco_id} exitosamente"}), 200

# Función para calcular TCEA Cartera y COK
def calcular_tcea_cartera(boletas):
    total_valor_recibido = sum(boleta['valor_recibido'] for boleta in boletas if 'valor_recibido' in boleta)
    if total_valor_recibido == 0:
        return 0, []

    cok_values = []
    tcea_cartera = 0

    for boleta in boletas:
        if 'tea_cartera' in boleta and 'valor_recibido' in boleta:
            cok = (boleta['tea_cartera'] * boleta['valor_recibido']) / total_valor_recibido
            cok_values.append({
                "Boleta ID": boleta['boleta_id'],
                "COK": round(cok * 100, 6)
            })
            tcea_cartera += cok

    return round(tcea_cartera * 100, 6), cok_values

# Endpoint para obtener el consolidado por banco y tipo de moneda
@app.route('/consolidado_boletas', methods=['POST'])
def consolidado_boletas():
    data = request.json
    banco_id = data.get('banco_id')
    tipo_moneda = data.get('tipo_moneda')
    fecha_inicio = data.get('fecha_inicio')  # Ejemplo: "12/10/2024"
    fecha_fin = data.get('fecha_fin')  # Ejemplo: "12/11/2024"

    if not banco_id or not tipo_moneda:
        return jsonify({"error": "Debe proporcionar banco_id y tipo_moneda"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Construir la consulta con los filtros de fechas si están presentes
    query = "SELECT * FROM boletas WHERE banco_id = %s AND tipo_moneda = %s"
    params = [banco_id, tipo_moneda]

    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y").strftime("%Y-%m-%d")
        query += " AND fecha_vencimiento >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, "%d/%m/%Y").strftime("%Y-%m-%d")
        query += " AND fecha_vencimiento <= %s"
        params.append(fecha_fin)

    cursor.execute(query, params)
    boletas = cursor.fetchall()
    cursor.close()
    conn.close()

    if not boletas:
        return jsonify({"message": f"No se encontraron boletas para el banco {banco_id} en {tipo_moneda} dentro del rango de fechas especificado"}), 404

    # Calcular TCEA Cartera y COK
    tcea_cartera, cok_values = calcular_tcea_cartera(boletas)
    total_valor_recibido = sum(boleta['valor_recibido'] for boleta in boletas if 'valor_recibido' in boleta)

    consolidado = {
        "Banco ID": banco_id,
        "Tipo de Moneda": tipo_moneda,
        "Lista de Boletas": cok_values,
        "Monto Total (Valor Recibido)": round(total_valor_recibido, 2),
        "TCEA Cartera (Tasa de Costo Efectivo Anual Cartera)": tcea_cartera
    }

    return jsonify({"consolidado": consolidado}), 200

if __name__ == '__main__':
    app.run(debug=True)

