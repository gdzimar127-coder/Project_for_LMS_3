import re
import json
import g4f
from flask import Blueprint, render_template_string, request, jsonify, session
from functools import wraps

gen_bp = Blueprint('generating', __name__)

# Хранилище истории чатов в памяти (ключ: username_subject_topic)
chat_histories = {}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)

    return decorated


def clean_json_response(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("Не удалось распознать JSON в ответе нейросети")


@gen_bp.route('/generate_question', methods=['POST'])
@login_required
def generate_question():
    data = request.json
    subject = data.get('subject', 'Математика')
    topic = data.get('topic', 'Базовые темы')

    prompt = f"""Ты эксперт по составлению заданий ОГЭ. Сгенерируй ОДНО задание по предмету "{subject}" на тему "{topic}".
Верни ТОЛЬКО валидный JSON без markdown-обёрток и пояснений в следующем формате:
{{
  "question": "текст задания",
  "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4"],
  "correct_answer": "текст правильного ответа (должен точно совпадать с одним из вариантов)",
  "explanation": "краткое пояснение решения"
}}"""

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600
        )
        return jsonify(clean_json_response(response))
    except Exception as e:
        return jsonify({'error': f'Ошибка генерации: {str(e)}'}), 500


@gen_bp.route('/tutor_chat')
@login_required
def tutor_chat():
    subject = request.args.get('subject', '')
    topic = request.args.get('topic', '')
    return render_template_string(TUTOR_HTML, subject=subject, topic=topic)


@gen_bp.route('/tutor_api', methods=['POST'])
@login_required
def tutor_api():
    data = request.json
    user_msg = data.get('message', '').strip()
    subject = data.get('subject', '')
    topic = data.get('topic', '')

    key = f"{session['username']}_{subject}_{topic}"
    if key not in chat_histories:
        chat_histories[key] = [{
            "role": "system",
            "content": f"Ты опытный репетитор ОГЭ по предмету '{subject}'. Твоя задача — подробно и понятно объяснить тему '{topic}' ученику. Используй примеры, задавай уточняющие вопросы, не давай готовые ответы сразу, а веди к ним. Отвечай только на русском языке. Сохраняй дружелюбный и профессиональный тон."
        }]

    chat_histories[key].append({"role": "user", "content": user_msg})

    if len(chat_histories[key]) > 21:
        chat_histories[key] = [chat_histories[key][0]] + chat_histories[key][-20:]

    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=chat_histories[key],
            max_tokens=1000
        )
        chat_histories[key].append({"role": "assistant", "content": response})
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': f'Ошибка чата: {str(e)}'}), 500


TUTOR_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Репетитор: {{ subject }}</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #f5f7fa; margin: 0; padding: 20px; }
        .chat-container { max-width: 900px; margin: 0 auto; background: #fff; border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); overflow: hidden; display: flex; flex-direction: column; height: 90vh; }
        .chat-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px 20px; font-size: 1.2em; display: flex; justify-content: space-between; align-items: center; }
        .chat-header a { color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 8px; font-size: 0.9em; }
        .chat-messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; background: #f9fafb; }
        .message { max-width: 85%; padding: 12px 16px; border-radius: 16px; line-height: 1.5; position: relative; word-wrap: break-word; white-space: pre-wrap; }
        .user-msg { background: #e0f2fe; align-self: flex-end; border-bottom-right-radius: 4px; }
        .ai-msg { background: #ffffff; border: 1px solid #e2e8f0; align-self: flex-start; border-bottom-left-radius: 4px; }
        .chat-input { display: flex; padding: 16px; border-top: 1px solid #e2e8f0; background: #fff; }
        .chat-input input { flex: 1; padding: 12px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 1em; outline: none; transition: border 0.2s; }
        .chat-input input:focus { border-color: #667eea; }
        .chat-input button { margin-left: 10px; padding: 0 24px; background: #667eea; color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: 500; transition: background 0.2s; }
        .chat-input button:hover { background: #5568d8; }
        .loading { color: #64748b; font-style: italic; padding: 8px; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            👨‍🏫 Репетитор ОГЭ: {{ subject }} | Тема: {{ topic }}
            <a href="javascript:history.back()">← Назад к темам</a>
        </div>
        <div class="chat-messages" id="messages"></div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Задайте вопрос по теме или попросите объяснить пример..." autocomplete="off">
            <button onclick="sendMessage()">Отправить</button>
        </div>
    </div>
    <script>
        const messagesDiv = document.getElementById('messages');
        const subject = "{{ subject }}";
        const topic = "{{ topic }}";

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const msg = input.value.trim();
            if (!msg) return;

            addMessage(msg, 'user-msg');
            input.value = '';
            input.disabled = true;

            const loading = document.createElement('div');
            loading.className = 'message loading';
            loading.textContent = '🤖 Думает...';
            messagesDiv.appendChild(loading);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            try {
                const res = await fetch('/tutor_api', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, subject: subject, topic: topic})
                });
                const data = await res.json();
                loading.remove();
                input.disabled = false;
                addMessage(data.response || '❌ Не удалось получить ответ', 'ai-msg');
            } catch (e) {
                loading.remove();
                input.disabled = false;
                addMessage('⚠️ Ошибка соединения с сервером', 'ai-msg');
            }
        }

        function addMessage(text, className) {
            const div = document.createElement('div');
            div.className = 'message ' + className;
            div.textContent = text;
            messagesDiv.appendChild(div);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        document.getElementById('userInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        window.onload = () => {
            addMessage("Здравствуйте! Я ваш виртуальный репетитор. Давайте разберём тему «{{ topic }}» по предмету «{{ subject }}». С чего начнём?", 'ai-msg');
        };
    </script>
</body>
</html>
"""