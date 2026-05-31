from app.core.runner import run_python_code

print("Тест 1: Обычный код...")
res1 = run_python_code("print('Hello from Docker!')")
print(f"Результат: {res1}\n")

print("Тест 2: Бесконечный цикл (проверка защиты)...")
res2 = run_python_code("while True: pass", timeout=2)
print(f"Результат: {res2}")

hack_system_payload = """
try:
    with open('/etc/passwd', 'r') as f:
        print("ХА-ХА! Я ПРОЧИТАЛ ТВОИ ПАРОЛИ:")
        print(f.read()[:100]) # Читаем первые 100 символов
except Exception as e:
    print(f"Доступ запрещен: {e}")
"""
print("\nТест 4: Чтение /etc/passwd (проверка изоляции)...")
res4 = run_python_code(hack_system_payload)
print(f"Результат: {res4}")


list_files_payload = """
import os
print("Файлы в корневой директории контейнера:")
print(os.listdir('/'))
"""
print("\nТест 5: Сканирование директорий...")
res5 = run_python_code(list_files_payload)
print(f"Результат: {res5}")

