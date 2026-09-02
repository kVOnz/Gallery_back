# различные импорты библиотек для хеширования пароля, работой с БД, .env файла и т.п.
import os
import bcrypt
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from schemas import ImageResponse, UserResponse
from flask_restx import Api, Resource, fields

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

# простраство имен для картинок
api = Api(
    app, 
    version='1.0', 
    title='Мой сайт с картинками',
    doc='/docs'
)
ns = api.namespace('api', description="операция с картинками")

# описание модели для главной страницы
image_model = api.model('Image', {
    'image_id': fields.Integer(description='ID изображения', example=1),
    'title': fields.String(description='Название картинки', example='Мой кот'),
    'file_path': fields.String(description='Путь к файлу', example='/uploads/cat.jpg'),
    'uploaded_at': fields.String(description='Дата загрузки', example='2026-08-29 12:00:00'),
    'username': fields.String(description='Кто загрузил', example='ivan_ivanov')
})

# описание модели номер 2 (для регистрации)
register_model = api.model('Register', {
    'username': fields.String(required=True, description='Логин пользователя', example='ivan'),
    'password': fields.String(required=True, description='Пароль', example='123'),
    'role': fields.String(required=False, description='Роль', example='user')
})

#
login_model = api.model('Login', {
    'username': fields.String(required=True, description='Логин', example='ivan'),
    'password': fields.String(required=True, description='Пароль', example='123')
})

#
upload_parser = api.parser()
upload_parser.add_argument('image', location='files', type=FileStorage, required=True, help='Файл картинки')
upload_parser.add_argument('title', location='form', type=str, help='Название картинки')
upload_parser.add_argument('user_id', location='form', type=int, help='ID пользователя')


# __ПОЛУЧЕНИЕ ВСЕХ КАРТИНОК (ГЛАВНАЯ)__
@ns.route('/images')
class ImageList(Resource):
    @ns.doc('get_images')
    @ns.marshal_list_with(image_model)
    def get(self):
        db = get_db()
        try: # выполнение функции SELECT и JOIN для получения image_id, title, file_path, uploaded_at картинки и username юзера, который опубликовал ее
            with db.cursor() as cur:
                cur.execute("""
                    SELECT i.image_id, i.title, i.file_path, i.uploaded_at, u.username
                    FROM images i
                    JOIN users u ON i.user_id = u.user_id
                    ORDER BY i.uploaded_at DESC
                """)
                images = cur.fetchall() # получение всех строк из результата SQL запроса
        finally:
            release_db(db) # возвращение соединения в пул

        return serialize_images(images)

# __РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ__
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
        if not username.strip() or not password.strip():
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
                user_id = cur.fetchone()[0] # получить одну строку из результата и взять из нее 1 столбец (0)
                db.commit() # сохранение изменений
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
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')): # проверка на совпадение пароля с хешом в БД
            # bcrypt.checkpw - сравнивает хэш введенного пароля и хэш в БД
            # password.encode - нужна для превращения строки пароля в байты
            # user['password_hash'].encode('utf-8') - нужно для забора хэша из БД
            return UserResponse(
                user_id=user['user_id'],
                username=user['username'],
                role=user['role']
            ).model_dump()
        else:
            return {'error': 'Неверный логин или пароль'}, 401
  

# __ЗАГРУЗКА КАРТИНКИ__
@ns.route('/upload')
class Upload(Resource):
    @ns.doc('upload_image')
    @ns.expect(upload_parser)
    @ns.response(201, 'Картинка загружена')
    @ns.response(400, 'Файл не найден или не выбран')
    def post(self):
        args = upload_parser.parse_args()
        file = args['image']
        title = args['title'] or ''
        user_id = args['user_id'] or 1
        
        #
        if not file:
            return {'error': 'Файл не найден'}, 400

        # если названия файла нет, то ошибка 400
        if file.filename == '':
            return {'error': 'Файл не выбран'}, 400
        
        upload_folder = os.path.join(app.root_path, 'static', 'uploads') # определение пути для папки с картинками
        os.makedirs(upload_folder, exist_ok=True) # создание папки если ее нет

        # сохранение файла
        filename = file.filename # название файла
        file.save(os.path.join(upload_folder, filename)) # сохранение файла на диск по пути, прописанный внутри

        # путь для БД
        file_path_db = f'/static/uploads/{filename}'

        db = get_db()
        try: # выполнение функции INSERT INTO images для сохранения информации о картинке, user_id, title, file_path
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO images (user_id, title, file_path) VALUES (%s, %s, %s) RETURNING image_id",
                    (user_id, title, file_path_db)
                )
                image_id = cur.fetchone()[0] # получить одну строку из результата и взять из нее 1 столбец
                db.commit()
        finally:
            release_db(db) # возвращение соединения в пул

        return {'status': 'ok', 'image_id': image_id, 'file_path': file_path_db}, 201 # ответ фронту после успешной загрузки картинки

# __ПОИСК КАРТИНКИ__
@app.route('/api/search')
def search(): # получение поискового запроса из URL
    query = request.args.get('q', '')

    db = get_db()
    try: # выполнение функций SELECT, JOIN с помощью ILIKE (поиск без учета регистра)
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
        release_db(db) # возвращение соединения в пул

    return jsonify(serialize_images(images))

# __ЗАПУСК ПРИЛОЖЕНИЯ__
if __name__ == '__main__':
    app.run(debug=True, port=5000)