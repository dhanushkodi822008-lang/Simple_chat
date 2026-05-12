from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store online users
users = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    username = data['username']
    users[request.sid] = username
    
    join_room('general')
    emit('user_joined', {'username': username}, broadcast=True, room='general')
    update_online_count()

@socketio.on('message')
def handle_message(data):
    username = users.get(request.sid, "Unknown")
    timestamp = datetime.datetime.now().strftime("%H:%M")
    
    message_data = {
        'username': username,
        'message': data['message'],
        'timestamp': timestamp
    }
    
    emit('message', message_data, broadcast=True, room='general')

@socketio.on('disconnect')
def on_disconnect():
    username = users.pop(request.sid, None)
    if username:
        leave_room('general')
        emit('user_left', {'username': username}, broadcast=True, room='general')
        update_online_count()

def update_online_count():
    count = len(users)
    socketio.emit('online_count', count, room='general')

if __name__ == '__main__':
    print("🚀 Simple Chat Server running on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)