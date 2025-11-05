import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from supabase import create_client

from config.matrix import (
    TRANSFORMER_TYPES,
    WORKSHOPS,
    PRODUCTS,
    get_workshops_for_transformer,
    get_products_for_workshop,
    is_product_number_required,
    validate_selection
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_WORKSHOP, CREATING_REQUEST = range(2)

# Инициализация Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

class FactoryBot:
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.Text(["📋 Мои заявки"]), self.show_my_requests))
        self.application.add_handler(MessageHandler(filters.Text(["➕ Новая заявка"]), self.start_new_request))
        
        # Обработчик выбора участка при регистрации
        workshop_keys = list(WORKSHOPS.values())
        self.application.add_handler(MessageHandler(filters.Text(workshop_keys), self.handle_workshop_selection))
        
        # Обработчик неизвестных сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_unknown))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        logger.info(f"User {user.id} started the bot")
        
        # Создаем клавиатуру с участками
        workshop_buttons = [[KeyboardButton(workshop)] for workshop in WORKSHOPS.values()]
        reply_markup = ReplyKeyboardMarkup(workshop_buttons, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_html(
            rf"Привет, {user.mention_html()}! 👋"
            f"\n\nЯ бот для управления заявками ОТК на заводе трансформаторов."
            f"\n\nВыбери свой участок:",
            reply_markup=reply_markup
        )
    
    async def handle_workshop_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора участка"""
        workshop = update.message.text
        user = update.effective_user
        
        try:
            # Сохраняем пользователя в БД
            if supabase:
                user_data = {
                    'telegram_id': user.id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'workshop': workshop
                }
                supabase.table('users').upsert(user_data).execute()
            
            logger.info(f"User {user.id} registered for workshop {workshop}")
            
            # Основная клавиатура
            main_keyboard = ReplyKeyboardMarkup([
                ["📋 Мои заявки", "➕ Новая заявка"],
                ["⚠️ Несоответствия", "📊 Статистика"]
            ], resize_keyboard=True)
            
            await update.message.reply_text(
                f"✅ Отлично! Ты привязан к участку: {workshop}\n\n"
                f"Теперь можешь создавать заявки на приемку и отслеживать их статус.",
                reply_markup=main_keyboard
            )
            
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении. Попробуй еще раз.",
                reply_markup=ReplyKeyboardMarkup([[w] for w in WORKSHOPS.values()], resize_keyboard=True)
            )
    
    async def start_new_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания новой заявки"""
        # Создаем клавиатуру с типами трансформаторов
        transformer_buttons = [[KeyboardButton(t_type)] for t_type in TRANSFORMER_TYPES.values()]
        reply_markup = ReplyKeyboardMarkup(transformer_buttons, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "🛠️ Создаем новую заявку!\n\n"
            "Выбери тип трансформатора:",
            reply_markup=reply_markup
        )
    
    async def show_my_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать заявки пользователя"""
        user = update.effective_user
        
        try:
            if supabase:
                # Получаем пользователя
                user_response = supabase.table('users').select('*').eq('telegram_id', user.id).execute()
                if not user_response.data:
                    await update.message.reply_text("Сначала зарегистрируйся через /start")
                    return
                
                current_user = user_response.data[0]
                
                # Получаем заявки пользователя
                requests_response = supabase.table('requests')\
                    .select('*')\
                    .eq('master_id', current_user['id'])\
                    .order('created_at', desc=True)\
                    .limit(5)\
                    .execute()
                
                requests = requests_response.data
            else:
                requests = []
            
            if not requests:
                await update.message.reply_text(
                    "📭 У тебя пока нет заявок.\n\n"
                    "Нажми '➕ Новая заявка' чтобы создать первую!",
                    reply_markup=ReplyKeyboardMarkup([
                        ["📋 Мои заявки", "➕ Новая заявка"]
                    ], resize_keyboard=True)
                )
                return
            
            message = "📋 Твои последние заявки:\n\n"
            
            for req in requests:
                status_icon = "🟡" if req['status'] == 'planned' else "🟢" if req['status'] == 'success' else "🔴"
                product_number = req['product_number'] or 'Б/н'
                message += f"{status_icon} {req['product_type']} №{product_number}\n"
                message += f"   Чертеж: {req['drawing_number']}\n"
                message += f"   Статус: {req['status']}\n"
                message += f"   Создана: {req['created_at'][:10]}\n\n"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error getting requests: {e}")
            await update.message.reply_text("❌ Ошибка при загрузке заявок")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🤖 *Помощь по боту:*\n\n"
            "*/start* - начать работу с ботом\n"
            "*/help* - показать эту справку\n"
            "📋 *Мои заявки* - посмотреть свои заявки\n"
            "➕ *Новая заявка* - создать заявку на приемку\n\n"
            "Для создания заявки выбери:\n"
            "1. Тип трансформатора\n"
            "2. Участок\n" 
            "3. Изделие\n"
            "4. Введи данные\n"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        await update.message.reply_text(
            "Я пока понимаю только основные команды 😊\n\n"
            "Используй кнопки ниже для навигации:",
            reply_markup=ReplyKeyboardMarkup([
                ["📋 Мои заявки", "➕ Новая заявка"],
                ["⚠️ Несоответствия", "📊 Статистика"]
            ], resize_keyboard=True)
        )
    
    def run(self):
        """Запуск бота"""
        logger.info("Bot is starting...")
        self.application.run_polling()

def main():
    """Точка входа для запуска бота"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    bot = FactoryBot(bot_token)
    bot.run()

if __name__ == '__main__':
    main()
