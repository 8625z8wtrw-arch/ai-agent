import asyncio
import os
import streamlit as st
import urllib3
from openai import AsyncOpenAI
from dotenv import load_dotenv
import sqlite3
import json
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

load_dotenv()

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1"

GROQ_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1"

st.set_page_config(
    page_title="🧠 AI-агент",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- БАЗА ДАННЫХ ----------
def init_db():
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            category TEXT,
            name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (id)
        )
    ''')
    conn.commit()
    conn.close()

def create_session(category):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    name = f"{category} - {datetime.now().strftime('%d.%m %H:%M')}"
    c.execute('INSERT INTO sessions (timestamp, category, name) VALUES (?, ?, ?)',
              (timestamp, category, name))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_sessions():
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute('SELECT id, timestamp, category, name FROM sessions ORDER BY timestamp DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_messages(session_id):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute('SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp', (session_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def add_message(session_id, role, content):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
              (session_id, role, content, timestamp))
    conn.commit()
    conn.close()

def delete_session(session_id):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
    c.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()

def rename_session(session_id, new_name):
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    c.execute('UPDATE sessions SET name = ? WHERE id = ?', (new_name, session_id))
    conn.commit()
    conn.close()

init_db()

# ============================================
# ПРИВЕТСТВЕННЫЙ ЭКРАН
# ============================================
if "first_start" not in st.session_state:
    st.session_state.first_start = True

if st.session_state.first_start:
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #b2f5ea, #d8b4fe) !important;
            background-attachment: fixed;
        }
        .welcome-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 80vh;
            text-align: center;
            padding: 20px;
        }
        .welcome-title {
            font-size: 3.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #6e44ff, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }
        .welcome-sub {
            font-size: 1.6rem;
            color: #4a1a8a;
            margin-bottom: 20px;
        }
        .welcome-desc {
            font-size: 1.2rem;
            color: #2d1b69;
            max-width: 600px;
            margin: 20px auto;
        }
        .css-1d391kg { display: none; }
        .st-emotion-cache-1r6slb0 { display: none; }
        .stButton > button {
            background: linear-gradient(135deg, #6e44ff, #a855f7) !important;
            color: white !important;
            border: none !important;
            padding: 12px 36px !important;
            font-size: 1.2rem !important;
            border-radius: 30px !important;
            font-weight: bold !important;
            box-shadow: 0 8px 30px rgba(110,68,255,0.4) !important;
            transition: transform 0.2s, box-shadow 0.2s !important;
            display: inline-block !important;
            margin: 0 auto !important;
        }
        .stButton > button:hover {
            transform: scale(1.05) !important;
            box-shadow: 0 12px 40px rgba(110,68,255,0.6) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="welcome-container">
        <div class="welcome-title">Здравствуйте, Николай!</div>
        <div class="welcome-sub">Приступаем к работе с вопросами 🚀</div>
        <div class="welcome-desc">
            Я — твой персональный AI-помощник. Помогу с учёбой, кодом, жизненными советами, спортом и здоровьем.
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Приступить →", key="start_btn", use_container_width=True):
            st.session_state.first_start = False
            st.session_state.current_session = create_session("⚡ Свободный")
            st.session_state.category = "⚡ Свободный"
            st.rerun()
    st.stop()

# ============================================
# ОСНОВНОЙ ИНТЕРФЕЙС (ЧАТ)
# ============================================
if "current_session" not in st.session_state:
    st.session_state.current_session = create_session("⚡ Свободный")
    st.session_state.category = "⚡ Свободный"

# ---------- КАТЕГОРИИ ----------
CATEGORIES = {
    "📚 Учёба": "Ты — репетитор. Объясняй просто, с примерами. Отвечай на языке вопроса.",
    "🧘 Жизнь": "Ты — мудрый советчик. Дай практичный совет. Отвечай на языке вопроса.",
    "💻 Код": "Ты — эксперт по программированию. Дай код и объясни. Отвечай на языке вопроса.",
    "🏋️ Спорт": "Ты — тренер. Дай советы по тренировкам. Отвечай на языке вопроса.",
    "🏥 Здоровье": "Ты — врач-диетолог. Дай советы по питанию. Отвечай на языке вопроса.",
    "⚡ Свободный": "Отвечай максимально полезно. Отвечай на языке вопроса."
}

# ---------- МОДЕЛИ ----------
ALL_MODELS = {
    "OR: Nemotron 3 Super 120B": {"provider": "openrouter", "model": "nvidia/nemotron-3-super-120b-a12b:free"},
    "OR: Nemotron 3 Nano 30B": {"provider": "openrouter", "model": "nvidia/nemotron-3-nano-30b-a3b:free"},
    "OR: Nemotron Nano 9B v2": {"provider": "openrouter", "model": "nvidia/nemotron-nano-9b-v2:free"},
    "OR: Nemotron 3.5 Lightning": {"provider": "openrouter", "model": "nvidia/nemotron-3.5-lightning:free"},
    "OR: Nemotron 3 Ultra 550B": {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
    "OR: GPT-OSS 20B": {"provider": "openrouter", "model": "openai/gpt-oss-20b:free"},
    "OR: North Mini Code": {"provider": "openrouter", "model": "cohere/north-mini-code:free"},
    "OR: Laguna XS 2.1": {"provider": "openrouter", "model": "poolside/laguna-xs-2.1:free"},
    "OR: Laguna S 2.1": {"provider": "openrouter", "model": "poolside/laguna-s-2.1:free"},
    "Groq: Llama 3.1 8B (быстрая)": {"provider": "groq", "model": "llama-3.1-8b-instant"},
    "Groq: Llama 3.3 70B": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    "Groq: Llama 4 Scout 17B": {"provider": "groq", "model": "llama-4-scout-17b-16e-instruct"},
    "Groq: Llama 4 Maverick 17B": {"provider": "groq", "model": "llama-4-maverick-17b-128e-instruct"},
    "Groq: Qwen3 32B": {"provider": "groq", "model": "qwen/qwen3-32b"},
    "Groq: GPT-OSS 120B": {"provider": "groq", "model": "openai/gpt-oss-120b"},
    "Groq: GPT-OSS 20B": {"provider": "groq", "model": "openai/gpt-oss-20b"},
    "Groq: GPT-OSS Safeguard 20B": {"provider": "groq", "model": "openai/gpt-oss-safeguard-20b"},
    "Groq: Compound": {"provider": "groq", "model": "groq/compound"},
    "Groq: Compound Mini": {"provider": "groq", "model": "groq/compound-mini"},
    "Groq: Mixtral 8x7B": {"provider": "groq", "model": "mixtral-8x7b-32768"},
    "Groq: Gemma 2 9B": {"provider": "groq", "model": "gemma2-9b-it"},
}

RECOMMENDED = {
    "📚 Учёба": [
        "OR: Nemotron 3 Super 120B",
        "Groq: Llama 3.3 70B",
        "Groq: Qwen3 32B",
        "OR: GPT-OSS 20B",
        "Groq: Mixtral 8x7B"
    ],
    "🧘 Жизнь": [
        "OR: Nemotron 3 Super 120B",
        "Groq: Llama 3.3 70B",
        "OR: Laguna XS 2.1",
        "Groq: Gemma 2 9B",
        "OR: GPT-OSS 20B"
    ],
    "💻 Код": [
        "Groq: Llama 3.3 70B",
        "OR: North Mini Code",
        "Groq: Mixtral 8x7B",
        "OR: Nemotron 3 Super 120B",
        "Groq: Llama 3.1 8B (быстрая)"
    ],
    "🏋️ Спорт": [
        "OR: Nemotron 3 Super 120B",
        "Groq: Llama 3.3 70B",
        "OR: GPT-OSS 20B",
        "Groq: Gemma 2 9B",
        "OR: Laguna S 2.1"
    ],
    "🏥 Здоровье": [
        "OR: Nemotron 3 Super 120B",
        "Groq: Llama 3.3 70B",
        "OR: GPT-OSS 20B",
        "Groq: Gemma 2 9B",
        "OR: Nemotron 3 Nano 30B"
    ],
    "⚡ Свободный": list(ALL_MODELS.keys())
}

SYNTHESIS_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

# ---------- ФУНКЦИИ ОПРОСА ----------
async def ask_openrouter(client, model, prompt, system_prompt):
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
            timeout=15
        )
        content = response.choices[0].message.content
        return content if content else "⚠️ Пустой ответ"
    except Exception as e:
        return f"⚠️ Ошибка: {e}"

async def ask_groq(client, model, prompt, system_prompt):
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
            timeout=15
        )
        content = response.choices[0].message.content
        return content if content else "⚠️ Пустой ответ"
    except Exception as e:
        return f"⚠️ Ошибка: {e}"

async def ask_model(model_info, prompt, system_prompt):
    provider = model_info["provider"]
    model = model_info["model"]
    
    if provider == "openrouter":
        if not OPENROUTER_KEY:
            return f"⚠️ Нет ключа OpenRouter"
        client = AsyncOpenAI(base_url=OPENROUTER_URL, api_key=OPENROUTER_KEY)
        return await ask_openrouter(client, model, prompt, system_prompt)
    elif provider == "groq":
        if not GROQ_KEY:
            return f"⚠️ Нет ключа Groq"
        client = AsyncOpenAI(base_url=GROQ_URL, api_key=GROQ_KEY)
        return await ask_groq(client, model, prompt, system_prompt)
    else:
        return "⚠️ Неизвестный провайдер"

async def ensemble_query(prompt, category, selected_models):
    system_prompt = CATEGORIES.get(category, CATEGORIES["⚡ Свободный"])
    tasks = []
    model_names = []
    
    for name in selected_models:
        model_info = ALL_MODELS.get(name)
        if model_info:
            tasks.append(ask_model(model_info, prompt, system_prompt))
            model_names.append(name)
    
    results = await asyncio.gather(*tasks)
    combined = list(zip(model_names, results))
    valid_results = [(name, ans) for name, ans in combined if isinstance(ans, str) and not ans.startswith("⚠️")]
    
    if not valid_results:
        return combined, "❌ Все модели вернули ошибку. Попробуйте позже."
    
    summary = f"Вопрос: {prompt}\nКатегория: {category}\n\n"
    for model, ans in valid_results:
        summary += f"--- {model} ---\n{ans}\n\n"
    
    synthesis_prompt = f"""
Ты — аналитик. Проанализируй ответы моделей и дай единый итоговый ответ.
Отвечай на том языке, на котором задан вопрос.
{summary}
Итоговый вывод:
"""
    
    try:
        if OPENROUTER_KEY:
            client = AsyncOpenAI(base_url=OPENROUTER_URL, api_key=OPENROUTER_KEY)
            final = await client.chat.completions.create(
                model=SYNTHESIS_MODEL,
                messages=[{"role": "user", "content": synthesis_prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            return combined, final.choices[0].message.content
        else:
            return combined, "⚠️ Нет ключа OpenRouter для синтеза"
    except Exception as e:
        return combined, f"❌ Ошибка синтеза: {e}"

# ============================================
# КАСТОМНЫЙ CSS + КАЛЛИГРАФИЧЕСКАЯ ПОДПИСЬ
# ============================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Great+Vibes&display=swap');

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.stApp {
    background: linear-gradient(135deg, #b2f5ea, #d8b4fe, #fbc2c2, #f5e6a3);
    background-size: 400% 400%;
    animation: gradient 18s ease infinite;
    color: #1a1a2e;
}

/* ЧАТ НА ВСЮ ВЫСОТУ */
.chat-container {
    height: calc(100vh - 220px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    padding: 10px 0;
    scroll-behavior: smooth;
}

/* ПОЛЕ ВВОДА */
.stTextArea {
    position: sticky;
    bottom: 0;
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(10px);
    padding: 8px 0;
    z-index: 10;
    border-radius: 12px;
    margin-top: 10px;
}
.stTextArea>div>textarea {
    background: #ffffff !important;
    color: #1a1a2e !important;
    border: 2px solid #6e44ff !important;
    border-radius: 12px !important;
    padding: 10px 16px !important;
    font-size: 1rem !important;
    box-shadow: 0 0 0 2px rgba(110,68,255,0.1) !important;
    transition: all 0.3s ease !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.stTextArea>div>textarea:focus {
    border-color: #a855f7 !important;
    box-shadow: 0 0 0 4px rgba(168,85,247,0.3) !important;
}

/* БОКОВАЯ ПАНЕЛЬ */
.css-1d391kg {
    background: rgba(255, 255, 255, 0.25) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255,255,255,0.3);
}
.css-1d391kg .stSelectbox label,
.css-1d391kg .stMultiselect label,
.css-1d391kg .stMarkdown,
.css-1d391kg .stText,
.css-1d391kg .stCaption {
    color: #1a1a2e !important;
}
.css-1d391kg .stSelectbox > div,
.css-1d391kg .stMultiselect > div {
    background: rgba(255,255,255,0.5) !important;
    color: #1a1a2e !important;
}

/* КАЛЛИГРАФИЧЕСКАЯ ПОДПИСЬ "НИКОЛАЙ" */
.signature {
    position: fixed;
    bottom: 30px;
    right: 30px;
    z-index: 1000;
    font-family: 'Great Vibes', cursive;
    font-size: 2.2rem;
    font-weight: 400;
    color: #6e44ff;
    background: linear-gradient(135deg, #6e44ff, #a855f7, #f5a3b3, #f5e6a3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: 0 0 20px rgba(110, 68, 255, 0.2);
    cursor: default;
    user-select: none;
    transition: transform 0.3s ease, text-shadow 0.3s ease;
    letter-spacing: 1px;
}
.signature:hover {
    transform: scale(1.05);
    text-shadow: 0 0 40px rgba(110, 68, 255, 0.5);
}

/* СООБЩЕНИЯ */
.message-user {
    background: rgba(110, 68, 255, 0.15);
    border-radius: 16px 16px 4px 16px;
    padding: 12px 18px;
    margin: 8px 0;
    border-left: 3px solid #6e44ff;
    align-self: flex-end;
    max-width: 80%;
}
.message-assistant {
    background: rgba(255, 255, 255, 0.3);
    border-radius: 16px 16px 16px 4px;
    padding: 12px 18px;
    margin: 8px 0;
    border-left: 3px solid #a855f7;
    align-self: flex-start;
    max-width: 80%;
}

/* КНОПКИ В БОКОВОЙ ПАНЕЛИ */
.stButton > button {
    background: linear-gradient(135deg, #6e44ff, #a855f7) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: bold !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 20px rgba(110, 68, 255, 0.3) !important;
}
.stButton > button:hover {
    transform: scale(1.02) !important;
    box-shadow: 0 6px 30px rgba(110, 68, 255, 0.6) !important;
}

/* СЕССИИ */
.session-item {
    background: rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 8px 12px;
    margin: 4px 0;
    transition: all 0.3s ease;
    border: 1px solid rgba(255,255,255,0.1);
    color: #1a1a2e;
    font-size: 0.9rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.session-item:hover {
    background: rgba(255,255,255,0.3);
    border-color: rgba(110,68,255,0.3);
}
.session-active {
    background: rgba(110,68,255,0.2);
    border-color: #6e44ff;
    border-left: 3px solid #6e44ff;
}

/* ИНДИКАТОР ПЕЧАТАЕТ */
.typing-indicator {
    display: inline-block;
    padding: 8px 16px;
    background: rgba(200,200,200,0.2);
    border-radius: 20px;
    font-size: 0.9rem;
    color: #555;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0% { opacity: 0.5; }
    50% { opacity: 1; }
    100% { opacity: 0.5; }
}

/* СКРОЛЛБАР */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: rgba(0,0,0,0.05); border-radius: 10px; }
::-webkit-scrollbar-thumb { background: linear-gradient(135deg, #6e44ff, #a855f7); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ---------- КАЛЛИГРАФИЧЕСКАЯ ПОДПИСЬ ----------
st.markdown("""
<div class="signature" title="Николай">
    ✦ Николай ✦
</div>
""", unsafe_allow_html=True)

# ---------- БОКОВАЯ ПАНЕЛЬ ----------
with st.sidebar:
    st.markdown("### 📂 Чаты")
    
    sessions = get_sessions()
    if not sessions:
        new_id = create_session("⚡ Свободный")
        st.session_state.current_session = new_id
        sessions = get_sessions()
    
    for sess in sessions:
        sess_id, ts, cat, name = sess
        is_active = (sess_id == st.session_state.current_session)
        
        col1, col2 = st.columns([5, 1])
        with col1:
            if st.button(f"{'✅ ' if is_active else ''}{name}", key=f"switch_{sess_id}", use_container_width=True):
                st.session_state.current_session = sess_id
                st.rerun()
        with col2:
            if st.button("❌", key=f"del_{sess_id}"):
                delete_session(sess_id)
                remaining = get_sessions()
                if remaining:
                    st.session_state.current_session = remaining[0][0]
                else:
                    new_id = create_session("⚡ Свободный")
                    st.session_state.current_session = new_id
                st.rerun()
    
    st.divider()
    
    # Создание нового чата
    col1, col2 = st.columns([3, 1])
    with col1:
        category = st.selectbox("Категория:", list(CATEGORIES.keys()), key="new_chat_cat")
    with col2:
        if st.button("➕", help="Создать новый чат"):
            new_id = create_session(category)
            st.session_state.current_session = new_id
            st.rerun()
    
    st.divider()
    
    # ---------- НАСТРОЙКИ МОДЕЛЕЙ (динамический ключ) ----------
    st.markdown("### ⚙️ Модели")
    
    default_models = RECOMMENDED.get(category, list(ALL_MODELS.keys()))
    
    selected = st.multiselect(
        "Выбери модели (минимум 2):",
        options=list(ALL_MODELS.keys()),
        default=default_models,
        key=f"model_selector_{category}"  # <-- КЛЮЧ ЗАВИСИТ ОТ КАТЕГОРИИ
    )
    
    st.caption("Модели с ошибками будут автоматически пропущены.")
    st.caption(f"🔹 OpenRouter: 9 моделей")
    st.caption(f"🔹 Groq: 12 моделей (14 400 запросов/день)")

# ---------- ОСНОВНАЯ ОБЛАСТЬ (ЧАТ) ----------
messages = get_messages(st.session_state.current_session)

session_info = None
for sess in get_sessions():
    if sess[0] == st.session_state.current_session:
        session_info = sess
        break

if session_info:
    col1, col2, col3 = st.columns([4, 1, 1])
    with col1:
        st.title(f"💬 {session_info[3]}")
    with col2:
        if st.button("✏️ Переименовать", key="rename_chat_btn"):
            st.session_state['show_rename'] = True
    with col3:
        if st.button("📥 Экспорт", key="export_chat_btn"):
            msgs = get_messages(st.session_state.current_session)
            text = f"Чат: {session_info[3]}\n\n"
            for role, content, ts in msgs:
                text += f"{'Вы' if role == 'user' else 'Агент'} ({ts[:16]}):\n{content}\n\n"
            st.download_button(
                "Скачать .txt",
                text,
                file_name=f"chat_{session_info[0]}.txt",
                mime="text/plain",
                key="download_btn"
            )

# Диалог переименования
if 'show_rename' in st.session_state and st.session_state['show_rename']:
    current_name = session_info[3] if session_info else ""
    new_name = st.text_input("Новое имя чата:", value=current_name, key="rename_input_chat")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Сохранить", key="rename_save_chat"):
            if new_name.strip():
                rename_session(st.session_state.current_session, new_name.strip())
            st.session_state['show_rename'] = False
            st.rerun()
    with col2:
        if st.button("❌ Отмена", key="rename_cancel_chat"):
            st.session_state['show_rename'] = False
            st.rerun()

# Контейнер для сообщений
chat_container = st.container()
with chat_container:
    for role, content, ts in messages:
        if role == "user":
            st.markdown(f'<div class="message-user"><strong>Вы</strong><br>{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="message-assistant"><strong>Агент</strong><br>{content}</div>', unsafe_allow_html=True)
    
    if 'typing' in st.session_state and st.session_state['typing']:
        st.markdown('<div class="typing-indicator">✍️ Агент печатает...</div>', unsafe_allow_html=True)

# Поле ввода
with st.container():
    user_input = st.text_area("", height=60, key="user_input", placeholder="Задайте вопрос...", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        send_btn = st.button("🚀 Отправить", type="primary", use_container_width=True)

if send_btn and user_input.strip():
    add_message(st.session_state.current_session, "user", user_input.strip())
    st.session_state['typing'] = True
    
    with st.spinner("Опрашиваю модели..."):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results, final = loop.run_until_complete(
                ensemble_query(user_input.strip(), category, selected)
            )
            loop.close()
            add_message(st.session_state.current_session, "assistant", final)
        except Exception as e:
            st.error(f"Ошибка: {e}")
        finally:
            st.session_state['typing'] = False
    
    st.rerun()
