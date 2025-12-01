"""
Китайско-русский словарь на основе BKRS (StarDict формат)
"""
import os
import struct
import re
from typing import Dict, Optional, List
from pathlib import Path


class ChineseRussianDictionary:
    """
    Словарь BKRS для получения русских переводов китайских иероглифов/слов
    """

    _instance = None
    _dict_data: Dict[str, str] = {}
    _loaded = False

    # Путь к файлам словаря
    DICT_DIR = Path(__file__).parent.parent.parent / 'data' / 'bkrs'

    @classmethod
    def get_instance(cls) -> 'ChineseRussianDictionary':
        """Singleton для словаря"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Сброс словаря для перезагрузки"""
        cls._instance = None
        cls._dict_data = {}
        cls._loaded = False

    def __init__(self):
        if not ChineseRussianDictionary._loaded:
            self._load_dictionary()

    def _load_dictionary(self):
        """Загрузка словаря из StarDict файлов"""
        idx_path = self.DICT_DIR / 'dabkrs.idx'
        dict_path = self.DICT_DIR / 'dabkrs.dict'

        if not idx_path.exists() or not dict_path.exists():
            print(f"⚠️ Словарь BKRS не найден в {self.DICT_DIR}")
            ChineseRussianDictionary._loaded = True
            return

        print(f"📖 Загружаю словарь BKRS...")

        # Читаем словарные статьи
        with open(dict_path, 'rb') as f:
            dict_data = f.read()

        # Читаем индекс и парсим
        with open(idx_path, 'rb') as f:
            idx_data = f.read()

        pos = 0
        count = 0

        while pos < len(idx_data):
            # Ищем null-terminated строку (слово)
            null_pos = idx_data.find(b'\x00', pos)
            if null_pos == -1:
                break

            word = idx_data[pos:null_pos].decode('utf-8', errors='ignore')
            pos = null_pos + 1

            # Читаем offset и size (big-endian uint32)
            if pos + 8 > len(idx_data):
                break

            offset = struct.unpack('>I', idx_data[pos:pos+4])[0]
            size = struct.unpack('>I', idx_data[pos+4:pos+8])[0]
            pos += 8

            # Получаем статью
            if offset + size <= len(dict_data):
                article = dict_data[offset:offset+size].decode('utf-8', errors='ignore')
                # Очищаем HTML и берём только первое значение
                clean_text = self._clean_html(article)
                if word and clean_text:
                    ChineseRussianDictionary._dict_data[word] = clean_text

            count += 1
            if count % 500000 == 0:
                print(f"   Загружено {count:,} записей...")

        ChineseRussianDictionary._loaded = True
        print(f"✅ Словарь загружен: {len(ChineseRussianDictionary._dict_data):,} слов")

    def _clean_html(self, html: str) -> str:
        """
        Очистка HTML и извлечение всех основных значений

        Формат BKRS: иероглиф<hr>pinyin<hr>значения
        """
        # Разбиваем по <hr> - берём часть со значениями (третью)
        parts = html.split('<hr>')
        if len(parts) >= 3:
            text = parts[2]  # Значения
        else:
            text = html

        # Убираем все HTML теги
        text = re.sub(r'<[^>]+>', ' ', text)

        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text).strip()

        # Регулярка для pinyin (латиница с тонами)
        pinyin_pattern = r'^[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+[\s,\-]*'

        # Убираем римские цифры в начале (I, II, III и т.д.)
        text = re.sub(r'^[IVX]+[\s,\-]*', '', text)

        # Убираем pinyin в начале
        for _ in range(3):
            old_text = text
            text = re.sub(pinyin_pattern, '', text)
            if text == old_text:
                break

        # Убираем грамматические пометки в начале
        text = re.sub(r'^(?:гл\.|сущ\.|прил\.|наречие|связка|частица|служ\.|служебная частица|союз|предлог|местоим\.)\s*', '', text)

        # Извлекаем все нумерованные значения (1), 2), 3)...)
        meanings = []
        # Ищем паттерн: цифра) текст
        numbered_matches = re.findall(r'(\d+)\)\s*([^0-9]+?)(?=\d+\)|$)', text)

        if numbered_matches:
            for num, meaning in numbered_matches[:6]:  # Максимум 6 значений
                meaning = meaning.strip()
                # Чистим каждое значение
                meaning = self._clean_single_meaning(meaning)
                if meaning and len(meaning) > 1:
                    meanings.append(meaning)

        if meanings:
            return '; '.join(meanings)

        # Если нет нумерованных значений, берём весь текст
        text = self._clean_single_meaning(text)
        return text.strip()

    def _clean_single_meaning(self, text: str) -> str:
        """Очистка одного значения"""
        pinyin_pattern = r'^[a-zA-Zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+[\s,\-]+'

        # Убираем pinyin в начале (только если есть пробел после - это важно!)
        for _ in range(2):
            old_text = text
            text = re.sub(pinyin_pattern, '', text)
            if text == old_text:
                break

        # Убираем грамматические пометки
        text = re.sub(r'^(?:гл\.|сущ\.|прил\.|наречие|связка|частица|служ\.|служебная частица|союз|предлог|местоим\.)\s*', '', text)

        # Убираем буквы подпунктов ТОЛЬКО если есть скобка после (А), Б), а))
        text = re.sub(r'^[А-Яа-я]\)\s*', '', text)

        # Берём до примера
        for sep in ['•', '//']:
            if sep in text:
                text = text.split(sep)[0].strip()

        # Убираем скобки с пояснениями
        text = re.sub(r'\s*\([^)]*\)\s*', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Убираем примеры (китайские символы в конце)
        text = re.sub(r'\s*[\u4e00-\u9fff].*$', '', text)

        return text.strip()

    def lookup(self, word: str) -> Optional[str]:
        """
        Поиск перевода слова/иероглифа

        Args:
            word: Китайское слово или иероглиф

        Returns:
            Русский перевод или None
        """
        return ChineseRussianDictionary._dict_data.get(word)

    def lookup_char(self, char: str) -> Optional[str]:
        """
        Поиск перевода одного иероглифа

        Args:
            char: Китайский иероглиф

        Returns:
            Русский перевод или None
        """
        if len(char) != 1:
            return None
        return self.lookup(char)

    def get_translation_with_pinyin(self, char: str, pinyin: str) -> str:
        """
        Получить строку с иероглифом, pinyin и переводом

        Args:
            char: Китайский иероглиф
            pinyin: Pinyin с тонами

        Returns:
            Форматированная строка: "他 (tā) — он, его"
        """
        translation = self.lookup(char)
        if translation:
            return f"{char} ({pinyin}) — {translation}"
        else:
            return f"{char} ({pinyin})"

    @property
    def is_loaded(self) -> bool:
        """Проверка загружен ли словарь"""
        return ChineseRussianDictionary._loaded and len(ChineseRussianDictionary._dict_data) > 0

    @property
    def word_count(self) -> int:
        """Количество слов в словаре"""
        return len(ChineseRussianDictionary._dict_data)


# Удобная функция для быстрого поиска
def translate_char(char: str) -> Optional[str]:
    """Быстрый перевод одного иероглифа"""
    return ChineseRussianDictionary.get_instance().lookup_char(char)


def translate_word(word: str) -> Optional[str]:
    """Быстрый перевод слова"""
    return ChineseRussianDictionary.get_instance().lookup(word)
