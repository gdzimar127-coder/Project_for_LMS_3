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

        # Создание таблиц
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password_hash TEXT NOT NULL
        )''')
        try:
            c.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except:
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

        # Добавление предметов
        if c.execute('SELECT COUNT(*) FROM subjects').fetchone()[0] == 0:
            subjects = [
                (1, 'Математика'), (2, 'Русский язык'), (3, 'Информатика'),
                (4, 'Обществознание'), (5, 'Физика'), (6, 'Биология'),
                (7, 'География'), (8, 'Химия'), (9, 'История'),
                (10, 'Литература'), (11, 'Английский язык'), (12, 'Немецкий язык'),
                (13, 'Французский язык'), (14, 'Испанский язык')
            ]
            c.executemany('INSERT INTO subjects (id, name) VALUES (?, ?)', subjects)

            # РАЗДЕЛЫ КЭС
            all_sections = [
                # Математика
                (1, 'Числа и вычисления', '1'), (1, 'Алгебраические выражения', '2'),
                (1, 'Уравнения и неравенства', '3'), (1, 'Числовые последовательности', '4'),
                (1, 'Функции', '5'), (1, 'Координаты на прямой и плоскости', '6'),
                (1, 'Геометрия', '7'), (1, 'Вероятность и статистика', '8'),

                # Русский язык
                (2, 'Язык и речь', '1'), (2, 'Текст', '2'),
                (2, 'Функциональные разновидности языка', '3'),
                (2, 'Система языка', '4'), (2, 'Культура речи', '5'),
                (2, 'Орфография', '6'), (2, 'Пунктуация', '7'),
                (2, 'Выразительность русской речи', '8'),

                # Информатика
                (3, 'Цифровая грамотность', '1'), (3, 'Теоретические основы', '2'),
                (3, 'Алгоритмы и программирование', '3'), (3, 'Информационные технологии', '4'),

                # Обществознание
                (4, 'Человек и общество', '1'), (4, 'Экономика', '3'),
                (4, 'Политика и право', '5'), (4, 'Социальная сфера', '4'),

                # Физика
                (5, 'Механические явления', '1'), (5, 'Тепловые явления', '2'),
                (5, 'Электромагнитные явления', '3'), (5, 'Квантовые явления', '4'),

                # Биология
                (6, 'Биология как наука', '1'), (6, 'Клетка. Ткани. Органы', '2'),
                (6, 'Система и многообразие органического мира', '3'),
                (6, 'Человек и его здоровье', '4'), (6, 'Экология и эволюция', '5'),

                # География
                (7, 'Источники географической информации', '1'),
                (7, 'Природа Земли и человек', '2'),
                (7, 'Материки и океаны', '3'),
                (7, 'География России: природа', '4'),
                (7, 'Население и хозяйство России', '5'),

                # Химия
                (8, 'Строение атома. Периодическая система', '1'),
                (8, 'Химическая связь. Строение вещества', '2'),
                (8, 'Классы неорганических веществ', '3'),
                (8, 'Химические реакции', '4'),
                (8, 'Растворы. Электролитическая диссоциация', '5'),

                # История
                (9, 'Древняя Русь и удельный период', '1'),
                (9, 'Московское государство (XV–XVII вв.)', '2'),
                (9, 'Россия в XVIII веке', '3'),
                (9, 'Россия в XIX веке', '4'),
                (9, 'Начало XX века и революции', '5'),
                (9, 'СССР (1917–1991)', '6'),

                # ЛИТЕРАТУРА - СОКРАЩЕНО ДО 15 САМЫХ ПОПУЛЯРНЫХ
                (10, '«Слово о полку Игореве»', '1'),
                (10, 'А.С. Грибоедов. «Горе от ума»', '2'),
                (10, 'А.С. Пушкин. Стихотворения', '3'),
                (10, 'А.С. Пушкин. «Евгений Онегин»', '4'),
                (10, 'А.С. Пушкин. «Капитанская дочка»', '5'),
                (10, 'М.Ю. Лермонтов. Стихотворения', '6'),
                (10, 'М.Ю. Лермонтов. «Герой нашего времени»', '7'),
                (10, 'Н.В. Гоголь. «Мёртвые души»', '8'),
                (10, 'Н.В. Гоголь. «Ревизор»', '9'),
                (10, 'И.С. Тургенев. Произведения', '10'),
                (10, 'Ф.М. Достоевский. Произведения', '11'),
                (10, 'Л.Н. Толстой. Произведения', '12'),
                (10, 'А.П. Чехов. Рассказы', '13'),
                (10, 'И.А. Бунин. Произведения', '14'),
                (10, 'М.А. Шолохов. «Тихий Дон»', '15'),

                # Языки
                (11, 'Аудирование', '1'), (11, 'Чтение', '2'),
                (11, 'Грамматика и лексика', '3'), (11, 'Письмо', '4'),
                (12, 'Аудирование', '1'), (12, 'Чтение', '2'),
                (12, 'Грамматика и лексика', '3'),
                (13, 'Аудирование', '1'), (13, 'Чтение', '2'),
                (13, 'Грамматика и лексика', '3'),
                (14, 'Аудирование', '1'), (14, 'Чтение', '2'),
                (14, 'Грамматика и лексика', '3'),
            ]
            c.executemany('INSERT INTO sections (subject_id, name, section_code) VALUES (?, ?, ?)', all_sections)

            # === ЗАДАНИЯ ДЛЯ ВСЕХ ПРЕДМЕТОВ ===
            tasks_data = [
                # МАТЕМАТИКА
                (1, 1, '1.1', 'Натуральные числа', 'easy', 'Вычислите: 3/4 + 1/2', json.dumps(["1", "5/4", "4/6"]),
                 "5/4", "3/4 + 2/4 = 5/4"),
                (1, 1, '1.2', 'Обыкновенные дроби', 'easy', 'Найдите значение: 2/3 * 9/10',
                 json.dumps(["3/5", "2/5", "4/5"]), "3/5", "2/3 * 9/10 = 18/30 = 3/5"),
                (1, 2, '2.1', 'Степень с целым показателем', 'easy', 'Вычислите: 2³', json.dumps(["6", "8", "9"]), "8",
                 "2³ = 2*2*2 = 8"),
                (1, 3, '3.1', 'Линейные уравнения', 'medium', 'Решите: 2x - 4 = 10', json.dumps(["3", "7", "14"]), "7",
                 "2x = 14 => x = 7"),
                (1, 3, '3.2', 'Квадратные уравнения', 'medium', 'Решите: x² - 5x + 6 = 0',
                 json.dumps(["2 и 3", "1 и 6", "-2 и -3"]), "2 и 3", "D = 25-24=1, x=(5±1)/2"),
                (1, 7, '7.1', 'Треугольники', 'medium', 'Найдите площадь треугольника со сторонами 3, 4, 5',
                 json.dumps(["6", "12", "10"]), "6", "Это прямоугольный треугольник: S = 3*4/2 = 6"),
                (1, 8, '8.1', 'Вероятность', 'easy',
                 'В коробке 5 красных и 3 синих шара. Найдите вероятность вытащить красный',
                 json.dumps(["5/8", "3/8", "1/2"]), "5/8", "P = 5/(5+3) = 5/8"),

                # РУССКИЙ ЯЗЫК
                (2, 1, '1.1', 'Орфоэпия', 'easy', 'В каком слове ударение на первый слог?',
                 json.dumps(["дОкумент", "портфЕль", "тОрты"]), "тОрты", "Правильно: тОрты"),
                (2, 6, '6.1', 'Правописание корней', 'medium', 'Укажите слово с проверяемой безударной гласной в корне',
                 json.dumps(["л..сной", "г..ра", "в..да"]), "л..сной", "лес - лесной"),
                (2, 7, '7.1', 'Запятые при однородных членах', 'medium',
                 'Где нужны запятые? "Он читал книги газеты журналы"',
                 json.dumps(["после книги", "после газеты", "нигде"]), "после книги",
                 "Однородные дополнения разделяются запятыми"),

                # ИНФОРМАТИКА
                (3, 1, '1.1', 'Системы счисления', 'easy', 'Переведите 101 из двоичной', json.dumps(["3", "4", "5"]),
                 "5", "1*4 + 0*2 + 1*1 = 5"),
                (3, 2, '2.1', 'Алгебра логики', 'medium', 'Чему равно A & B, если A=1, B=0?',
                 json.dumps(["0", "1", "неопределено"]), "0", "1 & 0 = 0"),
                (3, 3, '3.1', 'Алгоритмы', 'easy', 'Что выведет программа: x=5; x=x+3; print(x)',
                 json.dumps(["5", "8", "3"]), "8", "x = 5+3 = 8"),

                # ОБЩЕСТВОЗНАНИЕ
                (4, 1, '1.1', 'Человек', 'easy', 'Что отличает человека от животного?',
                 json.dumps(["Инстинкты", "Творчество", "Рефлексы"]), "Творчество",
                 "Творчество присуще только человеку"),
                (4, 3, '3.1', 'Экономика', 'medium', 'Что такое инфляция?',
                 json.dumps(["рост цен", "падение цен", "стабильность цен"]), "рост цен",
                 "Инфляция - устойчивый рост общего уровня цен"),

                # ФИЗИКА
                (5, 1, '1.1', 'Механика', 'easy', 'Единица измерения силы', json.dumps(["Ньютон", "Джоуль", "Ватт"]),
                 "Ньютон", "Сила измеряется в Ньютонах"),
                (5, 2, '2.1', 'Тепловые явления', 'medium', 'Формула количества теплоты',
                 json.dumps(["Q=mcΔT", "Q=F/S", "Q=mv"]), "Q=mcΔT", "Q = mcΔT - количество теплоты"),

                # БИОЛОГИЯ
                (6, 2, '2.1', 'Клетка', 'easy', 'Какой органоид отвечает за синтез белка?',
                 json.dumps(["Митохондрия", "Рибосома", "Ядро"]), "Рибосома", "Рибосомы синтезируют белки"),
                (6, 4, '4.1', 'Человек', 'medium', 'Сколько камер в сердце человека?', json.dumps(["2", "3", "4"]), "4",
                 "Два предсердия и два желудочка"),

                # ГЕОГРАФИЯ
                (7, 2, '2.1', 'Атмосфера', 'easy', 'В каком слое атмосферы формируется погода?',
                 json.dumps(["Тропосфера", "Стратосфера", "Мезосфера"]), "Тропосфера",
                 "Погода формируется в тропосфере"),
                (7, 5, '5.1', 'Население России', 'medium', 'Самый многочисленный народ России',
                 json.dumps(["татары", "русские", "башкиры"]), "русские", "Русские составляют около 80% населения"),

                # ХИМИЯ
                (8, 1, '1.1', 'Атом', 'easy', 'Заряд ядра атома углерода', json.dumps(["+4", "+6", "+12"]), "+6",
                 "Порядковый номер углерода 6, заряд ядра +6"),
                (8, 3, '3.1', 'Классы веществ', 'medium', 'К какому классу относится NaOH?',
                 json.dumps(["кислота", "основание", "соль"]), "основание", "NaOH - гидроксид натрия, щёлочь"),

                # ИСТОРИЯ
                (9, 1, '1.1', 'Древняя Русь', 'easy', 'В каком году произошло Крещение Руси?',
                 json.dumps(["882", "988", "1015"]), "988", "Крещение Руси при Владимире I в 988 году"),
                (9, 6, '6.1', 'СССР', 'medium', 'Когда образовался СССР?', json.dumps(["1917", "1922", "1924"]), "1922",
                 "СССР образован 30 декабря 1922 года"),

                # ЛИТЕРАТУРА
                (10, 3, '3.1', 'Пушкин', 'easy', 'Автор романа «Евгений Онегин»',
                 json.dumps(["Лермонтов", "Пушкин", "Толстой"]), "Пушкин", "А.С. Пушкин написал «Евгений Онегин»"),
                (10, 8, '8.1', 'Гоголь', 'medium', 'Жанр произведения «Мёртвые души»',
                 json.dumps(["роман", "поэма", "повесть"]), "поэма", "Гоголь определил жанр как поэма"),

                # АНГЛИЙСКИЙ ЯЗЫК
                (11, 3, '3.1', 'Грамматика', 'easy', 'Choose: She ___ to school every day',
                 json.dumps(["go", "goes", "going"]), "goes", "Present Simple, 3rd person singular"),
                (11, 3, '3.2', 'Времена', 'medium', 'Выберите Past Simple: I ___ yesterday',
                 json.dumps(["go", "went", "gone"]), "went", "went - Past Simple от go"),
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
    subjects = get_db().execute('SELECT * FROM subjects ORDER BY id').fetchall()
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
    subjects = get_db().execute('SELECT * FROM subjects').fetchall()
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