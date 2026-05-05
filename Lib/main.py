import os
import sqlite3
import re
import json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from generating import gen_bp

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-me-in-production'
DB_PATH = 'users.db'

app.register_blueprint(gen_bp)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with app.app_context():
        conn = get_db()
        c = conn.cursor()

        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL
        )''')

        try:
            c.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute('''CREATE TABLE IF NOT EXISTS sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            section_code TEXT,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            section_id INTEGER,
            fipi_code TEXT,
            topic_name TEXT,
            difficulty TEXT,
            question_text TEXT NOT NULL,
            options_json TEXT,
            correct_answer TEXT NOT NULL,
            solution_text TEXT,
            FOREIGN KEY(subject_id) REFERENCES subjects(id),
            FOREIGN KEY(section_id) REFERENCES sections(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            score REAL,
            time_spent INTEGER,
            mode TEXT DEFAULT 'practice',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS attempt_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            user_answer TEXT,
            is_correct INTEGER,
            FOREIGN KEY(attempt_id) REFERENCES attempts(id) ON DELETE CASCADE
        )''')

        if c.execute('SELECT COUNT(*) FROM subjects').fetchone()[0] == 0:
            subjects = [
                (1, 'Математика'), (2, 'Русский язык'), (3, 'Информатика'),
                (4, 'Обществознание'), (5, 'Физика'), (6, 'Биология'),
                (7, 'География'), (8, 'Химия'), (9, 'История'),
                (10, 'Литература'), (11, 'Английский язык'), (12, 'Немецкий язык'),
                (13, 'Французский язык'), (14, 'Испанский язык')
            ]
            c.executemany('INSERT INTO subjects (id, name) VALUES (?, ?)', subjects)

            all_sections = [
                (1, 'Числа и вычисления', '1'), (1, 'Алгебраические выражения', '2'),
                (1, 'Уравнения и неравенства', '3'), (1, 'Числовые последовательности', '4'),
                (1, 'Функции', '5'), (1, 'Координаты на прямой и плоскости', '6'),
                (1, 'Геометрия', '7'), (1, 'Вероятность и статистика', '8'),
                (2, 'Язык и речь', '1'), (2, 'Текст', '2'),
                (2, 'Функциональные разновидности языка', '3'),
                (2, 'Система языка', '4'), (2, 'Культура речи', '5'),
                (2, 'Орфография', '6'), (2, 'Пунктуация', '7'),
                (2, 'Выразительность русской речи', '8'),
                (3, 'Цифровая грамотность', '1'), (3, 'Теоретические основы', '2'),
                (3, 'Алгоритмы и программирование', '3'), (3, 'Информационные технологии', '4'),
                (4, 'Человек и общество', '1'), (4, 'Экономика', '3'),
                (4, 'Политика и право', '5'), (4, 'Социальная сфера', '4'),
                (5, 'Механические явления', '1'), (5, 'Тепловые явления', '2'),
                (5, 'Электромагнитные явления', '3'), (5, 'Квантовые явления', '4'),
                (6, 'Биология как наука', '1'), (6, 'Человек и здоровье', '7'),
                (7, 'География России', '7'), (7, 'Оболочки Земли', '4'),
                (8, 'Первоначальные химические понятия', '1'), (8, 'Химические реакции', '5'),
                (9, 'От Руси к Российскому государству', '1'), (9, 'История России XX века', '4'),
                (10, '«Слово о полку Игореве»', '1'), (10, 'М.В. Ломоносов. Стихотворения', '2'),
                (10, 'Д.И. Фонвизин. Комедия «Недоросль»', '3'),
                (10, 'Г.Р. Державин. Стихотворения', '4'),
                (10, 'Н.М. Карамзин. Повесть «Бедная Лиза»', '5'),
                (10, 'И.А. Крылов. Басни', '6'),
                (10, 'В.А. Жуковский. Стихотворения. Баллады', '7'),
                (10, 'А.С. Грибоедов. Комедия «Горе от ума»', '8'),
                (10, 'А.С. Пушкин. Стихотворения', '9'),
                (10, 'А.С. Пушкин. Роман «Евгений Онегин»', '10'),
                (10, 'А.С. Пушкин. «Повести Белкина»', '11'),
                (10, 'А.С. Пушкин. Поэма «Медный всадник»', '12'),
                (10, 'А.С. Пушкин. Роман «Капитанская дочка»', '13'),
                (10, 'М.Ю. Лермонтов. Стихотворения', '14'),
                (10, 'М.Ю. Лермонтов. Поэма «Песня про купца Калашникова»', '15'),
                (10, 'М.Ю. Лермонтов. Поэма «Мцыри»', '16'),
                (10, 'М.Ю. Лермонтов. Роман «Герой нашего времени»', '17'),
                (10, 'Н.В. Гоголь. Комедия «Ревизор»', '18'),
                (10, 'Н.В. Гоголь. Повесть «Шинель»', '19'),
                (10, 'Н.В. Гоголь. Поэма «Мёртвые души»', '20'),
                (10, 'Поэзия пушкинской эпохи', '21'),
                (10, 'И.С. Тургенев. Произведения', '22'),
                (10, 'Н.С. Лесков. Произведения', '23'),
                (10, 'Ф.И. Тютчев. Стихотворения', '24'),
                (10, 'А.А. Фет. Стихотворения', '25'),
                (10, 'Н.А. Некрасов. Стихотворения', '26'),
                (10, 'М.Е. Салтыков-Щедрин. Сказки', '27'),
                (10, 'Ф.М. Достоевский. Произведения', '28'),
                (10, 'Л.Н. Толстой. Произведения', '29'),
                (10, 'А.П. Чехов. Рассказы', '30'),
                (10, 'А.К. Толстой. Стихотворения', '31'),
                (10, 'И.А. Бунин. Стихотворения', '32'),
                (10, 'А.А. Блок. Стихотворения', '33'),
                (10, 'В.В. Маяковский. Стихотворения', '34'),
                (10, 'С.А. Есенин. Стихотворения', '35'),
                (10, 'Н.С. Гумилёв. Стихотворения', '36'),
                (10, 'М.И. Цветаева. Стихотворения', '37'),
                (10, 'О.Э. Мандельштам. Стихотворения', '38'),
                (10, 'Б.Л. Пастернак. Стихотворения', '39'),
                (10, 'А.И. Куприн. Произведения', '40'),
                (10, 'М.А. Шолохов. Рассказ «Судьба человека»', '41'),
                (10, 'А.Т. Твардовский. Поэма «Василий Тёркин»', '42'),
                (10, 'В.М. Шукшин. Рассказы', '43'),
                (10, 'А.И. Солженицын. Рассказ «Матрёнин двор»', '44'),
                (10, 'Авторы прозы XX–XXI вв.', '45'),
                (10, 'Авторы лирики XX–XXI вв.', '46'),
                (10, 'Произведения зарубежной литературы', '47'),
                (11, 'Коммуникативные умения', '1'), (11, 'Языковые знания', '2'),
                (12, 'Коммуникативные умения', '1'), (12, 'Языковые знания', '2'),
                (13, 'Коммуникативные умения', '1'), (13, 'Языковые знания', '2'),
                (14, 'Коммуникативные умения', '1'), (14, 'Языковые знания', '2'),
            ]
            c.executemany('INSERT INTO sections (subject_id, name, section_code) VALUES (?, ?, ?)', all_sections)

            tasks_data = [
                (1, 1, '1.1', 'Натуральные числа', 'easy', 'Вычислите: 3/4 + 1/2', json.dumps(["1", "5/4", "4/6"]),
                 "5/4", "3/4 + 2/4 = 5/4"),
                (1, 3, '3.1', 'Уравнения', 'medium', 'Решите: 2x - 4 = 10', json.dumps(["3", "7", "14"]), "7",
                 "2x = 14 => x = 7"),
                (2, 1, '1.1', 'Орфоэпия', 'easy', 'В каком слове ударение на первый слог?',
                 json.dumps(["дОкумент", "портфЕль", "тОрты"]), "тОрты", "Правильно: тОрты"),
                (3, 1, '1.1', 'Системы счисления', 'easy', 'Переведите 101 из двоичной:', json.dumps(["3", "4", "5"]),
                 "5", "1*4 + 0*2 + 1*1 = 5"),
                (4, 1, '1.1', 'Человек', 'easy', 'Что отличает человека от животного?',
                 json.dumps(["Инстинкты", "Творчество", "Рефлексы"]), "Творчество",
                 "Творчество присуще только человеку"),
                (5, 1, '1.1', 'Механика', 'easy', 'Единица измерения силы:', json.dumps(["Ньютон", "Джоуль", "Ватт"]),
                 "Ньютон", "Сила измеряется в Ньютонах"),
            ]
            for t in tasks_data:
                c.execute('''INSERT INTO tasks 
                    (subject_id, section_id, fipi_code, topic_name, difficulty, question_text, options_json, correct_answer, solution_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', t)
            conn.commit()
        conn.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated


@app.route('/')
def index():
    return render_template('index_main.html', username=session.get('username'))


@app.route('/login', methods=['POST'])
def login():
    u, p = request.form.get('username', '').strip(), request.form.get('password', '').strip()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (u,)).fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'], p):
        session['username'] = u
        session['user_id'] = user['id']
        return redirect(url_for('index'))
    flash('Неверный логин или пароль', 'error')
    return redirect(url_for('index'))


