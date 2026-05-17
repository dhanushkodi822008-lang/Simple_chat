import os
import sqlite3
import datetime
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'database' / 'chat.db'
UPLOAD_BASE = BASE_DIR / 'static' / 'uploads'
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg',
    'mp4', 'webm', 'ogg', 'mov',
    'pdf', 'doc', 'docx', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf'
}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg', 'mov'}

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret!')
app.config['UPLOAD_FOLDER'] = UPLOAD_BASE
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

users = {}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            username TEXT,
            text TEXT,
            timestamp TEXT,
            message_type TEXT,
            file_url TEXT,
            file_name TEXT,
            edited INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            forwarded_from TEXT
        )
        '''
    )
    conn.commit()
    conn.close()


def sanitize_message_row(row):
    return {
        'id': row['id'],
        'username': row['username'],
        'text': row['text'],
        'timestamp': row['timestamp'],
        'message_type': row['message_type'],
        'file_url': row['file_url'],
        'file_name': row['file_name'],
        'edited': bool(row['edited']),
        'deleted': bool(row['deleted']),
        'forwarded_from': row['forwarded_from']
    }


def insert_message(username, text, message_type='text', file_url=None, file_name=None, forwarded_from=None):
    msg_id = uuid.uuid4().hex
    timestamp = datetime.datetime.now().strftime('%H:%M')
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO messages (id, username, text, timestamp, message_type, file_url, file_name, forwarded_from) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (msg_id, username, text, timestamp, message_type, file_url, file_name, forwarded_from)
    )
    conn.commit()
    row = conn.execute('SELECT * FROM messages WHERE id = ?', (msg_id,)).fetchone()
    conn.close()
    return sanitize_message_row(row)


def load_recent_messages(limit=100):
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM messages ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [sanitize_message_row(row) for row in reversed(rows)]


def get_message_by_id(message_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM messages WHERE id = ?', (message_id,)).fetchone()
    conn.close()
    return row


def update_message(message_id, new_text):
    conn = get_db_connection()
    conn.execute(
        'UPDATE messages SET text = ?, edited = 1 WHERE id = ? AND deleted = 0',
        (new_text, message_id)
    )
    conn.commit()
    row = conn.execute('SELECT * FROM messages WHERE id = ?', (message_id,)).fetchone()
    conn.close()
    return sanitize_message_row(row) if row else None


def delete_message(message_id):
    conn = get_db_connection()
    conn.execute('UPDATE messages SET deleted = 1, text = ? WHERE id = ?', ('', message_id))
    conn.commit()
    conn.close()


def allowed_file(filename):
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return extension in ALLOWED_EXTENSIONS


def get_upload_folder(filename):
    extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if extension in IMAGE_EXTENSIONS:
        return 'images'
    if extension in VIDEO_EXTENSIONS:
        return 'videos'
    return 'files'


init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'No file uploaded'}), 400

    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({'error': 'File type not allowed'}), 400

    folder_name = get_upload_folder(filename)
    target_dir = UPLOAD_BASE / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = target_dir / stored_filename
    file.save(file_path)

    file_url = url_for('static', filename=f'uploads/{folder_name}/{stored_filename}')
    message_type = 'image' if folder_name == 'images' else 'video' if folder_name == 'videos' else 'file'

    return jsonify({
        'file_url': file_url,
        'filename': filename,
        'message_type': message_type
    })


@socketio.on('join')
def on_join(data):
    username = data.get('username', 'Guest')
    users[request.sid] = username
    join_room('general')
    emit('user_joined', {'username': username}, broadcast=True, room='general')
    update_online_count()
    emit('chat_history', load_recent_messages(), room=request.sid)


@socketio.on('message')
def handle_message(data):
    username = users.get(request.sid, 'Unknown')
    text = data.get('message', '').strip()
    message_type = data.get('message_type', 'text')
    file_url = data.get('file_url')
    file_name = data.get('file_name')
    forwarded_from = data.get('forwarded_from')

    if message_type == 'text' and text == '' and not file_url:
        return

    message = insert_message(
        username=username,
        text=text,
        message_type=message_type,
        file_url=file_url,
        file_name=file_name,
        forwarded_from=forwarded_from
    )
    emit('message', message, broadcast=True, room='general')


@socketio.on('edit_message')
def edit_message(data):
    message_id = data.get('id')
    new_text = data.get('message', '').strip()
    username = users.get(request.sid, 'Unknown')

    original = get_message_by_id(message_id)
    if not original or original['username'] != username or original['deleted']:
        return

    updated = update_message(message_id, new_text)
    if updated:
        emit('message_updated', updated, broadcast=True, room='general')


@socketio.on('delete_message')
def remove_message(data):
    message_id = data.get('id')
    username = users.get(request.sid, 'Unknown')

    original = get_message_by_id(message_id)
    if not original or original['username'] != username:
        return

    delete_message(message_id)
    emit('message_deleted', {'id': message_id}, broadcast=True, room='general')


@socketio.on('forward_message')
def forward_message(data):
    message_id = data.get('id')
    original = get_message_by_id(message_id)
    if not original or original['deleted']:
        return

    forwarded = insert_message(
        username=users.get(request.sid, 'Unknown'),
        text=original['text'],
        message_type=original['message_type'],
        file_url=original['file_url'],
        file_name=original['file_name'],
        forwarded_from=original['username']
    )
    emit('message', forwarded, broadcast=True, room='general')


@socketio.on('disconnect')
def on_disconnect():
    username = users.pop(request.sid, None)
    if username:
        leave_room('general')
        emit('user_left', {'username': username}, broadcast=True, room='general')
        update_online_count()


def update_online_count():
    active_users = list(users.values())
    socketio.emit('online_count', {'count': len(active_users), 'users': active_users}, room='general')


if __name__ == '__main__':
    print('🚀 Simple Chat Server running')
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), allow_unsafe_werkzeug=True)
