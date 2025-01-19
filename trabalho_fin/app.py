from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt, check_password_hash
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash
import os

app = Flask(__name__)
app.secret_key = 'minha-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app)

# Modelo de Usuário
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    finances = db.relationship('Finance', backref='user', lazy=True)

# Modelo de Finanças
class Finance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'income' ou 'expense'
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'paid'

# Definindo a estrutura da Tabela 1
class Table1(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)

# Definindo a estrutura da Tabela 2
class Table2(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()

# Rota principal
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Rota de login
@app.route('/login', methods=['GET','POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password, password):  # Utilize `check_password_hash` corretamente
        session['user_id'] = user.id
        return redirect(url_for('dashboard'))
    return render_template('login.html', error="Credenciais inválidas. Tente novamente.")

# Rota de registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            return jsonify({"status": "error", "message": "As senhas não coincidem."})

        if User.query.filter_by(username=username).first():
            return jsonify({"status": "error", "message": "Nome de usuário já existe."})
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect('/login')  # Redireciona para a página de login após sucesso
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": "Erro ao registrar. Tente novamente."})
    return render_template('register.html')

# Rota de dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Eventos SocketIO para gerenciamento de finanças
@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        emit('redirect', {'url': url_for('index')})

@socketio.on('get_finances')
def get_finances():
    if 'user_id' in session:
        user_id = session['user_id']
        finances = Finance.query.filter_by(user_id=user_id).all()
        finances_data = [
            {
                'id': f.id,
                'type': f.type,
                'description': f.description,
                'amount': f.amount,
                'status': f.status
            }
            for f in finances
        ]
        emit('update_finances', finances_data)

@socketio.on('add_finance')
def add_finance(data):
    if 'user_id' in session:
        user_id = session['user_id']
        new_finance = Finance(
            user_id=user_id,
            type=data['type'],
            description=data['description'],
            amount=float(data['amount']),
            status=data.get('status', 'pending')
        )
        try:
            db.session.add(new_finance)
            db.session.commit()
            emit('finance_added', {
                'id': new_finance.id,
                'type': new_finance.type,
                'description': new_finance.description,
                'amount': new_finance.amount,
                'status': new_finance.status
            }, broadcast=True)
        except Exception:
            db.session.rollback()
            emit('error', {'message': 'Erro ao adicionar finança'})

@socketio.on('resolve_finance')
def resolve_finance(finance_id):
    finance = Finance.query.get(finance_id)
    if finance and finance.user_id == session.get('user_id'):
        finance.status = 'paid'
        db.session.commit()
        emit('finance_resolved', {'id': finance.id}, broadcast=True)

# Rotas para manipulação das Tabelas 1 e 2
@app.route('/api/table1', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table1():
    if request.method == 'GET':
        data = Table1.query.all()
        return jsonify([{"id": row.id, "value": row.value, "date": row.date} for row in data])

    if request.method == 'POST':
        new_data = request.json
        new_row = Table1(id=new_data['id'], value=new_data['value'], date=new_data['date'])
        db.session.add(new_row)
        db.session.commit()
        socketio.emit('update_graph', {'table': 'table1'})
        return jsonify({"message": "Dado adicionado à Tabela 1!"})

    if request.method == 'PUT':
        updated_data = request.json
        row = Table1.query.get(updated_data['id'])
        if row:
            row.value = updated_data['value']
            db.session.commit()
            socketio.emit('update_graph', {'table': 'table1'})
            return jsonify({"message": "Dado atualizado na Tabela 1!"})
        return jsonify({"message": "ID não encontrado!"}), 404

    if request.method == 'DELETE':
        row_id = request.args.get('id')
        row = Table1.query.get(row_id)
        if row:
            db.session.delete(row)
            db.session.commit()
            socketio.emit('update_graph', {'table': 'table1'})
            return jsonify({"message": "Dado deletado da Tabela 1!"})
        return jsonify({"message": "ID não encontrado!"}), 404

# Rotas para manipulação da Tabela 2
@app.route('/api/table2', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table2():
    if request.method == 'GET':
        data = Table2.query.all()
        return jsonify([{"id": row.id, "value": row.value, "date": row.date} for row in data])

    if request.method == 'POST':
        new_data = request.json
        new_row = Table2(id=new_data['id'], value=new_data['value'], date=new_data['date'])
        db.session.add(new_row)
        db.session.commit()
        socketio.emit('update_graph', {'table': 'table2'})
        return jsonify({"message": "Dado adicionado à Tabela 2!"})

    if request.method == 'PUT':
        updated_data = request.json
        row = Table2.query.get(updated_data['id'])
        if row:
            row.value = updated_data['value']
            db.session.commit()
            socketio.emit('update_graph', {'table': 'table2'})
            return jsonify({"message": "Dado atualizado na Tabela 2!"})
        return jsonify({"message": "ID não encontrado!"}), 404

    if request.method == 'DELETE':
        row_id = request.args.get('id')
        row = Table2.query.get(row_id)
        if row:
            db.session.delete(row)
            db.session.commit()
            socketio.emit('update_graph', {'table': 'table2'})
            return jsonify({"message": "Dado deletado da Tabela 2!"})
        return jsonify({"message": "ID não encontrado!"}), 404

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