@app.route('/register', methods=['POST'])
def register():
    u, e, p = request.form.get('username', '').strip(), request.form.get('email', '').strip(), request.form.get(
        'password', '').strip()
    if len(p) < 6 or not re.search(r'\d', p) or not re.search(r'[A-Za-z]', p):
        flash('Пароль: мин. 6 символов, буква и цифра', 'error')
        return redirect(url_for('index'))
    conn = get_db()
    if conn.execute('SELECT id FROM users WHERE username = ?', (u,)).fetchone():
        flash('Логин занят', 'error')
        conn.close()
        return redirect(url_for('index'))
    conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                 (u, e, generate_password_hash(p)))
    conn.commit()
    conn.close()
    session['username'] = u
    flash('Регистрация успешна!', 'success')
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли', 'info')
    return redirect(url_for('index'))


@app.route('/subjects')
def subjects_page():
    conn = get_db()
    subjects = conn.execute('SELECT * FROM subjects ORDER BY id').fetchall()
    conn.close()
    return render_template('subjects.html', subjects=subjects, username=session.get('username'))


@app.route('/topics/<int:subject_id>')
@login_required
def topics_page(subject_id):
    conn = get_db()
    subject = conn.execute('SELECT * FROM subjects WHERE id = ?', (subject_id,)).fetchone()
    sections = conn.execute('SELECT * FROM sections WHERE subject_id = ? ORDER BY section_code',
                            (subject_id,)).fetchall()
    tasks = conn.execute('SELECT DISTINCT fipi_code, topic_name FROM tasks WHERE subject_id = ?',
                         (subject_id,)).fetchall()
    conn.close()
    return render_template('topics.html', subject=subject, sections=sections, tasks=tasks, username=session['username'])


