import telebot
from telebot.types import Message
from config import TELEGRAM_TOKEN
from gpt import generate_text

# Создаем экземпляр бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Словарь для хранения контекста пользователей (история сообщений)
user_contexts = {}

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message: Message):
    """Обработчик команд /start и /help"""
    bot.reply_to(message, 
        "Привет! Я GPT-4o бот. Отправьте мне текст, и я отвечу вам.\n"
        "Команды:\n"
        "/start, /help - показать это сообщение\n"
        "/clear - очистить историю сообщений")

@bot.message_handler(commands=['clear'])
def handle_clear(message: Message):
    """Обработчик команды /clear для очистки контекста пользователя"""
    user_id = message.from_user.id
    if user_id in user_contexts:
        user_contexts[user_id] = []
    bot.reply_to(message, "История сообщений очищена!")

@bot.message_handler(content_types=['text'])
def handle_text(message: Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    
    # Получаем или создаем контекст пользователя
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    
    # Добавляем сообщение пользователя в контекст
    user_contexts[user_id].append(f"User: {message.text}")
    
    # Создаем полный промпт с контекстом
    prompt = "\n".join(user_contexts[user_id])
    
    # Отправляем "печатает..." статус
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Получаем ответ от модели
    response = generate_text(prompt)
    
    # Добавляем ответ бота в контекст
    user_contexts[user_id].append(f"Assistant: {response}")
    
    # Ограничиваем размер контекста (оставляем последние 10 сообщений)
    if len(user_contexts[user_id]) > 20:
        user_contexts[user_id] = user_contexts[user_id][-20:]
    
    # Отправляем ответ пользователю
    bot.reply_to(message, response)

if __name__ == "__main__":
    print("Бот запущен!")
    # Запускаем бота
    bot.polling(none_stop=True)