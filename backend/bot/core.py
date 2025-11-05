import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config.matrix import (
    TRANSFORMER_TYPES,
    WORKSHOPS,
    PRODUCTS,
    get_workshops_for_transformer,
    get_products_for_workshop,
    is_product_number_required,
    validate_selection
)
from database import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger.getLogger(__name__)

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
        self.application.add_handler(MessageHandler(filters.Text(["❌ Отмена"]), self.cancel_request))
        
        # Обработчики создания заявки
        self.application.add_handler(MessageHandler(filters.Text(list(TRANSFORMER_TYPES.values())), self.handle_transformer_selection))
        self.application.add_handler(MessageHandler(filters.Text(list(WORKSHOPS.values())), self.handle_workshop_selection_request))
        self.application.add_handler(MessageHandler(filters.Text(list(PRODUCTS.values())), self.handle_product_selection))
        
        # Обработчик выбора участка при регистрации
        self.application.add_handler(MessageHandler(filters.Text(list(WORKSHOPS.values())), self.handle_workshop_selection))
        
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
        """Обработчик выбора участка при регистрации"""
        workshop = update.message.text
        user = update.effective_user
        
        try:
            # Сохраняем пользователя в БД
            user_data = {
                'telegram_id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'workshop': workshop
            }
            db.create_user(user_data)
            
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
        transformer_buttons.append(["❌ Отмена"])
        reply_markup = ReplyKeyboardMarkup(transformer_buttons, resize_keyboard=True, one_time_keyboard=True)
        
        await update.message.reply_text(
            "🛠️ Создаем новую заявку!\n\n"
            "Выбери тип трансформатора:",
            reply_markup=reply_markup
        )
    
    async def handle_transformer_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора типа трансформатора"""
        transformer_type_name = update.message.text
        user = update.effective_user
        
        # Находим ключ типа по названию
        transformer_type = next(key for key, value in TRANSFORMER_TYPES.items() if value == transformer_type_name)
        
        # Получаем доступные участки для этого типа
        available_workshops = get_workshops_for_transformer(transformer_type)
        workshop_buttons = [[KeyboardButton(WORKSHOPS[ws])] for ws in available_workshops]
        workshop_buttons.append(["❌ Отмена"])
        
        reply_markup = ReplyKeyboardMarkup(workshop_buttons, resize_keyboard=True, one_time_keyboard=True)
        
        # Сохраняем в сессию
        db.save_session({
            'telegram_id': user.id,
            'transformer_type': transformer_type,
            'current_step': 'selecting_workshop'
        })
        
        await update.message.reply_text(
            f"✅ Выбран тип: {transformer_type_name}\n\n"
            f"Теперь выбери участок:",
            reply_markup=reply_markup
        )
    
    async def handle_workshop_selection_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора участка при создании заявки"""
        workshop_name = update.message.text
        user = update.effective_user
        
        # Получаем сессию пользователя
        session_response = db.get_session(user.id)
        if not session_response.data:
            await update.message.reply_text("❌ Сессия устарела. Начни заново.")
            return
        
        session = session_response.data[0]
        transformer_type = session['transformer_type']
        
        # Находим ключ участка по названию
        workshop = next(key for key, value in WORKSHOPS.items() if value == workshop_name)
        
        # Получаем доступные изделия для этого участка
        available_products = get_products_for_workshop(workshop)
        product_buttons = [[KeyboardButton(PRODUCTS[prod])] for prod in available_products]
        product_buttons.append(["❌ Отмена"])
        
        reply_markup = ReplyKeyboardMarkup(product_buttons, resize_keyboard=True, one_time_keyboard=True)
        
        # Обновляем сессию
        db.save_session({
            'telegram_id': user.id,
            'transformer_type': transformer_type,
            'workshop': workshop,
            'current_step': 'selecting_product'
        })
        
        await update.message.reply_text(
            f"✅ Выбран участок: {workshop_name}\n\n"
            f"Теперь выбери изделие:",
            reply_markup=reply_markup
        )
    
    async def handle_product_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора изделия"""
        product_name = update.message.text
        user = update.effective_user
        
        # Получаем сессию пользователя
        session_response = db.get_session(user.id)
        if not session_response.data:
            await update.message.reply_text("❌ Сессия устарела. Начни заново.")
            return
        
        session = session_response.data[0]
        
        # Находим ключ изделия по названию
        product = next(key for key, value in PRODUCTS.items() if value == product_name)
        
        # Обновляем сессию
        db.save_session({
            'telegram_id': user.id,
            'transformer_type': session['transformer_type'],
            'workshop': session['workshop'],
            'product_type': product,
            'current_step': 'entering_drawing_number'
        })
        
        # Проверяем, требуется ли номер изделия
        requires_number = is_product_number_required(product)
        number_text = "и номер изделия" if requires_number else ""
        
        await update.message.reply_text(
            f"✅ Выбрано изделие: {product_name}\n\n"
            f"Теперь введи номер чертежа {number_text}.\n\n"
            f"Сначала введи номер чертежа:",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
    
    async def cancel_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания заявки"""
        user = update.effective_user
        db.delete_session(user.id)
        
        main_keyboard = ReplyKeyboardMarkup([
            ["📋 Мои заявки", "➕ Новая заявка"],
            ["⚠️ Несоответствия", "📊 Статистика"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            "❌ Создание заявки отменено.",
            reply_markup=main_keyboard
        )
    
    async def show_my_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать заявки пользователя"""
        user = update.effective_user
        
        try:
            # Получаем пользователя
            user_response = db.get_user_by_telegram_id(user.id)
            if not user_response.data:
                await update.message.reply_text("Сначала зарегистрируйся через /start")
                return
            
            current_user = user_response.data[0]
            
            # Получаем заявки пользователя
            requests_response = db.get_user_requests(current_user['id'], limit=5)
            requests = requests_response.data
            
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
            "➕ *Новая заявка* - создать заявку на приемку\n"
            "❌ *Отмена* - отменить создание заявки\n\n"
            "*Процесс создания заявки:*\n"
            "1. Выбери тип трансформатора\n"
            "2. Выбери участок\n" 
            "3. Выбери изделие\n"
            "4. Введи данные\n"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        # Проверяем, не находится ли пользователь в процессе создания заявки
        user = update.effective_user
        session_response = db.get_session(user.id)
        
        if session_response.data:
            session = session_response.data[0]
            current_step = session.get('current_step')
            
            if current_step == 'entering_drawing_number':
                # Пользователь вводит номер чертежа
                drawing_number = update.message.text
                
                # Обновляем сессию
                db.save_session({
                    'telegram_id': user.id,
                    'transformer_type': session['transformer_type'],
                    'workshop': session['workshop'],
                    'product_type': session['product_type'],
                    'drawing_number': drawing_number,
                    'current_step': 'entering_product_number'
                })
                
                requires_number = is_product_number_required(session['product_type'])
                
                if requires_number:
                    await update.message.reply_text(
                        f"✅ Номер чертежа: {drawing_number}\n\n"
                        f"Теперь введи номер изделия:",
                        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
                    )
                else:
                    # Создаем заявку без номера изделия
                    await self.finalize_request(update, user, session, drawing_number, None)
                
            elif current_step == 'entering_product_number':
                # Пользователь вводит номер изделия
                product_number = update.message.text
                drawing_number = session['drawing_number']
                
                # Создаем заявку
                await self.finalize_request(update, user, session, drawing_number, product_number)
                
        else:
            await update.message.reply_text(
                "Я пока понимаю только основные команды 😊\n\n"
                "Используй кнопки ниже для навигации:",
                reply_markup=ReplyKeyboardMarkup([
                    ["📋 Мои заявки", "➕ Новая заявка"],
                    ["⚠️ Несоответствия", "📊 Статистика"]
                ], resize_keyboard=True)
            )
    
    async def finalize_request(self, update: Update, user, session, drawing_number: str, product_number: str):
        """Завершение создания заявки"""
        try:
            # Получаем пользователя
            user_response = db.get_user_by_telegram_id(user.id)
            if not user_response.data:
                await update.message.reply_text("❌ Пользователь не найден")
                return
            
            current_user = user_response.data[0]
            
            # Создаем заявку
            request_data = {
                'transformer_type': session['transformer_type'],
                'workshop': session['workshop'],
                'product_type': session['product_type'],
                'drawing_number': drawing_number,
                'product_number': product_number,
                'master_id': current_user['id'],
                'status': 'planned'
            }
            
            db.create_request(request_data)
            
            # Очищаем сессию
            db.delete_session(user.id)
            
            # Основная клавиатура
            main_keyboard = ReplyKeyboardMarkup([
                ["📋 Мои заявки", "➕ Новая заявка"],
                ["⚠️ Несоответствия", "📊 Статистика"]
            ], resize_keyboard=True)
            
            product_name = PRODUCTS[session['product_type']]
            workshop_name = WORKSHOPS[session['workshop']]
            transformer_name = TRANSFORMER_TYPES[session['transformer_type']]
            
            await update.message.reply_text(
                f"✅ *Заявка создана!*\n\n"
                f"*Тип:* {transformer_name}\n"
                f"*Участок:* {workshop_name}\n"
                f"*Изделие:* {product_name}\n"
                f"*Чертеж:* {drawing_number}\n"
                f"*Номер изделия:* {product_number or 'Б/н'}\n"
                f"*Статус:* 🟡 Планируется\n\n"
                f"Заявка отправлена в ОТК для приемки.",
                parse_mode='Markdown',
                reply_markup=main_keyboard
            )
            
            logger.info(f"Request created for user {user.id}")
            
        except Exception as e:
            logger.error(f"Error creating request: {e}")
            await update.message.reply_text("❌ Ошибка при создании заявки")
    
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
