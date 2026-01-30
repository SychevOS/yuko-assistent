#transcription.py
"""
Модуль транскрипции русских слов в латиницу для улучшенного поиска приложений
"""

import re
from typing import Dict, Tuple, List

class RussianTranscriber:
    """Класс для транскрипции русских слов в латиницу"""
    
    # Основные правила транскрипции
    TRANSCRIPTION_RULES = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
        'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
        'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
        'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
        'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya',
        
        # Заглавные буквы
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D',
        'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I',
        'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N',
        'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T',
        'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch',
        'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
        'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    }
    
    # Альтернативные варианты транскрипции (для неоднозначных случаев)
    ALTERNATIVE_TRANSCRIPTIONS = {
        'х': ['kh', 'h'],
        'ц': ['ts', 'c'],
        'ч': ['ch', 'tch'],
        'ш': ['sh', 'sch'],
        'щ': ['shch', 'sch', 'shh'],
        'е': ['e', 'ye'],
        'ё': ['yo', 'e'],
        'ю': ['yu', 'iu', 'ju'],
        'я': ['ya', 'ia', 'ja'],
        'ж': ['zh', 'j'],
        'э': ['e', 'eh'],
    }
    
    # Распространённые комбинации для улучшения точности
    COMBINATIONS = {
        'ие': 'ie', 'ия': 'ia', 'ий': 'iy',
        'ье': 'ie', 'ья': 'ia', 'ьи': 'i',
        'ие': 'ie', 'ые': 'ye', 'ай': 'ay',
        'ой': 'oy', 'ей': 'ey', 'ий': 'iy',
    }
    
    @classmethod
    def to_latin(cls, text: str) -> List[str]:
        """
        Преобразование русского текста в латиницу
        Возвращает список вариантов транскрипции
        """
        text = text.strip().lower()
        
        # Сначала обрабатываем комбинации букв
        for rus_combo, lat_combo in cls.COMBINATIONS.items():
            text = text.replace(rus_combo, f'{{{lat_combo}}}')
        
        # Разделяем на части для альтернативных вариантов
        parts = re.split(r'(\{.*?\})', text)
        
        variants = ['']
        for part in parts:
            if part.startswith('{') and part.endswith('}'):
                # Это комбинация
                combo = part[1:-1]
                new_variants = []
                for var in variants:
                    new_variants.append(var + combo)
                variants = new_variants
            else:
                # Обычные символы
                new_variants = []
                for char in part:
                    if char in cls.TRANSCRIPTION_RULES:
                        base = cls.TRANSCRIPTION_RULES[char]
                        alternatives = cls.ALTERNATIVE_TRANSCRIPTIONS.get(char, [base])
                        
                        if new_variants:
                            temp_variants = []
                            for var in new_variants:
                                for alt in alternatives:
                                    temp_variants.append(var + alt)
                            new_variants = temp_variants
                        else:
                            new_variants = alternatives.copy()
                    else:
                        # Оставляем латинские символы как есть
                        if new_variants:
                            new_variants = [var + char for var in new_variants]
                        else:
                            new_variants = [char]
                
                if variants:
                    variants = [v1 + v2 for v1 in variants for v2 in new_variants]
                else:
                    variants = new_variants
        
        # Убираем дубликаты
        unique_variants = []
        seen = set()
        for var in variants:
            if var not in seen:
                seen.add(var)
                unique_variants.append(var)
        
        return unique_variants[:5]  # Ограничиваем количество вариантов
    
    @classmethod
    def normalize_app_name(cls, name: str) -> List[str]:
        """
        Нормализация имени приложения для поиска
        Возвращает список нормализованных вариантов
        """
        name = name.lower().strip()
        
        # Убираем расширения и лишние слова
        name = re.sub(r'\.(exe|lnk|msi|app)$', '', name)
        name = re.sub(r'\s+(pro|plus|lite|free|premium|ultimate)$', '', name)
        name = re.sub(r'\s+(русская?|английская?|version|edition|редакция)', '', name)
        
        # Транскрипция
        latin_variants = cls.to_latin(name)
        
        # Добавляем оригинальное имя
        all_variants = [name] + latin_variants
        
        # Добавляем варианты без пробелов
        additional_variants = []
        for var in all_variants:
            if ' ' in var:
                additional_variants.append(var.replace(' ', ''))
                additional_variants.append(var.replace(' ', '-'))
        
        all_variants.extend(additional_variants)
        
        # Убираем дубликаты
        unique_variants = []
        seen = set()
        for var in all_variants:
            if var and var not in seen:
                seen.add(var)
                unique_variants.append(var)
        
        return unique_variants


class AppNameMatcher:
    """Класс для сравнения имён приложений с использованием транскрипции"""
    
    @staticmethod
    def get_trigrams(text: str) -> set:
        """Получение набора триграмм из строки"""
        text = text.lower().replace(' ', '').replace('-', '')
        if len(text) < 3:
            return {text + '_' * (3 - len(text))} if text else set()
        
        trigrams = set()
        for i in range(len(text) - 2):
            trigram = text[i:i+3]
            trigrams.add(trigram)
        return trigrams
    
    @staticmethod
    def trigram_similarity(str1: str, str2: str) -> float:
        """Вычисление схожести строк по триграммам"""
        trigrams1 = AppNameMatcher.get_trigrams(str1)
        trigrams2 = AppNameMatcher.get_trigrams(str2)
        
        if not trigrams1 and not trigrams2:
            return 0.0
        
        intersection = trigrams1.intersection(trigrams2)
        union = trigrams1.union(trigrams2)
        
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def three_element_similarity(str1: str, str2: str) -> float:
        """
        Сравнение по трём элементам:
        1. Первые 3 символа
        2. Последние 3 символа  
        3. Набор триграмм
        """
        str1 = str1.lower().replace(' ', '').replace('-', '')
        str2 = str2.lower().replace(' ', '').replace('-', '')
        
        if not str1 or not str2:
            return 0.0
        
        # 1. Сравнение первых трёх символов
        if len(str1) >= 3 and len(str2) >= 3:
            first_score = 1.0 if str1[:3] == str2[:3] else 0.0
        else:
            first_score = 1.0 if str1 == str2 else 0.0
        
        # 2. Сравнение последних трёх символов
        if len(str1) >= 3 and len(str2) >= 3:
            last_score = 1.0 if str1[-3:] == str2[-3:] else 0.0
        else:
            last_score = 1.0 if str1 == str2 else 0.0
        
        # 3. Сравнение по триграммам
        trigram_score = AppNameMatcher.trigram_similarity(str1, str2)
        
        # Взвешенная сумма
        return (first_score * 0.3) + (last_score * 0.3) + (trigram_score * 0.4)
    
    @classmethod
    def find_best_match(cls, query: str, candidates: List[str], 
                        threshold: float = 0.3) -> Tuple[str, float]:
        """
        Поиск наилучшего совпадения среди кандидатов
        """
        if not candidates:
            return "", 0.0
        
        # Получаем варианты транскрипции для запроса
        query_variants = RussianTranscriber.normalize_app_name(query)
        
        best_match = ""
        best_score = 0.0
        
        for candidate in candidates:
            # Нормализуем кандидата
            candidate_normalized = candidate.lower().strip()
            candidate_variants = [candidate_normalized]  # Простой вариант
            
            for query_var in query_variants:
                for cand_var in candidate_variants:
                    score = cls.three_element_similarity(query_var, cand_var)
                    
                    if score > best_score:
                        best_score = score
                        best_match = candidate
        
        if best_score >= threshold:
            return best_match, best_score
        else:
            return "", 0.0

