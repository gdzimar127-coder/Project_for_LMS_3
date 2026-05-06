import g4f
import re
import json
from flask import Blueprint, render_template_string, request, jsonify, session
from functools import wraps

gen_bp = Blueprint('generating', __name__)
chat_histories = {}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)

    return decorated


@gen_bp.route('/tutor_chat')
@login_required
def tutor_chat():
    subject = request.args.get('subject', '')
    topic = request.args.get('topic', '')
    username = session.get('username', 'ученик')

    # ✅ Определяем, пришёл ли пользователь с главной страницы
    is_from_main = subject in ['Общий вопрос', '', 'General']

    key = f"{username}_{subject}_{topic}"

    if key not in chat_histories:
        if is_from_main:
            # ✅ Ваше приветствие при переходе с главной
            system_prompt = f"Ты опытный репетитор ОГЭ/ЕГЭ. Обращайся к ученику по имени '{username}'. Будь дружелюбным, объясняй понятно, с примерами. Отвечай только на русском."
            greeting = f"Здравствуйте {username}, я ваш репетитор для подготовки к ОГЭ/ЕГЭ, давайте разберем непонятную тему. С чего начнём?"
        else:
            # Стандартное приветствие для конкретной темы
            system_prompt = f"Ты репетитор ОГЭ по предмету '{subject}'. Объясняй тему '{topic}' подробно. Отвечай на русском."
            greeting = f"Здравствуйте! Я репетитор по предмету '{subject}'. Какая тема вас интересует?"

        chat_histories[key] = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": greeting}
        ]

    return render_template_string(TUTOR_HTML,
                                  subject=subject,
                                  topic=topic,
                                  username=username,
                                  greeting=greeting,
                                  is_from_main=is_from_main)


@gen_bp.route('/tutor_api', methods=['POST'])
@login_required
def tutor_api():
    data = request.json
    user_msg = data.get('message', '').strip()
    subject = data.get('subject', '')
    topic = data.get('topic', '')
    username = session.get('username', 'ученик')

    key = f"{username}_{subject}_{topic}"
    if key not in chat_histories:
        chat_histories[key] = [{"role": "system", "content": "Ты репетитор ОГЭ/ЕГЭ. Отвечай только по теме."}]

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
    <title>Репетитор: {{ subject or 'Общий вопрос' }}</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }
        .chat-box { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); height: 85vh; display: flex; flex-direction: column; }
        .header { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; border-radius: 12px 12px 0 0; }
        .header h3 { margin: 0; font-size: 1.1rem; }
        .header a { color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 6px; font-size: 0.9rem; }
        .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
        .msg { max-width: 85%; padding: 12px 16px; border-radius: 16px; line-height: 1.5; white-space: pre-wrap; }
        .user { background: #dbeafe; color: #1e40af; align-self: flex-end; border-bottom-right-radius: 4px; }
        .ai { background: #f1f5f9; border: 1px solid #e2e8f0; align-self: flex-start; border-bottom-left-radius: 4px; }
        .input-area { padding: 16px 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; }
        input { flex: 1; padding: 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 1rem; }
        button { padding: 12px 20px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; }
        button:hover { background: #5568d8; }
    </style>
</head>
<body>
    <div class="chat-box">
        <div class="header">
            <h3>👨‍🏫 Репетитор{% if subject and subject != 'Общий вопрос' %}: {{ subject }}{% endif %}</h3>
            <a href="javascript:history.back()">← Назад</a>
        </div>
        <div class="messages" id="msgs">
            <!-- ✅ Приветствие при загрузке -->
            <div class="msg ai">{{ greeting }}</div>
        </div>
        <div class="input-area">
            <input id="inp" placeholder="Задайте вопрос..." onkeydown="if(event.key==='Enter')send()">
            <button onclick="send()">Отправить</button>
        </div>
    </div>
    <script>
        const msgs = document.getElementById('msgs');
        const inp = document.getElementById('inp');
        const subject = "{{ subject }}";
        const topic = "{{ topic }}";

        async function send() {
            const txt = inp.value.trim();
            if(!txt) return;

            // Сообщение пользователя
            const userDiv = document.createElement('div');
            userDiv.className = 'msg user';
            userDiv.textContent = txt;
            msgs.appendChild(userDiv);

            inp.value = '';
            inp.disabled = true;

            try {
                const res = await fetch('/tutor_api', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: txt, subject, topic})
                });
                const data = await res.json();

                // Ответ бота
                const botDiv = document.createElement('div');
                botDiv.className = 'msg ai';
                botDiv.textContent = data.response || 'Ошибка генерации';
                msgs.appendChild(botDiv);
                msgs.scrollTop = msgs.scrollHeight;
            } catch(e) {
                const errDiv = document.createElement('div');
                errDiv.className = 'msg ai';
                errDiv.textContent = '⚠️ Ошибка соединения';
                msgs.appendChild(errDiv);
            }
            inp.disabled = false;
            inp.focus();
        }
    </script>
</body>
</html>
"""