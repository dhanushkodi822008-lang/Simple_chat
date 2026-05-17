# Simple_chat

A modern Flask-based chat application with real-time messaging, file sharing, emojis, message edit/delete/forward actions, dark/light themes, and a responsive WhatsApp-style interface.

## Features

- Real-time multi-user chat using Flask SocketIO
- File uploads for images, videos, PDFs, documents, and more
- Emoji support in messages
- Edit or delete your own messages
- Forward messages to the group
- Dark mode / light mode toggle
- Active user list with online count
- Responsive layout for desktop and mobile
- SQLite database persistence for message history

## Project Structure

```
Simple_chat/
├── app.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   ├── uploads/
│   │   ├── images/
│   │   ├── files/
│   │   └── videos/
│   ├── profile/
│   │   └── default.png
│   ├── emojis/
│   ├── stickers/
│   ├── sounds/
│   └── themes/
├── database/
│   └── chat.db
└── README.md
```

## Requirements

- Python 3.8+
- Flask
- Flask-SocketIO

## Install

```powershell
py -3 -m pip install -r requirements.txt
```

## Run

```powershell
py -3 app.py
```

Then open `http://127.0.0.1:5003` in your browser.

## Notes

- File uploads are stored under `static/uploads`
- Message history is stored in `database/chat.db`
- The UI uses Socket.IO for instant chat updates and interaction
