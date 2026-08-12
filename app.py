from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2
import psycopg2.extras
import os

app = Flask(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'postgres',
    'password': '',
    'database': ''
}
def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.cursor_factory = psycopg2.extras.DictCursor
    return conn

# главная страница
@app.route('/')
def index():
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
        db.close()
    return render_template('index.html', images=images)

# загрузить картинку
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        title = request.form['title']
        file = request.files['image']
        
        # сохранить файл
        filename = file.filename
        file.save(os.path.join('static/uploads', filename))
        
        # записать в БД
        file_path = f'/static/uploads/{filename}'
        db = get_db()
        cur = db.cursor()
        cur.execute(
                "INSERT INTO images (user_id, title, file_path) VALUES (%s, %s, %s) RETURNING image_id",
                (1, title, file_path)
                )
        image_id = cur.fetchone()[0]
        db.commit()
        db.close()
        
        return redirect(url_for('index'))
    
    return render_template('upload.html')

# поиск картинки
@app.route('/search')
def search():
    query = request.args.get('q', '')
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT * FROM images WHERE title ILIKE %s ORDER BY uploaded_at DESC",
        (f'%{query}%',)
    )
    images = cur.fetchall()
    db.close()
    return render_template('index.html', images=images, query=query)

# войти
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "SELECT user_id, role FROM users WHERE username = %s AND password_hash = %s",
                    (username, password)
                )
                user = cur.fetchone()
        finally:
            db.close()
    
        if user:
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')

    return render_template('login.html')

# регистрация
@app.route('/registration', methods=['GET', 'POST'])
def registration():

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
    
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, password, role)
                )
                db.commit()
        finally:
            db.close()

        return redirect(url_for('login'))

    return render_template('registration.html')