from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import secrets
import sqlite3
from werkzeug.utils import secure_filename
from contextlib import closing

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Конфигурация
app.config.update({
    'UPLOAD_FOLDER': 'static/gifts',
    'DATABASE': 'gifts.db',
    'INITIAL_BALANCE': 2000000,
    'ADMIN_ID': 5000936733,
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024
})

# Инициализация БД
def init_db():
    with closing(connect_db()) as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 2000000
        )""")
        
        db.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            filename TEXT NOT NULL
        )""")
        
        db.execute("""
        CREATE TABLE IF NOT EXISTS user_gifts (
            user_id INTEGER,
            gift_id INTEGER,
            quantity INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, gift_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (gift_id) REFERENCES gifts(id)
        )""")
        
        db.commit()

def connect_db():
    return sqlite3.connect(app.config['DATABASE'])

if not os.path.exists(app.config['DATABASE']):
    init_db()

# Функции для работы с БД
def get_user(user_id):
    with closing(connect_db()) as db:
        db.execute("INSERT OR IGNORE INTO users (id, balance) VALUES (?, ?)",
                  (user_id, app.config['INITIAL_BALANCE']))
        db.commit()
        
        user = db.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        gifts = db.execute("""
            SELECT g.name, g.filename, ug.quantity 
            FROM user_gifts ug
            JOIN gifts g ON ug.gift_id = g.id
            WHERE ug.user_id = ?
        """, (user_id,)).fetchall()
        
        return {
            'balance': user[0],
            'gifts': [{'name': g[0], 'file': g[1], 'quantity': g[2]} for g in gifts]
        }

def get_all_gifts():
    with closing(connect_db()) as db:
        return db.execute("SELECT id, name, price, stock, filename FROM gifts").fetchall()

def buy_gift(user_id, gift_id):
    with closing(connect_db()) as db:
        try:
            gift = db.execute("SELECT price, stock FROM gifts WHERE id = ?", (gift_id,)).fetchone()
            if not gift or gift[1] <= 0:
                return False, "Подарок недоступен"
            
            balance = db.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()[0]
            if balance < gift[0]:
                return False, "Недостаточно звёзд"
            
            db.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (gift[0], user_id))
            db.execute("UPDATE gifts SET stock = stock - 1 WHERE id = ?", (gift_id,))
            
            # Добавляем или обновляем подарок у пользователя
            db.execute("""
                INSERT INTO user_gifts (user_id, gift_id, quantity) 
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, gift_id) DO UPDATE SET quantity = quantity + 1
            """, (user_id, gift_id))
            
            db.commit()
            return True, "Подарок куплен!"
        except Exception as e:
            db.rollback()
            return False, f"Ошибка: {str(e)}"

def add_gift(name, price, stock, filename):
    with closing(connect_db()) as db:
        try:
            db.execute("""
                INSERT INTO gifts (name, price, stock, filename)
                VALUES (?, ?, ?, ?)
            """, (name, price, stock, filename))
            db.commit()
            return True, "Подарок добавлен"
        except Exception as e:
            db.rollback()
            return False, f"Ошибка: {str(e)}"

# Маршруты
@app.route('/')
def home():
    user_id = request.args.get('user_id', type=int) or 1
    session['user_id'] = user_id
    is_admin = user_id == app.config['ADMIN_ID']
    
    return render_template('index.html',
                         user=get_user(user_id),
                         gifts=get_all_gifts(),
                         is_admin=is_admin)

@app.route('/buy/<int:gift_id>')
def buy(gift_id):
    user_id = session.get('user_id', 1)
    success, message = buy_gift(user_id, gift_id)
    return jsonify(success=success, message=message)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    user_id = session.get('user_id', 1)
    if user_id != app.config['ADMIN_ID']:
        return "Доступ запрещен", 403
    
    if request.method == 'POST':
        name = request.form['name']
        price = int(request.form['price'])
        stock = int(request.form['stock'])
        file = request.files['file']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            add_gift(name, price, stock, filename)
    
    return render_template('admin.html', gifts=get_all_gifts())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'tgs'

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
