from flask import Flask, render_template, session, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO, emit
import os

# Inicialização do app
app = Flask(__name__)
app.secret_key = 'minha-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Remova o banco de dados existente se ele existir
if os.path.exists('database.db'):
    os.remove('database.db')

# Inicialize as extensões
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app)

# Modelos
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    finances = db.relationship('Finance', backref='user', lazy=True)
    table1_entries = db.relationship('Table1', backref='user', lazy=True)
    table2_entries = db.relationship('Table2', backref='user', lazy=True)

class Finance(db.Model):
    __tablename__ = 'finance'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')

class Table1(db.Model):
    __tablename__ = 'table1'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_id = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'entry_id', name='unique_entry_user1'),)

class Table2(db.Model):
    __tablename__ = 'table2'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_id = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'entry_id', name='unique_entry_user2'),)

# Middleware
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Rotas de autenticação
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        return render_template('login.html', error="Credenciais inválidas")
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            return render_template('register.html', error="As senhas não coincidem")

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error="Nome de usuário já existe")
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            return render_template('register.html', error="Erro ao registrar")

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Rotas principais
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('base.html')

@app.route('/client_page')
@login_required
def client_page():
    user_id = session['user_id']
    finances = Finance.query.filter_by(user_id=user_id).all()
    finances_data = [{
        'id': f.id,
        'type': f.type,
        'description': f.description,
        'amount': f.amount,
        'status': f.status
    } for f in finances]
    
    return render_template('dashboard.html', finances=finances_data)

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    if 'user_id' not in session:
        emit('redirect', {'url': url_for('login')})

@socketio.on('get_finances')
def get_finances():
    if 'user_id' in session:
        user_id = session['user_id']
        finances = Finance.query.filter_by(user_id=user_id).all()
        finances_data = [{
            'id': f.id,
            'type': f.type,
            'description': f.description,
            'amount': f.amount,
            'status': f.status
        } for f in finances]
        emit('update_finances', finances_data)

@socketio.on('add_finance')
def add_finance(data):
    if 'user_id' in session:
        try:
            new_finance = Finance(
                user_id=session['user_id'],
                type=data['type'],
                description=data['description'],
                amount=float(data['amount']),
                status=data.get('status', 'pending')
            )
            db.session.add(new_finance)
            db.session.commit()
            
            emit('finance_added', {
                'id': new_finance.id,
                'type': new_finance.type,
                'description': new_finance.description,
                'amount': new_finance.amount,
                'status': new_finance.status
            }, broadcast=True)
        except Exception as e:
            db.session.rollback()
            emit('error', {'message': 'Erro ao adicionar finança'})

@socketio.on('resolve_finance')
def resolve_finance(finance_id):
    if 'user_id' in session:
        finance = Finance.query.get(finance_id)
        if finance and finance.user_id == session['user_id']:
            finance.status = 'paid'
            db.session.commit()
            emit('finance_resolved', {'id': finance.id}, broadcast=True)

@app.route('/api/balance', methods=['GET'])
@login_required
def get_balance():
    user_id = session['user_id']
    
    try:
        # Obtém todas as entradas (table1)
        income_data = Table1.query.filter_by(user_id=user_id).all()
        total_income = sum(entry.value for entry in income_data)
        
        # Obtém todas as saídas (table2)
        expense_data = Table2.query.filter_by(user_id=user_id).all()
        total_expenses = sum(entry.value for entry in expense_data)
        
        # Calcula o saldo atual
        current_balance = total_income - total_expenses
        
        return jsonify({
            'current_balance': current_balance,
            'total_income': total_income,
            'total_expenses': total_expenses
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API Routes
@app.route('/api/table1', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def handle_table1():
    user_id = session['user_id']

    if request.method == 'GET':
        data = Table1.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": row.entry_id,
            "value": row.value,
            "date": row.date
        } for row in data])

    if request.method == 'POST':
        try:
            new_data = request.json
            new_row = Table1(
                user_id=user_id,
                entry_id=new_data['id'],
                value=new_data['value'],
                date=new_data['date']
            )
            db.session.add(new_row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado adicionado à Tabela 1!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

    if request.method == 'PUT':
        try:
            updated_data = request.json
            row = Table1.query.filter_by(user_id=user_id, entry_id=updated_data['id']).first()
            if not row:
                return jsonify({"message": "ID não encontrado!"}), 404
            
            row.value = updated_data['value']
            row.date = updated_data.get('date', row.date)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado atualizado na Tabela 1!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

    if request.method == 'DELETE':
        try:
            entry_id = request.args.get('id')
            row = Table1.query.filter_by(user_id=user_id, entry_id=entry_id).first()
            if not row:
                return jsonify({"message": "ID não encontrado!"}), 404
            
            db.session.delete(row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado deletado da Tabela 1!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

@app.route('/api/table2', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def handle_table2():
    user_id = session['user_id']

    if request.method == 'GET':
        data = Table2.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": row.entry_id,
            "value": row.value,
            "date": row.date
        } for row in data])

    if request.method == 'POST':
        try:
            new_data = request.json
            new_row = Table2(
                user_id=user_id,
                entry_id=new_data['id'],
                value=new_data['value'],
                date=new_data['date']
            )
            db.session.add(new_row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado adicionado à Tabela 2!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

    if request.method == 'PUT':
        try:
            updated_data = request.json
            row = Table2.query.filter_by(user_id=user_id, entry_id=updated_data['id']).first()
            if not row:
                return jsonify({"message": "ID não encontrado!"}), 404
            
            row.value = updated_data['value']
            row.date = updated_data.get('date', row.date)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado atualizado na Tabela 2!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

    if request.method == 'DELETE':
        try:
            entry_id = request.args.get('id')
            row = Table2.query.filter_by(user_id=user_id, entry_id=entry_id).first()
            if not row:
                return jsonify({"message": "ID não encontrado!"}), 404
            
            db.session.delete(row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado deletado da Tabela 2!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": str(e)}), 400

# Inicialização do banco de dados
def init_db():
    with app.app_context():
        db.drop_all()  # Remove todas as tabelas existentes
        db.create_all()  # Cria todas as tabelas novamente
        print("Banco de dados inicializado com sucesso!")

if __name__ == '__main__':
    init_db()  # Inicializa o banco de dados
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)