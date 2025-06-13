import telebot
import io
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from config import TELEGRAM_TOKEN
from gpt import generate_text, generate_with_image

# Создаем экземпляр бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Словарь для хранения контекста пользователей (история сообщений)
user_contexts = {}

# Словарь для хранения режима обработки изображений пользователей
user_image_mode = {}  # "auto" - автоматическая обработка, "text" - описание изображения текстом

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message: Message):
    """Обработчик команд /start и /help"""
    bot.reply_to(message, 
        "Привет! Я GPT-4o бот. Отправьте мне текст или изображение с вопросом, и я отвечу вам.\n"
        "Команды:\n"
        "/start, /help - показать это сообщение\n"
        "/clear - очистить историю сообщений\n"
        "/image_mode - настроить режим обработки изображений")

@bot.message_handler(commands=['clear'])
def handle_clear(message: Message):
    """Обработчик команды /clear для очистки контекста пользователя"""
    user_id = message.from_user.id
    if user_id in user_contexts:
        user_contexts[user_id] = []
    bot.reply_to(message, "История сообщений очищена!")

@bot.message_handler(commands=['image_mode'])
def handle_image_mode(message: Message):
    """Обработчик команды /image_mode для выбора режима обработки изображений"""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Автоматическая обработка", callback_data="image_mode:auto"),
        InlineKeyboardButton("Через текстовое описание", callback_data="image_mode:text")
    )
    bot.reply_to(message, 
        "Выберите режим обработки изображений:\n"
        "• Автоматическая обработка - бот попытается самостоятельно анализировать изображение (может не работать)\n"
        "• Через текстовое описание - вы опишите изображение текстом, и бот будет работать с описанием", 
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('image_mode:'))
def callback_image_mode(call):
    """Обработчик выбора режима обработки изображений"""
    user_id = call.from_user.id
    mode = call.data.split(':')[1]
    
    user_image_mode[user_id] = mode
    
    if mode == "auto":
        bot.answer_callback_query(call.id, "Выбран режим автоматической обработки изображений")
        bot.edit_message_text(
            "Установлен режим автоматической обработки изображений.\n"
            "⚠️ В случае ошибок с API попробуйте перейти на режим текстового описания через /image_mode",
            call.message.chat.id, call.message.message_id)
    else:  # text
        bot.answer_callback_query(call.id, "Выбран режим текстового описания изображений")
        bot.edit_message_text(
            "Установлен режим текстового описания изображений.\n"
            "Когда вы отправите фото, бот попросит вас описать его.",
            call.message.chat.id, call.message.message_id)

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

@bot.message_handler(content_types=['photo'])
def handle_photo(message: Message):
    """Обработчик сообщений с фото"""
    user_id = message.from_user.id
    
    # Получаем или создаем контекст пользователя
    if user_id not in user_contexts:
        user_contexts[user_id] = []
        
    # Проверяем выбранный режим обработки изображений
    mode = user_image_mode.get(user_id, "auto")  # По умолчанию авто-режим
    
    if mode == "text":
        # Режим текстового описания - запрашиваем у пользователя описание изображения
        msg = bot.reply_to(message, 
                        "Опишите, пожалуйста, что изображено на фото (это нужно для работы бота):")
        bot.register_next_step_handler(msg, process_image_description, message.photo[-1].file_id)
        return
        
    # Автоматический режим обработки изображения
    
    # Получаем текст сообщения (если есть)
    text = message.caption or "Опиши, что на этом изображении?"
    
    # Получаем фото наилучшего качества
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Отправляем "печатает..." статус
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Получаем ответ от модели с учетом изображения
        response = generate_with_image(text, downloaded_file)
        
        # Добавляем в контекст информацию о сообщении с фото и ответ
        user_contexts[user_id].append(f"User: [Отправлено изображение] {text}")
        user_contexts[user_id].append(f"Assistant: {response}")
        
        # Ограничиваем размер контекста
        if len(user_contexts[user_id]) > 20:
            user_contexts[user_id] = user_contexts[user_id][-20:]
        
        # Отправляем ответ пользователю
        bot.reply_to(message, response)
        
    except Exception as e:
        error_msg = f"Ошибка при обработке изображения: {str(e)}\n\n" \
                   f"Попробуйте использовать текстовый режим обработки изображений через команду /image_mode"
        bot.reply_to(message, error_msg)

def process_image_description(message: Message, photo_id=None):
    """Обработчик описания изображения"""
    user_id = message.from_user.id
    
    if not message.text:
        bot.reply_to(message, "Пожалуйста, отправьте текстовое описание изображения.")
        return
        
    # Получаем или создаем контекст пользователя
    if user_id not in user_contexts:
        user_contexts[user_id] = []
    
    # Описание пользователем изображения
    image_description = message.text
    
    # Формируем вопрос с описанием изображения
    full_prompt = f"[На изображении: {image_description}] Прокомментируй это изображение."
    
    # Отправляем "печатает..." статус
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Добавляем в контекст информацию о сообщении с фото
    user_contexts[user_id].append(f"User: {full_prompt}")
    
    # Получаем ответ от модели (просто текстовый запрос, без изображения)
    response = generate_text(full_prompt)
    
    # Добавляем ответ бота в контекст
    user_contexts[user_id].append(f"Assistant: {response}")
    
    # Ограничиваем размер контекста
    if len(user_contexts[user_id]) > 20:
        user_contexts[user_id] = user_contexts[user_id][-20:]
    
    # Отправляем ответ пользователю
    bot.reply_to(message, response)

if __name__ == "__main__":
    print("Бот запущен!")
    # Запускаем бота
    bot.polling(none_stop=True) 