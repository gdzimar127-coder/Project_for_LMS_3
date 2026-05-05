import g4f
import re
import json
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


@gen_bp.route('/tutor_chat')
@login_required
def tutor_chat():
    subject = request.args.get('subject', '')
    topic = request.args.get('topic', '')
    username = session.get('username', 'Друг')

    # Определяем тип приветствия: общий вопрос с главной или конкретная тема
    is_general = subject in ['Общий вопрос', '', 'General']

    key = f"{username}_{subject}_{topic}"

    if key not in chat_histories:
        if is_general:
            # === ПЕРСОНАЛИЗИРОВАННОЕ ПРИВЕТСТВИЕ С ГЛАВНОЙ ===
            system_prompt = f"Ты опытный репетитор ОГЭ/ЕГЭ. Обращайся к ученику по имени '{username}'. Твоя задача — помочь разобраться с любым вопросом по подготовке к экзаменам. Будь дружелюбным, задавай уточняющие вопросы, объясняй понятно и с примерами. Отвечай только на русском языке."
            welcome_message = f"Здравствуйте {username}, я ваш репетитор для подготовки к ОГЭ/ЕГЭ, давайте разберем непонятную тему. С чего начнём?"
        else:
            # Стандартное приветствие для конкретной темы
            system_prompt = f"Ты опытный репетитор ОГЭ по предмету '{subject}'. Объясняй тему '{topic}' подробно, приводи примеры, задавай уточняющие вопросы. Отвечай только на русском."
            welcome_message = f"Здравствуйте, {username}! Давайте разберём тему «{topic}» по предмету «{subject}». С чего начнём?"

        chat_histories[key] = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": welcome_message}
        ]

    return render_template_string(TUTOR_HTML,
                                  subject=subject,
                                  topic=topic,
                                  username=username,
                                  is_general=is_general)


@gen_bp.route('/tutor_api', methods=['POST'])
@login_required
def tutor_api():
    data = request.json
    user_msg = data.get('message', '').strip()
    subject = data.get('subject', '')
    topic = data.get('topic', '')
    username = session.get('username', 'Друг')

    is_general = subject in ['Общий вопрос', '', 'General']
    key = f"{username}_{subject}_{topic}"

    if key not in chat_histories:
        if is_general:
            system_prompt = f"Ты опытный репетитор ОГЭ/ЕГЭ. Обращайся к ученику по имени '{username}'. Будь дружелюбным и объясняй понятно."
            chat_histories[key] = [{"role": "system", "content": system_prompt}]
        else:
            system_prompt = f"Ты репетитор ОГЭ по предмету '{subject}'. Объясни тему '{topic}'..."
            chat_histories[key] = [{"role": "system", "content": system_prompt}]

    chat_histories[key].append({"role": "user", "content": user_msg})

    # Ограничиваем историю последними 20 сообщениями
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
        :root { --primary: #667eea; --bg: #f5f7fa; --card: #ffffff; --text: #1e293b; --muted: #64748b; }
        body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); margin: 0; color: var(--text); }
        .chat-box { max-width: 800px; margin: 20px auto; background: var(--card); border-radius: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); height: 85vh; display: flex; flex-direction: column; }
        .header { background: linear-gradient(135deg, var(--primary), #764ba2); color: white; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; border-radius: 16px 16px 0 0; }
        .header-info h3 { margin: 0 0 4px; font-size: 1.1rem; }
        .header-info p { margin: 0; opacity: 0.9; font-size: 0.9rem; }
        .header a { color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 8px; font-size: 0.9rem; transition: 0.2s; }
        .header a:hover { background: rgba(255,255,255,0.3); }
        .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; background: #fafbfc; }
        .msg { max-width: 85%; padding: 12px 16px; border-radius: 16px; line-height: 1.5; white-space: pre-wrap; animation: fadeIn 0.2s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .user { background: #dbeafe; color: #1e40af; align-self: flex-end; border-bottom-right-radius: 4px; }
        .ai { background: var(--card); border: 1px solid #e2e8f0; align-self: flex-start; border-bottom-left-radius: 4px; }
        .input-area { padding: 16px 20px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; background: var(--card); border-radius: 0 0 16px 16px; }
        input { flex: 1; padding: 12px 16px; border: 1px solid #cbd5e1; border-radius: 10px; font-size: 1rem; outline: none; transition: 0.2s; }
        input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(102,126,234,0.1); }
        button { padding: 12px 24px; background: var(--primary); color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: 500; transition: 0.2s; }
        button:hover { background: #5568d8; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        .typing { color: var(--muted); font-style: italic; padding: 8px 16px; }
        .topic-tag { display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="chat-box">
        <div class="header">
            <div class="header-info">
                <h3>👨‍🏫 Репетитор ОГЭ/ЕГЭ</h3>
                <p>Онлайн • Готов помочь с любым вопросом</p>
                {% if not is_general %}
                    <span class="topic-tag">📚 {{ subject }}: {{ topic }}</span>
                {% endif %}
            </div>
            <a href="javascript:history.back()">← Назад</a>
        </div>
        <div class="messages" id="msgs"></div>
        <div class="input-area">
            <input id="inp" placeholder="Задайте вопрос по теме..." onkeydown="if(event.key==='Enter')send()" autocomplete="off">
            <button id="sendBtn" onclick="send()">Отправить</button>
        </div>
    </div>
    <script>
        const msgs = document.getElementById('msgs');
        const inp = document.getElementById('inp');
        const sendBtn = document.getElementById('sendBtn');
        const subject = "{{ subject }}";
        const topic = "{{ topic }}";
        const username = "{{ username }}";
        const isGeneral = {{ 'true' if is_general else 'false' }};

        // Добавляем приветственное сообщение при загрузке
        window.onload = () => {
            {% if is_general %}
                addMsg("Здравствуйте {{ username }}, я ваш репетитор для подготовки к ОГЭ/ЕГЭ, давайте разберем непонятную тему. С чего начнём?", 'ai');
            {% else %}
                addMsg("Здравствуйте, {{ username }}! Давайте разберём тему «{{ topic }}» по предмету «{{ subject }}». С чего начнём?", 'ai');
            {% endif %}
        };

        async function send() {
            const txt = inp.value.trim();
            if(!txt) return;

            addMsg(txt, 'user');
            inp.value = '';
            inp.disabled = true;
            sendBtn.disabled = true;

            // Индикатор "печатает..."
            const typing = document.createElement('div');
            typing.className = 'msg ai typing';
            typing.textContent = '🤖 Думаю...';
            typing.id = 'typing-indicator';
            msgs.appendChild(typing);
            msgs.scrollTop = msgs.scrollHeight;

            try {
                const res = await fetch('/tutor_api', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: txt, subject, topic})
                });
                const data = await res.json();

                // Удаляем индикатор
                document.getElementById('typing-indicator')?.remove();

                if(data.error) {
                    addMsg('❌ ' + data.error, 'ai');
                } else {
                    addMsg(data.response, 'ai');
                }
            } catch(e) {
                document.getElementById('typing-indicator')?.remove();
                addMsg('⚠️ Ошибка соединения. Проверьте интернет.', 'ai');
            }
            inp.disabled = false;
            sendBtn.disabled = false;
            inp.focus();
        }

        function addMsg(txt, cls) {
            const d = document.createElement('div');
            d.className = 'msg ' + cls;
            d.textContent = txt;
            msgs.appendChild(d);
            msgs.scrollTop = msgs.scrollHeight;
        }
    </script>
</body>
</html>
"""