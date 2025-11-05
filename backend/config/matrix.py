"""
МАТРИЧНАЯ СТРУКТУРА ДАННЫХ ДЛЯ СИСТЕМЫ ЗАЯВОК ОТК
"""

# 1. ТИПЫ ТРАНСФОРМАТОРОВ
TRANSFORMER_TYPES = {
    "TMG": "ТМГ",
    "TSL": "ТСЛ", 
    "TSZL": "ТСЗЛ"
}

# 2. УЧАСТКИ ПРОИЗВОДСТВА
WORKSHOPS = {
    "winding": "Намотки",
    "painting": "Покраски",
    "assembly": "Сборки",
    "testing": "ППП", 
    "metal": "Металлоконструкций",
    "cnc": "Станки с ЧПУ",
    "vishnya": "Площадка Вишнёвая",
    "housing": "Сборки кожухов"
}

# 3. ВИДЫ ИЗДЕЛИЙ
PRODUCTS = {
    "lv_winding": "Обмотка НН",
    "hv_winding": "Обмотка ВН",
    "tank": "Бак",
    "cover": "Крышка", 
    "console_kit": "Комплект консолей",
    "equipment": "Оснастка",
    "corrugated_walls": "Гофростенки",
    "detail": "Деталь",
    "assembled_tfm": "Трансформатор собранный",
    "tested_tfm": "Трансформатор испытанный", 
    "housed_tfm": "Трансформатор в кожухе"
}

# 4. МАТРИЦА: КАКИЕ УЧАСТКИ ДОСТУПНЫ ДЛЯ КАЖДОГО ТИПА ТРАНСФОРМАТОРА
TRANSFORMER_WORKSHOPS = {
    "TMG": ["winding", "painting", "assembly", "testing", "metal", "cnc", "vishnya"],
    "TSL": ["winding", "metal", "testing", "assembly"], 
    "TSZL": ["housing"]
}

# 5. МАТРИЦА: КАКИЕ ИЗДЕЛИЯ ПРОИЗВОДЯТСЯ НА КАЖДОМ УЧАСТКЕ
WORKSHOP_PRODUCTS = {
    "winding": ["lv_winding", "hv_winding"],
    "painting": ["tank", "cover", "console_kit", "equipment", "corrugated_walls"],
    "metal": ["tank", "cover", "console_kit", "equipment", "corrugated_walls"],
    "vishnya": ["tank", "cover"],
    "cnc": ["detail"],
    "assembly": ["assembled_tfm"],
    "testing": ["tested_tfm"],
    "housing": ["housed_tfm"]
}

# 6. МАТРИЦА: ДЛЯ КАКИХ ИЗДЕЛИЙ ОБЯЗАТЕЛЕН НОМЕР ИЗДЕЛИЯ
PRODUCT_REQUIRES_NUMBER = {
    "lv_winding": True,
    "hv_winding": True, 
    "tank": True,
    "cover": True,
    "console_kit": True,
    "equipment": False,
    "corrugated_walls": False, 
    "detail": False,
    "assembled_tfm": True,
    "tested_tfm": True,
    "housed_tfm": True
}

def get_workshops_for_transformer(transformer_type: str) -> list:
    """Получить участки доступные для типа трансформатора"""
    return TRANSFORMER_WORKSHOPS.get(transformer_type, [])

def get_products_for_workshop(workshop: str) -> list:
    """Получить изделия доступные для участка"""
    return WORKSHOP_PRODUCTS.get(workshop, [])

def is_product_number_required(product: str) -> bool:
    """Требуется ли номер изделия для данного продукта"""
    return PRODUCT_REQUIRES_NUMBER.get(product, False)

def validate_selection(transformer_type: str, workshop: str, product: str) -> tuple[bool, str]:
    """Валидация выбора пользователя"""
    if workshop not in get_workshops_for_transformer(transformer_type):
        return False, "❌ Этот участок недоступен для выбранного типа трансформатора"
    
    if product not in get_products_for_workshop(workshop):
        return False, "❌ Это изделие недоступно для выбранного участка"
    
    return True, "✅ Выбор корректен"
