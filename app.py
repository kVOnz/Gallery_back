import os
import bcrypt
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from schemas import ImageResponse, UserResponse

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv('SECRET_KEY')

connection_pool = pool.SimpleConnectionPool( 1, 20,
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 5432)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

def get_db():
    conn = connection_pool.getconn()
    conn.cursor_factory = psycopg2.extras.DictCursor
    return conn

def release_db(conn):
    connection_pool.putconn(conn)

def serialize_images(images):
    result = []
    for img in images:
        result.append(
            ImageResponse(
                image_id=img['image_id'],
                title=img['title'],
                file_path=img['file_path'],
                uploaded_at=img['uploaded_at'],
                username=img['username']
            ).model_dump()
        )
    return result

# Получить список картинок
@app.route('/api/images', methods=['GET'])
def get_images():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT i.image_id, i.title, i.file_path, i.uploaded_at, u.username
                FROM images i
                JOIN users u ON i.user_id = u.user_id
                ORDER BY i.uploaded_at DESC
            """)
            images = cur.fetchall()
    finally:
        release_db(db)

    return jsonify(serialize_images(images))

# Регистрация
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING user_id",
                (username, hashed, role)
            )
            user_id = cur.fetchone()[0]
            db.commit()
    finally:
        release_db(db)

    return jsonify({'status': 'ok', 'user_id': user_id}), 201

# Вход
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT user_id, username, password_hash, role FROM users WHERE username = %s",
                (username,)
            )
            user = cur.fetchone()
    finally:
        release_db(db)

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify(UserResponse(
            user_id=user['user_id'],
            username=user['username'],
            role=user['role']
        ).model_dump())
    else:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

# Загрузка картинки
@app.route('/api/upload', methods=['POST'])
def upload():
    if 'image' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400

    file = request.files['image']
    title = request.form.get('title', '')
    user_id = request.form.get('user_id', 1)

    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    upload_folder = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    filename = file.filename
    file_path_full = os.path.join(upload_folder, filename)
    file.save(file_path_full)

    file_path_db = f'/static/uploads/{filename}'

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO images (user_id, title, file_path) VALUES (%s, %s, %s) RETURNING image_id",
                (user_id, title, file_path_db)
            )
            image_id = cur.fetchone()[0]
            db.commit()
    finally:
        release_db(db)

    return jsonify({'status': 'ok', 'image_id': image_id, 'file_path': file_path_db}), 201

# Поиск
@app.route('/api/search')
def search():
    query = request.args.get('q', '')

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT i.image_id, i.title, i.file_path, i.uploaded_at, u.username
                FROM images i
                JOIN users u ON i.user_id = u.user_id
                WHERE i.title ILIKE %s
                ORDER BY i.uploaded_at DESC
            """, (f'%{query}%',))
            images = cur.fetchall()
    finally:
        release_db(db)

    return jsonify(serialize_images(images))

if __name__ == '__main__':
    app.run(debug=True, port=5000)