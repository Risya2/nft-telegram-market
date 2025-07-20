from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nft.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

ADMIN_ID = 5000936733
START_BALANCE = 1_000_000

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Integer, default=START_BALANCE)

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    price = db.Column(db.Integer)
    stock = db.Column(db.Integer)
    tgs_path = db.Column(db.String(100))

db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/init_user', methods=['POST'])
def init_user():
    user_id = int(request.args.get('user_id'))
    if not User.query.get(user_id):
        db.session.add(User(id=user_id))
        db.session.commit()
    return jsonify({'ok': True})

@app.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get(user_id)
    return jsonify({'balance': user.balance})

@app.route('/store')
def store():
    return jsonify([
        {
            'id': g.id,
            'name': g.name,
            'price': g.price,
            'stock': g.stock,
            'tgs_path': f'/uploads/{g.tgs_path}'
        } for g in Gift.query.all()
    ])

@app.route('/admin/add_gift', methods=['POST'])
def add_gift():
    user_id = int(request.form.get('user_id'))
    if user_id != ADMIN_ID:
        return jsonify({'error': 'Unauthorized'}), 403

    name = request.form['name']
    price = int(request.form['price'])
    stock = int(request.form['stock'])
    file = request.files['file']
    filename = file.filename
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    db.session.add(Gift(name=name, price=price, stock=stock, tgs_path=filename))
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/uploads/<filename>')
def upload_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