@app.route('/training')
@login_required
def training():
    conn = get_db()
    subjects = conn.execute('SELECT * FROM subjects').fetchall()
    conn.close()
    return render_template('training.html', subjects=subjects, username=session['username'])


@app.route('/profile')
@login_required
def profile():
    return render_template('stats.html', username=session['username'])


@app.route('/info')
def info():
    return render_template('info.html')


@app.route('/alisa')
@login_required
def alisa_chat():
    return render_template('alisa.html', username=session['username'])


# === API ===
@app.route('/api/subjects')
def api_subjects():
    conn = get_db()
    subs = conn.execute('SELECT * FROM subjects').fetchall()
    conn.close()
    return jsonify([dict(r) for r in subs])


@app.route('/api/sections')
def api_sections():
    subject_id = request.args.get('subject_id')
    conn = get_db()
    if subject_id:
        sections = conn.execute('SELECT * FROM sections WHERE subject_id = ? ORDER BY section_code',
                                (subject_id,)).fetchall()
    else:
        sections = conn.execute('SELECT * FROM sections ORDER BY subject_id, section_code').fetchall()
    conn.close()
    return jsonify([dict(r) for r in sections])


@app.route('/api/tasks')
def api_tasks():
    conn = get_db()
    q = """SELECT t.*, s.name as subject_name, sec.name as section_name
           FROM tasks t JOIN subjects s ON t.subject_id = s.id
           LEFT JOIN sections sec ON t.section_id = sec.id WHERE 1=1"""
    params = []
    if request.args.get('subject_id'):
        q += " AND t.subject_id = ?";
        params.append(request.args.get('subject_id'))
    if request.args.get('section_id'):
        q += " AND t.section_id = ?";
        params.append(request.args.get('section_id'))
    if request.args.get('fipi_code'):
        q += " AND t.fipi_code = ?";
        params.append(request.args.get('fipi_code'))
    q += " ORDER BY t.section_id, t.fipi_code LIMIT ?"
    params.append(request.args.get('limit', 10))
    tasks = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in tasks])


