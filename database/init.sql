-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT,
    workshop TEXT NOT NULL,
    role TEXT DEFAULT 'master',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица заявок
CREATE TABLE IF NOT EXISTS requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    -- Основные данные
    transformer_type TEXT NOT NULL,
    workshop TEXT NOT NULL,
    product_type TEXT NOT NULL,
    drawing_number TEXT NOT NULL,
    product_number TEXT,
    status TEXT DEFAULT 'planned',
    
    -- Связи
    master_id UUID REFERENCES users(id),
    
    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Таблица для хранения состояний создания заявок
CREATE TABLE IF NOT EXISTS request_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    transformer_type TEXT,
    workshop TEXT,
    product_type TEXT,
    drawing_number TEXT,
    product_number TEXT,
    current_step TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_requests_master ON requests(master_id);
CREATE INDEX IF NOT EXISTS idx_requests_workshop ON requests(workshop);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_sessions_telegram ON request_sessions(telegram_id);

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггеры для автоматического обновления updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_requests_updated_at BEFORE UPDATE ON requests FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
