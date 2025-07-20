from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nft.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
db = SQLAlchemy(app)

# ===== Модели =====
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Integer, default=1_000_000)

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Integer)
    stock = db.Column(db.Integer)
    tgs_path = db.Column(db.String(200))

# ===== Инициализация базы и папок =====
with app.app_context():
    db.create_all()
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ===== Роуты =====
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/init_user', methods=['POST'])
def init_user():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return 'Missing user_id', 400
    user = User.query.get(user_id)
    if not user:
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()
    return jsonify({'user_id': user.id, 'balance': user.balance})

@app.route('/store')
def store():
    gifts = Gift.query.all()
    return jsonify([
        {'id': g.id, 'name': g.name, 'price': g.price, 'stock': g.stock, 'tgs_path': g.tgs_path}
        for g in gifts
    ])

@app.route('/admin/add_gift', methods=['POST'])
def add_gift():
    user_id = request.form.get('user_id', type=int)
    if user_id != 5000936733:
        return 'Access denied', 403

    name = request.form['name']
    price = int(request.form['price'])
    stock = int(request.form['stock'])
    file = request.files['file']

    if not file or not file.filename.endswith('.tgs'):
        return 'Invalid file', 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    gift = Gift(name=name, price=price, stock=stock, tgs_path=f'static/uploads/{filename}')
    db.session.add(gift)
    db.session.commit()

    return jsonify({'status': 'added', 'gift_id': gift.id})

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ===== Запуск =====
if __name__ == '__main__':
    app.run(debug=True, port=8000)