@app.route('/api/start_test', methods=['POST'])
@login_required
def start_test():
    data = request.get_json()
    conn = get_db()
    user_id = conn.execute('SELECT id FROM users WHERE username = ?', (session['username'],)).fetchone()['id']
    aid = conn.execute('''INSERT INTO attempts (user_id, subject_id, started_at, mode)
                          VALUES (?, ?, ?, ?)''',
                       (user_id, data.get('subject_id'), datetime.now().isoformat(), 'practice')).lastrowid
    conn.commit()
    conn.close()
    return jsonify({'attempt_id': aid})


@app.route('/api/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    data = request.get_json()
    conn = get_db()
    task = conn.execute('SELECT correct_answer FROM tasks WHERE id = ?', (data['task_id'],)).fetchone()
    is_correct = 1 if task and task['correct_answer'].strip().lower() == str(data['answer']).strip().lower() else 0
    conn.execute('''INSERT INTO attempt_answers (attempt_id, task_id, user_answer, is_correct) 
                    VALUES (?, ?, ?, ?)''', (data['attempt_id'], data['task_id'], data['answer'], is_correct))
    conn.commit()
    conn.close()
    return jsonify({'correct': bool(is_correct), 'expected': task['correct_answer'] if task else ''})


@app.route('/api/finish_test', methods=['POST'])
@login_required
def finish_test():
    data = request.get_json()
    conn = get_db()
    stats = conn.execute(
        'SELECT COUNT(*) as total, SUM(is_correct) as correct FROM attempt_answers WHERE attempt_id = ?',
        (data['attempt_id'],)).fetchone()
    total = stats['total'] or 0
    correct = stats['correct'] or 0
    score = (correct / total * 100) if total > 0 else 0
    conn.execute('''UPDATE attempts SET finished_at = ?, time_spent = ?, score = ? WHERE id = ?''',
                 (datetime.now().isoformat(), data.get('time_spent', 0), score, data['attempt_id']))
    conn.commit()
    conn.close()
    return jsonify({'score': round(score, 1), 'correct': correct, 'total': total, 'percentage': f"{round(score)}%"})


@app.route('/api/profile/stats')
@login_required
def profile_stats():
    conn = get_db()
    user_id = conn.execute('SELECT id FROM users WHERE username = ?', (session['username'],)).fetchone()['id']
    attempts = conn.execute(
        'SELECT s.name, a.score, a.finished_at FROM attempts a JOIN subjects s ON a.subject_id = s.id WHERE a.user_id = ? ORDER BY a.finished_at DESC',
        (user_id,)).fetchall()
    res = [{'subject': a['name'], 'score': a['score'], 'date': a['finished_at']} for a in attempts]
    conn.close()
    return jsonify({'history': res})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)