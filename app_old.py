import asyncio
import os
import base64
import requests
from io import BytesIO
from PIL import Image
import streamlit as st
from dotenv import load_dotenv
from openai import AsyncOpenAI
import replicate  # для генерации фото (бесплатно)

# Загружаем переменные окружения
load_dotenv()

BASE_URL = os.getenv("FRELLMAPI_BASE")
API_KEY = os.getenv("FRELLMAPI_KEY")
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN")  # опционально для генерации фото

# -------- 1. СПИСОК БЕСПЛАТНЫХ МОДЕЛЕЙ (ансамбль) --------
MODELS = [
    "openrouter/google/gemini-2.0-flash",          # быстрая, vision, бесплатно
    "openrouter/meta-llama/llama-3.3-70b-instruct", # мощная бесплатная
    "openrouter/mistralai/mistral-large-latest",    # хорошая бесплатная
    # можно добавить ещё бесплатные, например:
    # "openrouter/google/gemma-4-31b",
    # "openrouter/microsoft/phi-3.5-mini",
]

SYNTHESIS_MODEL = "openrouter/google/gemini-2.0-flash"  # модель-синтезатор

# -------- 2. ФУНКЦИИ ДЛЯ ТЕКСТОВОГО АНСАМБЛЯ --------
async def ask_model(client, model, prompt):
    """Запрос к одной модели"""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return model, response.choices[0].message.content
    except Exception as e:
        return model, f"❌ Ошибка: {e}"

async def ensemble_query(prompt):
    """Опрашиваем все модели, собираем ответы, синтезируем итог"""
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    tasks = [ask_model(client, model, prompt) for model in MODELS]
    results = await asyncio.gather(*tasks)

    summary = f"Вопрос: {prompt}\n\n"
    for model, answer in results:
        summary += f"--- {model} ---\n{answer}\n\n"

    synthesis_prompt = f"""
Ты — эксперт-аналитик. Проанализируй ответы моделей и дай итоговый вывод.
{summary}
Итоговый вывод (чётко, без воды):
"""
    final = await client.chat.completions.create(
        model=SYNTHESIS_MODEL,
        messages=[{"role": "user", "content": synthesis_prompt}],
        temperature=0.3,
        max_tokens=1500
    )
    return results, final.choices[0].message.content

# -------- 3. ФУНКЦИЯ ДЛЯ АНАЛИЗА ИЗОБРАЖЕНИЙ (Vision) --------
async def ask_vision_model(prompt, image_base64):
    """Отправляем изображение и вопрос в модель с Vision (Gemini Flash)"""
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    try:
        response = await client.chat.completions.create(
            model="openrouter/google/gemini-2.0-flash",  # бесплатная vision-модель
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Ошибка при анализе изображения: {e}"

# -------- 4. ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ (через Replicate) --------
def generate_image(prompt):
    """Генерирует изображение по тексту через бесплатную модель на Replicate"""
    if not REPLICATE_TOKEN:
        return "❌ Не задан REPLICATE_API_TOKEN в .env. Зарегистрируйтесь на replicate.com и получите токен."
    try:
        # Используем бесплатную модель (например, flux или stable-diffusion)
        output = replicate.run(
            "black-forest-labs/flux-schnell",  # бесплатная и быстрая модель
            input={"prompt": prompt, "num_outputs": 1}
        )
        # output – это список URL-адресов
        if output:
            return output[0]  # возвращаем ссылку на картинку
        else:
            return None
    except Exception as e:
        return f"❌ Ошибка генерации: {e}"

# -------- 5. ИНТЕРФЕЙС STREAMLIT --------
st.set_page_config(page_title="Мой AI-агент (бесплатно)", layout="centered")

st.title("🧠 Мой AI-агент + 🤖 Ассистент DeepSeek")
st.markdown("**Привет! Это твой личный ассистент на базе нескольких бесплатных ИИ-моделей.**")
st.markdown("Задавай вопросы, загружай фото для анализа или генерируй картинки — всё бесплатно!")
st.divider()

# -------- ВКЛАДКА 1: Текстовый ансамбль --------
st.subheader("📝 Вопрос к ансамблю моделей")
user_prompt = st.text_area("Введите ваш вопрос:", height=100)
if st.button("Спросить всех", type="primary", key="ensemble"):
    if not user_prompt.strip():
        st.warning("Введите вопрос!")
    else:
        with st.spinner("Опрашиваю модели..."):
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results, final_answer = loop.run_until_complete(ensemble_query(user_prompt))
                loop.close()
                st.subheader("📌 Итоговый вывод")
                st.success(final_answer)
                with st.expander("🔍 Посмотреть ответы каждой модели"):
                    for model, ans in results:
                        st.markdown(f"**{model}**")
                        st.text(ans)
                        st.divider()
            except Exception as e:
                st.error(f"Ошибка: {e}")

st.divider()

# -------- ВКЛАДКА 2: Анализ изображений --------
st.subheader("🖼️ Анализ изображения (Vision)")
uploaded_file = st.file_uploader("Загрузите фото", type=["jpg", "jpeg", "png"])
vision_question = st.text_input("Вопрос по фото (например, 'Что здесь изображено?')")
if uploaded_file and vision_question and st.button("Проанализировать фото", key="vision"):
    with st.spinner("Анализирую..."):
        # Конвертируем изображение в base64
        image = Image.open(uploaded_file)
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        # Отправляем запрос
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            answer = loop.run_until_complete(ask_vision_model(vision_question, img_base64))
            loop.close()
            st.success(answer)
        except Exception as e:
            st.error(f"Ошибка: {e}")

st.divider()

# -------- ВКЛАДКА 3: Генерация изображений --------
st.subheader("🎨 Генерация изображения по описанию")
gen_prompt = st.text_input("Опишите, что нарисовать:")
if st.button("Сгенерировать фото", key="generate"):
    if not gen_prompt.strip():
        st.warning("Введите описание!")
    else:
        with st.spinner("Генерирую изображение..."):
            result = generate_image(gen_prompt)
            if isinstance(result, str) and result.startswith("http"):
                st.image(result, caption="Сгенерированное изображение")
                st.markdown(f"[Открыть в новой вкладке]({result})")
            else:
                st.error(result)  # покажет ошибку или сообщение о токене

st.divider()
st.caption("🤖 Бесплатный AI-агент, работающий на OpenRouter + FreeLLMAPI. Ваш ассистент DeepSeek всегда с вами.")
