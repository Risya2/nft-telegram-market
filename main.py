import os
import secrets
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import sqlite3
from contextlib import closing

app = Flask(__name__)

# Генерация случайного секретного ключа
def generate_secret_key():
    return secrets.token_hex(32)

# Конфигурация приложения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or generate_secret_key()
app.config['UPLOAD_FOLDER'] = 'static/gifts'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['DATABASE'] = 'gift_market.db'
app.config['INITIAL_BALANCE'] = 2000000

# Создаем папку для загрузки файлов, если ее нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация базы данных
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])

# Создаем файл схемы базы данных (schema.sql)
with open('schema.sql', 'w') as f:
    f.write("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        balance INTEGER NOT NULL DEFAULT 2000000
    );
    
    CREATE TABLE IF NOT EXISTS gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL,
        stock INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS user_gifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        gift_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (gift_id) REFERENCES gifts (id)
    );
    """)

# Инициализируем базу данных при первом запуске
if not os.path.exists(app.config['DATABASE']):
    init_db()

# Функции для работы с базой данных
def get_user_data():
    with closing(connect_db()) as db:
        cursor = db.cursor()
        
        # Получаем или создаем пользователя
        cursor.execute("SELECT id, balance FROM users LIMIT 1")
        user = cursor.fetchone()
        
        if not user:
            cursor.execute("INSERT INTO users (balance) VALUES (?)", (app.config['INITIAL_BALANCE'],))
            db.commit()
            user_id = cursor.lastrowid
            balance = app.config['INITIAL_BALANCE']
        else:
            user_id, balance = user
        
        # Получаем подарки пользователя
        cursor.execute("""
            SELECT g.name, g.file_path, ug.quantity 
            FROM user_gifts ug
            JOIN gifts g ON ug.gift_id = g.id
            WHERE ug.user_id = ?
        """, (user_id,))
        gifts = [{"name": name, "file": file_path, "quantity": quantity} 
                for name, file_path, quantity in cursor.fetchall()]
        
        return {
            "balance": balance,
            "gifts": gifts
        }

def get_gifts():
    with closing(connect_db()) as db:
        cursor = db.cursor()
        cursor.execute("SELECT id, name, price, stock, file_path FROM gifts")
        return [{
            "id": id,
            "name": name,
            "price": price,
            "stock": stock,
            "file": file_path
        } for id, name, price, stock, file_path in cursor.fetchall()]

def buy_gift(user_id, gift_id):
    with closing(connect_db()) as db:
        cursor = db.cursor()
        
        # Получаем данные о подарке
        cursor.execute("SELECT price, stock FROM gifts WHERE id = ?", (gift_id,))
        gift = cursor.fetchone()
        if not gift:
            return False, "Подарок не найден"
        
        price, stock = gift
        
        # Проверяем баланс пользователя
        cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        balance = cursor.fetchone()[0]
        
        if balance < price:
            return False, "Недостаточно звёзд"
        
        if stock <= 0:
            return False, "Этот подарок закончился"
        
        try:
            # Обновляем баланс
            cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
            
            # Уменьшаем остаток
            cursor.execute("UPDATE gifts SET stock = stock - 1 WHERE id = ?", (gift_id,))
            
            # Добавляем подарок пользователю
            cursor.execute("""
                INSERT INTO user_gifts (user_id, gift_id, quantity)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, gift_id) DO UPDATE SET quantity = quantity + 1
            """, (user_id, gift_id))
            
            db.commit()
            return True, "Подарок успешно куплен"
        except Exception as e:
            db.rollback()
            return False, f"Ошибка при покупке: {str(e)}"

def add_gift(name, price, stock, file_path):
    with closing(connect_db()) as db:
        cursor = db.cursor()
        try:
            cursor.execute("""
                INSERT INTO gifts (name, price, stock, file_path)
                VALUES (?, ?, ?, ?)
            """, (name, price, stock, file_path))
            db.commit()
            return True, "Подарок успешно добавлен"
        except Exception as e:
            db.rollback()
            return False, f"Ошибка при добавлении подарка: {str(e)}"

# Маршруты Flask
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
def api_user_data():
    return jsonify(get_user_data())

@app.route('/api/gifts', methods=['GET'])
def api_gifts():
    return jsonify(get_gifts())

@app.route('/api/buy/<int:gift_id>', methods=['POST'])
def api_buy(gift_id):
    user_id = 1  # В реальном приложении здесь должна быть аутентификация
    success, message = buy_gift(user_id, gift_id)
    if success:
        return jsonify({"status": "success", "message": message, "user_data": get_user_data()})
    else:
        return jsonify({"status": "error", "message": message}), 400

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if request.method == 'POST':
        name = request.form.get('name')
        price = int(request.form.get('price'))
        stock = int(request.form.get('stock'))
        
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            success, message = add_gift(name, price, stock, filename)
            if not success:
                return render_template('admin.html', error=message, gifts=get_gifts())
    
    return render_template('admin.html', gifts=get_gifts())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'tgs'}

if __name__ == '__main__':
    app.run(debug=True)
