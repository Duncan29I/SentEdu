from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from pysentimiento import create_analyzer
import sqlite3
from datetime import datetime, timedelta

def crear_app():
    
 app = Flask(__name__)
 app.secret_key = 'clave_secreta_segura'  # Cambiar por una clave real
 CORS(app)

 # Analizador de sentimientos
 analyzer = create_analyzer(task="sentiment", lang="es")

 # Etiquetas de sentimiento
 etiquetas = {
    'NEG': 'Negativo',
    'NEU': 'Neutral',
    'POS': 'Positivo'
 }

 # ---------------------- FUNCIONES DE BASE DE DATOS ----------------------

 def conectar():
     return sqlite3.connect("database.db")

 def obtener_usuario_por_correo(correo):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE correo = ?", (correo,))
    usuario = cursor.fetchone()
    conn.close()
    return usuario

 # ---------------------- RUTAS DE AUTENTICACIÓN ----------------------

 @app.route('/registro', methods=['GET', 'POST'])
 def registro():
     if request.method == 'POST':
         nombre = request.form['nombre']
         correo = request.form['correo']
         contrasena = generate_password_hash(request.form['contrasena'])

         conn = conectar()
         try:
             conn.execute("INSERT INTO usuarios (nombre, correo, contrasena) VALUES (?, ?, ?)",
                          (nombre, correo, contrasena))
             conn.commit()
         except sqlite3.IntegrityError:
             conn.close()
             return "⚠️ Ya existe una cuenta con ese correo."
         conn.close()
         return redirect(url_for('login'))
     return render_template('registro.html')


 @app.route('/login', methods=['GET', 'POST'])
 def login():
     if request.method == 'POST':
         correo = request.form['correo']
         contrasena = request.form['contrasena']

         usuario = obtener_usuario_por_correo(correo)
         if usuario and check_password_hash(usuario[3], contrasena):
             session['usuario_id'] = usuario[0]
             session['nombre'] = usuario[1]
             return redirect(url_for('index'))
         else:
             return "❌ Credenciales incorrectas"
     return render_template('login.html')


 @app.route('/logout')
 def logout():
     session.clear()
     return redirect(url_for('login'))

 # ---------------------- PÁGINA PRINCIPAL ----------------------

 @app.route('/')
 def index():
     if 'usuario_id' not in session:
         return redirect(url_for('login'))
     return render_template('index.html', nombre=session['nombre'])

 # ---------------------- ANÁLISIS DE SENTIMIENTO ----------------------

 @app.route('/analizar', methods=['POST'])
 def analizar():
     if 'usuario_id' not in session:
         return jsonify({'error': 'No autenticado'}), 401

     data = request.get_json()
     texto = data.get('texto', '')
     actividad = data.get('actividad', 'No especificada')

     if not texto.strip():
         return jsonify({'error': 'Texto vacío'}), 400

     resultado = analyzer.predict(texto)
     etiqueta = resultado.output
     puntaje = resultado.probas[etiqueta]

     # Guardar en base de datos
     conn = conectar()
     conn.execute("""
         INSERT INTO analisis (usuario_id, actividad, texto, sentimiento, puntaje)
         VALUES (?, ?, ?, ?, ?)
     """, (session['usuario_id'], actividad, texto, etiquetas[etiqueta], float(puntaje)))
     conn.commit()
     conn.close()

     return jsonify({
         'actividad': actividad,
         'sentimiento': etiquetas.get(etiqueta, etiqueta),
         'puntaje': round(float(puntaje), 3),
         'detalles': {
             'POS': round(float(resultado.probas['POS']), 3),
             'NEUTRAL': round(float(resultado.probas['NEU']), 3),
             'NEG': round(float(resultado.probas['NEG']), 3)
         }
     })

 # ---------------------- REPORTE SEMANAL ----------------------

 @app.route('/reporte')
 def reporte():
     if 'usuario_id' not in session:
         return redirect(url_for('login'))

     conn = conectar()
     hoy = datetime.now()
     hace_una_semana = hoy - timedelta(days=7)

     cursor = conn.cursor()
     cursor.execute("""
         SELECT actividad, sentimiento, COUNT(*) 
         FROM analisis 
         WHERE usuario_id = ? AND fecha >= ?
         GROUP BY actividad, sentimiento
     """, (session['usuario_id'], hace_una_semana))
    
     datos = cursor.fetchall()
     conn.close()

     return render_template('reporte.html', nombre=session['nombre'], datos=datos)
 return app 
# ---------------------- INICIAR ----------------------


if __name__ == '__main__':
    app = crear_app()
    app.run(debug=True)
