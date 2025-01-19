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
    table1_entries = db.relationship('Table1', backref='user', lazy=True)
    table2_entries = db.relationship('Table2', backref='user', lazy=True)

# Modelo de Finanças
class Finance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')

# Definindo a estrutura da Tabela 1 com vínculo ao usuário
class Table1(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_id = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    
    # Garante que entry_id seja único para cada usuário
    __table_args__ = (db.UniqueConstraint('user_id', 'entry_id', name='unique_entry_user1'),)

# Definindo a estrutura da Tabela 2 com vínculo ao usuário
class Table2(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_id = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    
    # Garante que entry_id seja único para cada usuário
    __table_args__ = (db.UniqueConstraint('user_id', 'entry_id', name='unique_entry_user2'),)

# [Rotas anteriores permanecem iguais até as rotas das tabelas]

# Rotas atualizadas para manipulação da Tabela 1
@app.route('/api/table1', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table1():
    if 'user_id' not in session:
        return jsonify({"message": "Usuário não autenticado"}), 401
    
    user_id = session['user_id']

    if request.method == 'GET':
        data = Table1.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": row.entry_id,
            "value": row.value,
            "date": row.date
        } for row in data])

    if request.method == 'POST':
        new_data = request.json
        new_row = Table1(
            user_id=user_id,
            entry_id=new_data['id'],
            value=new_data['value'],
            date=new_data['date']
        )
        try:
            db.session.add(new_row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado adicionado à Tabela 1!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "Erro ao adicionar dado"}), 400

    if request.method == 'PUT':
        updated_data = request.json
        row = Table1.query.filter_by(
            user_id=user_id,
            entry_id=updated_data['id']
        ).first()
        
        if row:
            row.value = updated_data['value']
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado atualizado na Tabela 1!"})
        return jsonify({"message": "ID não encontrado!"}), 404

    if request.method == 'DELETE':
        entry_id = request.args.get('id')
        row = Table1.query.filter_by(
            user_id=user_id,
            entry_id=entry_id
        ).first()
        
        if row:
            db.session.delete(row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table1'})
            return jsonify({"message": "Dado deletado da Tabela 1!"})
        return jsonify({"message": "ID não encontrado!"}), 404

# Rotas atualizadas para manipulação da Tabela 2
@app.route('/api/table2', methods=['GET', 'POST', 'PUT', 'DELETE'])
def handle_table2():
    if 'user_id' not in session:
        return jsonify({"message": "Usuário não autenticado"}), 401
    
    user_id = session['user_id']

    if request.method == 'GET':
        data = Table2.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": row.entry_id,
            "value": row.value,
            "date": row.date
        } for row in data])

    if request.method == 'POST':
        new_data = request.json
        new_row = Table2(
            user_id=user_id,
            entry_id=new_data['id'],
            value=new_data['value'],
            date=new_data['date']
        )
        try:
            db.session.add(new_row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado adicionado à Tabela 2!"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"message": "Erro ao adicionar dado"}), 400

    if request.method == 'PUT':
        updated_data = request.json
        row = Table2.query.filter_by(
            user_id=user_id,
            entry_id=updated_data['id']
        ).first()
        
        if row:
            row.value = updated_data['value']
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado atualizado na Tabela 2!"})
        return jsonify({"message": "ID não encontrado!"}), 404

    if request.method == 'DELETE':
        entry_id = request.args.get('id')
        row = Table2.query.filter_by(
            user_id=user_id,
            entry_id=entry_id
        ).first()
        
        if row:
            db.session.delete(row)
            db.session.commit()
            socketio.emit(f'update_graph_{user_id}', {'table': 'table2'})
            return jsonify({"message": "Dado deletado da Tabela 2!"})
        return jsonify({"message": "ID não encontrado!"}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
