from flask import Flask, render_template, request, redirect, url_for
import pymysql

app = Flask(__name__)

DB_CONFIG = {

}

def get_db():
    return pymysql.connect(**DB_CONFIG)


# галвная страница
@app.route('/')
def index():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT p.product_id, p.name, c.name AS category,
                       p.unit, p.quantity_on_stock
                FROM products p
                JOIN categories c ON p.category_id = c.category_id
                WHERE p.is_deleted = 0
                ORDER BY p.name
            """)
            products = cur.fetchall()
    finally:
        db.close()
    return render_template('index.html', products=products)

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