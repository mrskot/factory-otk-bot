import os
from supabase import create_client

class Database:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_KEY')
        )
    
    def create_user(self, user_data: dict):
        """Создание/обновление пользователя"""
        return self.supabase.table('users').upsert(user_data).execute()
    
    def get_user_by_telegram_id(self, telegram_id: int):
        """Получить пользователя по Telegram ID"""
        return self.supabase.table('users').select('*').eq('telegram_id', telegram_id).execute()
    
    def create_request(self, request_data: dict):
        """Создание новой заявки"""
        return self.supabase.table('requests').insert(request_data).execute()
    
    def get_user_requests(self, user_id: str, limit: int = 10):
        """Получить заявки пользователя"""
        return self.supabase.table('requests')\
            .select('*')\
            .eq('master_id', user_id)\
            .order('created_at', desc=True)\
            .limit(limit)\
            .execute()
    
    def save_session(self, session_data: dict):
        """Сохранить сессию создания заявки"""
        return self.supabase.table('request_sessions').upsert(session_data).execute()
    
    def get_session(self, telegram_id: int):
        """Получить сессию пользователя"""
        return self.supabase.table('request_sessions')\
            .select('*')\
            .eq('telegram_id', telegram_id)\
            .execute()
    
    def delete_session(self, telegram_id: int):
        """Удалить сессию пользователя"""
        return self.supabase.table('request_sessions')\
            .delete()\
            .eq('telegram_id', telegram_id)\
            .execute()

# Глобальный экземпляр базы данных
db = Database()
