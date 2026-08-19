import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

print("=== ДИАГНОСТИКА ===")
print("1. Проверяю переменные окружения...")
print(f"BASE_URL: {os.getenv('FRELLMAPI_BASE')}")
print(f"API_KEY (первые 10 символов): {os.getenv('FRELLMAPI_KEY')[:10]}...")

try:
    print("2. Пытаюсь подключиться к FreeLLMAPI...")
    client = OpenAI(
        base_url=os.getenv("FRELLMAPI_BASE"),
        api_key=os.getenv("FRELLMAPI_KEY")
    )
    
    print("3. Отправляю тестовый запрос...")
    response = client.chat.completions.create(
        model="openrouter/google/gemini-2.5-flash",
        messages=[{"role": "user", "content": "Привет"}],
        max_tokens=20
    )
    
    print("✅ УСПЕХ! Ответ модели:", response.choices[0].message.content)
    
except Exception as e:
    print("❌ ОШИБКА. Текст ошибки:")
    print(e)

