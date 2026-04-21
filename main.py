import os
import sqlite3
import re  # ← Добавляем для проверки пароля

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
DB_PATH = 'users.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with app.app_context():
        conn = get_db()
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL)''')
        conn.commit()
        conn.close()


def is_password_strong(password):
    if len(password) < 6:
        return False, "Пароль должен содержать минимум 6 символов"
    if not re.search(r'[A-Za-zА-Яа-я]', password):
        return False, "Пароль должен содержать хотя бы одну букву"
    if not re.search(r'\d', password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    return True, ""


@app.route('/')
def index():
    return render_template('index_main.html', username=session.get('username'))


@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        flash('Заполните все поля')
        return redirect(url_for('index'))

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['username'] = username
        flash('Вы успешно вошли!')
    else:
        flash('Неверный логин или пароль')

    return redirect(url_for('index'))


@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not password:
        flash('Заполните все поля')
        return redirect(url_for('index'))

    is_strong, error_msg = is_password_strong(password)
    if not is_strong:
        flash(error_msg)
        return redirect(url_for('index'))

    conn = get_db()

    if conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
        flash('Пользователь с таким логином уже существует')
        conn.close()
        return redirect(url_for('index'))

    pwd_hash = generate_password_hash(password)
    conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, pwd_hash))
    conn.commit()
    conn.close()

    session['username'] = username
    flash('Регистрация прошла успешно!')
    return redirect(url_for('index'))


@app.route('/info')
def info():
    return render_template('info.html')


@app.route('/training')
def training():
    return render_template('training.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Вы вышли из аккаунта')
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(port=5000)
