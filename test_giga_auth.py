import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("GIGACHAT_CLIENT_ID")
client_secret = os.getenv("GIGACHAT_AUTH_KEY")

if not client_id or not client_secret:
    print("❌ Не заданы GIGACHAT_CLIENT_ID или GIGACHAT_AUTH_KEY")
    exit(1)

print("=== ДАННЫЕ ДЛЯ АВТОРИЗАЦИИ ===")
print(f"Client ID: {client_id}")
print(f"Client Secret: {client_secret[:10]}... (показано только начало)")

url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "RqUID": str(uuid.uuid4()),
    "Accept": "application/json",
}
data = {
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "client_credentials",
    "scope": "GIGACHAT_API_PERS"  # если не работает, попробуйте GIGACHAT_API
}

print("\nОтправляю запрос...")
try:
    response = requests.post(url, data=data, headers=headers, verify=False, timeout=10)
    print(f"Статус: {response.status_code}")
    print(f"Ответ сервера: {response.text[:200]}")
    if response.status_code == 200:
        print("✅ Успешно! Токен получен.")
    else:
        print("❌ Ошибка авторизации. Проверьте client_secret.")
except Exception as e:
    print(f"❌ Исключение: {e}")
