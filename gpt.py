import requests
import time
from config import GENAPI_TOKEN, GENAPI_URL_GENERATE, GENAPI_URL_STATUS

def generate_text(prompt, max_retries=15, delay=1):
    """
    Отправляет запрос к GPT-4o и возвращает ответ.
    
    Args:
        prompt: Текстовый запрос пользователя
        max_retries: Максимальное количество попыток получить ответ
        delay: Задержка между запросами в секундах
        
    Returns:
        Ответ от модели или сообщение об ошибке
    """
    # Заголовки запроса
    headers = {
        "Authorization": f"Bearer {GENAPI_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Данные для запроса
    data = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        # Отправляем запрос на генерацию
        response = requests.post(GENAPI_URL_GENERATE, headers=headers, json=data)
        response.raise_for_status()
        
        # Получаем ID запроса
        result = response.json()
        request_id = result.get("request_id")
        
        if not request_id:
            return "Ошибка: Не получен ID запроса"
        
        # Проверяем статус запроса
        for attempt in range(max_retries):
            time.sleep(delay)
            status_url = f"{GENAPI_URL_STATUS}{request_id}"
            status_response = requests.get(status_url, headers=headers)
            status_response.raise_for_status()
            
            status_data = status_response.json()
            status = status_data.get("status")
            
            if status == "success":
                try:
                    # Получение ответа из поля 'result'
                    result = status_data.get("result", [])
                    if result and isinstance(result, list) and len(result) > 0:
                        return result[0]
                        
                    # Альтернативный вариант: извлечь из full_response
                    full_response = status_data.get("full_response", [])
                    if full_response and isinstance(full_response, list) and len(full_response) > 0:
                        message = full_response[0].get("message", {})
                        if message and "content" in message:
                            return message["content"]
                    
                    # Попытка найти ответ в стандартном поле output
                    output = status_data.get("output")
                    if output:
                        return output
                    
                    # Возвращаем весь ответ в виде строки, если не удалось найти контент
                    return str(status_data)
                    
                except Exception as e:
                    return f"Ошибка при обработке ответа: {str(e)}"
                
            elif status == "failed":
                return "Ошибка: Запрос не выполнен"
            # Для статуса "processing" или "starting" продолжаем ожидание
        
        return "Превышено время ожидания ответа"
    
    except Exception as e:
        return f"Произошла ошибка: {str(e)}"