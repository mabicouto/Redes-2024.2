from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt, check_password_hash, generate_password_hash
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.secret_key = 'minha-chave-secreta'




user_databases = {}  # Dicionário para armazenar as URIs de banco de dados por usuário

# Função para definir o banco de dados para cada cliente
def get_db_uri(user_id):
    return f'sqlite:///database_{user_id}.db'

# Configuração do banco de dados padrão (global)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///default.db'
db = SQLAlchemy(app)

# Inicialização inicial (não no init_app!)
with app.app_context():
    db.create_all()

bcrypt = Bcrypt(app)
socketio = SocketIO(app)

# Modelo de Usuário
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    finances = db.relationship('Finance', backref='user', lazy=True)
    table1 = db.relationship('Table1', backref='user', lazy=True)
    table2 = db.relationship('Table2', backref='user', lazy=True)

# Modelo de Finanças
class Finance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'income' ou 'expense'
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'paid'

# Modelo para Table1
class Table1(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    id = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)

# Modelo para Table2
class Table2(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    id = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)

# Rota principal
@app.route('/')
def index():
    return render_template('login.html')

# Rota de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Credenciais inválidas. Tente novamente.")
    
    return render_template('login.html')

# Rota de Registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            return render_template('register.html', error="As senhas não coincidem.")

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="Nome de usuário já existe.")
        
        hashed_password = generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error="Erro ao registrar. Tente novamente.")

    return render_template('register.html')


# Rota de dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('base.html')


@app.route('/client_page', methods=['GET'])
def client_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    if user_id in user_databases:
        app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]

    with app.app_context():
        # Consultar Finanças do Usuário
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

  
    return render_template('dashboard.html', 
                           finances=finances_data)

     
# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user_id = session['user_id']
        print(user_databases)

        app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]
    else:
        emit('redirect', {'url': url_for('index')})

@socketio.on('get_finances')
def get_finances():
    if 'user_id' in session:
        user_id = session['user_id']
        app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]
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
        app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]
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
    if 'user_id' in session:
        user_id = session['user_id']
        app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]
        finance = Finance.query.get(finance_id)
        if finance and finance.user_id == session.get('user_id'):
            finance.status = 'paid'
            db.session.commit()
            emit('finance_resolved', {'id': finance.id}, broadcast=True)

# Rotas para manipulação das Tabelas 1 e 2
@app.route('/api/table1', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table1():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Usuário não autenticado"}), 401
    
    user_id = session['user_id']
    print(user_databases)
    app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]

    with app.app_context():
        if request.method == 'GET':
            table1_records = Table1.query.filter_by(user_id=user_id).all()
            return jsonify([{'id': t.id, 'value': t.value, 'date': t.date} for t in table1_records])
        elif request.method == 'POST':
            new_record = Table1(
                user_id=user_id,
                id=request.json['id'],
                value=request.json['value'],
                date=request.json['date']
            )
            try:
                db.session.add(new_record)
                db.session.commit()
                return jsonify({'status': 'success', 'message': 'Registro adicionado com sucesso!'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'status': 'error', 'message': 'Erro ao adicionar o registro'})
        elif request.method == 'PUT':
            record_id = request.json['id']
            record = Table1.query.filter_by(user_id=user_id, id=record_id).first()
            if record:
                record.value = request.json['value']
                record.date = request.json['date']
                try:
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': 'Registro atualizado com sucesso!'})
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Erro ao atualizar o registro'})
        elif request.method == 'DELETE':
            record_id = request.json['id']
            record = Table1.query.filter_by(user_id=user_id, id=record_id).first()
            if record:
                try:
                    db.session.delete(record)
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': 'Registro excluído com sucesso!'})
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Erro ao excluir o registro'})

@app.route('/api/table2', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table2():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Usuário não autenticado"}), 401
    
    user_id = session['user_id']
    app.config['SQLALCHEMY_DATABASE_URI'] = user_databases[user_id]

    with app.app_context():
        if request.method == 'GET':
            table2_records = Table2.query.filter_by(user_id=user_id).all()
            return jsonify([{'id': t.id, 'value': t.value, 'date': t.date} for t in table2_records])
        elif request.method == 'POST':
            new_record = Table2(
                user_id=user_id,
                id=request.json['id'],
                value=request.json['value'],
                date=request.json['date']
            )
            try:
                db.session.add(new_record)
                db.session.commit()
                return jsonify({'status': 'success', 'message': 'Registro adicionado com sucesso!'})
            except Exception as e:
                db.session.rollback()
                return jsonify({'status': 'error', 'message': 'Erro ao adicionar o registro'})
        elif request.method == 'PUT':
            record_id = request.json['id']
            record = Table2.query.filter_by(user_id=user_id, id=record_id).first()
            if record:
                record.value = request.json['value']
                record.date = request.json['date']
                try:
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': 'Registro atualizado com sucesso!'})
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Erro ao atualizar o registro'})
        elif request.method == 'DELETE':
            record_id = request.json['id']
            record = Table2.query.filter_by(user_id=user_id, id=record_id).first()
            if record:
                try:
                    db.session.delete(record)
                    db.session.commit()
                    return jsonify({'status': 'success', 'message': 'Registro excluído com sucesso!'})
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'message': 'Erro ao excluir o registro'})

if __name__ == '__main__':
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///default.db'  # Banco de dados padrão
    print(app.config['SQLALCHEMY_DATABASE_URI'])
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
