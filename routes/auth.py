# __РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ__
import os
import bcrypt
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_restx import Namespace, Resource
from dotenv import load_dotenv
from schemas import ImageResponse, UserResponse
from flask_restx import Api, Resource, fields
from werkzeug.datastructures import FileStorage
from flask import session
from functools import wraps
from app import api


# загрузить все из .env файла
load_dotenv()

app = Flask(__name__)
CORS(app) # разрешить запросы из других портов
app.secret_key = os.getenv('SECRET_KEY') 

# пул соединений, чтобы не открывать новые соединения на каждый запрос
connection_pool = pool.SimpleConnectionPool(
    1, # мин. кол-во соединений
    20, # макс. кол-во соединений
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 5432)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)

# функция получения соединения из _пула_ --> (штука выше)
def get_db():
    conn = connection_pool.getconn()
    conn.cursor_factory = psycopg2.extras.DictCursor
    return conn

# функция возврата соединения в пул
def release_db(conn):
    connection_pool.putconn(conn)

# декоратор для входа
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return {'error': 'Не авторизован'}, 401
        return f(*args, **kwargs)
    return decorated

# модель для регистрации
register_model = api.model('Register', {
    'username': fields.String(required=True, description='Логин пользователя', example='ivan'),
    'password': fields.String(required=True, description='Пароль', example='123'),
    'role': fields.String(required=False, description='Роль', example='user')
})

# модель для логина
login_model = api.model('Login', {
    'username': fields.String(required=True, description='Логин', example='ivan'),
    'password': fields.String(required=True, description='Пароль', example='123')
})

ns = Namespace('auth', description='операция с авторизацией')

@ns.route('/register')
class Register(Resource):
    @ns.doc('register_user')
    @ns.expect(register_model, validate=True) # validatre нужно для автоматической проверки полей
    @ns.response(400, 'Логин и пароль обязательны или неверный формат')
    @ns.response(201, 'Пользователь успешно создан')
    def post(self):
        # получение JSON запроса от фронта с username, password и ролей usera
        data = ns.payload
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'user')

        # проверка, что username и password не пустые, иначе выдать ошибку 400
        if not username or not password or not username.strip() or not password.strip():
            return {'error': 'Логин и пароль обязательны'}, 400

        # хеширование пароля через bcrypt
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        db = get_db()
        try: # выполнение функции INSERT INTO users, чтобы записать нового пользователя
            with db.cursor() as cur:
                cur.execute( 
                    "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING user_id",
                    (username, hashed, role)
                )
                result = cur.fetchone() # получить одну строку из результата и взять из нее 1 столбец (0)
                if result is None:
                    return {'ошибка: не удалось создать пользователя'}, 500

                user_id = result[0]
                db.commit()

        finally:
            release_db(db) # возвращение соединения в пул
        return {'status': 'ok', 'user_id': user_id}, 201


# __ВХОД__
@ns.route('/login')
class Login(Resource):
    @ns.doc('login_user')
    @ns.expect(login_model, validate=True)
    @ns.response(200, 'Успешный вход')
    @ns.response(401, 'Неверный логин или пароль')
    def post(self):
        data = ns.payload
        username = data.get('username')
        password = data.get('password')

        db = get_db()
        try: # выполнение функции SELECT для поиска usera по логину
            with db.cursor() as cur:
                cur.execute(
                    "SELECT user_id, username, password_hash, role FROM users WHERE username = %s",
                    (username,)
                )
                user = cur.fetchone()
        finally:
            release_db(db) # возвращение соединения в пул

        # проверка пародя через bcrypt
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')): # проверка на совпадение пароля с хешом в БД
            # bcrypt.checkpw - сравнивает хэш введенного пароля и хэш в БД
            # password.encode - нужна для превращения строки пароля в байты
            # user['password_hash'].encode('utf-8') - нужно для забора хэша из БД
            session['user_id'] = user[0]
            session['role'] = user[3]
            return UserResponse(
                user_id=user[0],
                username=user[1],
                role=user[3]
            ).model_dump()
        else:
            return {'error': 'Неверный логин или пароль'}, 401