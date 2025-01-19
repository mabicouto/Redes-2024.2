from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = 'minha-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

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


@app.route('/')
def index():
    return render_template('index.html')


# Rota para Tabela 1
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

# Rota para Tabela 2
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
