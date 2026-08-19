import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"

st.set_page_config(page_title="Тест OpenRouter", layout="centered")
st.title("🔌 Тест подключения к OpenRouter")

if not API_KEY:
    st.error("❌ API ключ не найден. Проверь файл .env")
    st.stop()

user_input = st.text_input("Введите вопрос:")

if st.button("Отправить") and user_input:
    try:
        client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
        response = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b:free",
            messages=[
                {"role": "system", "content": "Ты — полезный ассистент. Отвечай на том языке, на котором задан вопрос пользователя. Если вопрос на русском — отвечай на русском. Если вопрос на английском — отвечай на английском."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=200
        )
        st.success("✅ Ответ получен!")
        st.write(response.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")
