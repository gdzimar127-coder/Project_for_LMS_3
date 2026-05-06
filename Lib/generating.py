import g4f
import re
import json
from flask import Blueprint, render_template_string, request, jsonify, session
from functools import wraps

# ⚠️ Имя блюпринта должно точно совпадать с префиксом в url_for
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

    key = f"{session['username']}_{subject}_{topic}"
    if key not in chat_histories:
        chat_histories[key] = [{
            "role": "system",
            "content": f"Ты опытный репетитор ОГЭ по предмету '{subject}'. Объясняй тему '{topic}' подробно, приводи примеры, задавай уточняющие вопросы. Отвечай только на русском."
        }]

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
        chat_histories[key] = [{"role": "system", "content": "Ты репетитор ОГЭ. Отвечай только по теме."}]

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
        body { font-family: system-ui, sans-serif; background: #f5f7fa; margin: 0; padding: 20px; }
        .chat-box { max-width: 800px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); height: 85vh; display: flex; flex-direction: column; }
        .header { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px; display: flex; justify-content: space-between; align-items: center; border-radius: 12px 12px 0 0; }
        .header a { color: white; text-decoration: none; background: rgba(255,255,255,0.2); padding: 5px 10px; border-radius: 6px; font-size: 0.9rem; }
        .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 10px; }
        .msg { max-width: 85%; padding: 12px; border-radius: 12px; line-height: 1.5; white-space: pre-wrap; }
        .user { background: #e0f2fe; align-self: flex-end; }
        .ai { background: #f8fafc; border: 1px solid #e2e8f0; align-self: flex-start; }
        .input-area { padding: 15px; border-top: 1px solid #e2e8f0; display: flex; gap: 10px; }
        input { flex: 1; padding: 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
        button { padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="chat-box">
        <div class="header">
            👨‍🏫 Репетитор: {{ subject }} | Тема: {{ topic }}
            <a href="javascript:history.back()">← Назад</a>
        </div>
        <div class="messages" id="msgs"></div>
        <div class="input-area">
            <input id="inp" placeholder="Задайте вопрос..." onkeydown="if(event.key==='Enter')send()">
            <button onclick="send()">Отправить</button>
        </div>
    </div>
    <script>
        const msgs = document.getElementById('msgs');
        const subject = "{{ subject }}";
        const topic = "{{ topic }}";

        window.onload = () => addMsg("Здравствуйте! Давайте разберём тему «{{ topic }}» по предмету «{{ subject }}». С чего начнём?", 'ai');

        async function send() {
            const inp = document.getElementById('inp');
            const txt = inp.value.trim();
            if(!txt) return;
            addMsg(txt, 'user');
            inp.value = '';
            inp.disabled = true;

            try {
                const res = await fetch('/tutor_api', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: txt, subject, topic})
                });
                const data = await res.json();
                addMsg(data.response || '❌ Ошибка ответа', 'ai');
            } catch(e) { addMsg('⚠️ Ошибка соединения', 'ai'); }
            inp.disabled = false;
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