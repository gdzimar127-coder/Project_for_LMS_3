import json
import re
import g4f
from flask import Blueprint, request, jsonify, session
from functools import wraps

ai_bp = Blueprint('ai_generator', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated

def clean_ai_json(text):
    """Убирает markdown-обёртки и мусор, возвращает валидный JSON"""
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)

@ai_bp.route('/api/generate_questions', methods=['POST'])
@login_required
def generate_questions():
    data = request.json
    subject = data.get('subject', 'Математика')
    topic = data.get('topic', 'Общие темы')
    count = min(int(data.get('count', 5)), 15)  # Ограничение до 15 вопросов для стабильности

    prompt = f"""Ты эксперт по подготовке к ОГЭ. Сгенерируй ровно {count} заданий по предмету "{subject}" на тему "{topic}".
Каждое задание должно соответствовать формату ОГЭ. Верни ТОЛЬКО валидный JSON-массив без markdown-обёрток и пояснений.
Формат каждого объекта:
{{
  "question": "текст задания",
  "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4"],
  "correct_answer": "текст правильного ответа",
  "explanation": "краткое пояснение решения"
}}"""

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        questions = clean_ai_json(response)
        for i, q in enumerate(questions):
            q['id'] = f"ai_{i}"
        return jsonify(questions)
    except Exception as e:
        return jsonify({'error': f'Ошибка генерации: {str(e)}'}), 500