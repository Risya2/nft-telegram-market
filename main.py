from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nft.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

START_BALANCE = 1_000_000
ADMIN_ID = 5000936733

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    balance = db.Column(db.Integer, default=START_BALANCE)

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Integer)
    stock = db.Column(db.Integer)
    tgs_path = db.Column(db.String(200))

db.create_all()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/init_user', methods=['POST'])
def init_user():
    user_id = int(request.args.get('user_id'))
    user = User.query.get(user_id)
    if not user:
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/store')
def store():
    gifts = Gift.query.all()
    return jsonify([
        {
            'id': g.id,
            'name': g.name,
            'price': g.price,
            'stock': g.stock,
            'tgs_path': g.tgs_path
        } for g in gifts
    ])

@app.route('/admin/add_gift', methods=['POST'])
def add_gift():
    user_id = int(request.form.get('user_id'))
    if user_id != ADMIN_ID:
        return jsonify({'error': 'Forbidden'}), 403

    name = request.form['name']
    price = int(request.form['price'])
    stock = int(request.form['stock'])
    file = request.files['file']

    filename = file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    gift = Gift(name=name, price=price, stock=stock, tgs_path=f'uploads/{filename}')
    db.session.add(gift)
    db.session.commit()

    return jsonify({'status': 'added'})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
