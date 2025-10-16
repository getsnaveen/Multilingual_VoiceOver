
LANGUAGES = {
    "English": "en",
    "Spanish": "es",
    "Bhasa": "id",
    "Hindi": "hi",
    "Malay": "ms",
    "Tamil": "ta",
    "Malayalam": "ml",
    "Kannada": "kn",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Bhojpuri": "bho"
}

from typing import Dict
LANGUAGE_CONFIG: Dict[str, Dict[str, str]] = {
        "hi": {
            "font_name": "Noto Sans Devanagari",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSansDevanagari-Regular.ttf"
        },
        "kn": {
            "font_name": "Noto Sans Kannada",
            "font_size": 28,
            "font_color": "&H00FFFFFF",
            "font_file": "NotoSansKannada-Regular.ttf"
        },
        "ta": {
            "font_name": "Noto Sans Tamil",
            "font_size": 30,
            "font_color": "&H00FFFF00",
            "font_file": "NotoSansTamil-Regular.ttf"
        },
        "ml": {
            "font_name": "Noto Sans Malayalam",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSansMalayalam-Regular.ttf"
        },
        "gu": {
            "font_name": "Noto Sans Gujarati",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSansGujarati-Regular.ttf"
        },
        "mr": {
            "font_name": "Noto Sans Devanagari",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSansDevanagari-Regular.ttf"
        },
        "es": {
            "font_name": "Noto Sans",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSans-Regular.ttf"
        },
        "ms": {
            "font_name": "Noto Sans",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSans-Regular.ttf"
        },
        "id": {
            "font_name": "Noto Sans",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSans-Regular.ttf"
        },
        "bho": {
            "font_name": "Noto Sans Devanagari",
            "font_size": 32,
            "font_color": "&H0000FF00",
            "font_file": "NotoSansDevanagari-Regular.ttf"
        }
    }

# from enum import Enum

# class Language(Enum):
#     ENGLISH = "en"
#     SPANISH = "es"
#     BHASA = "id"
#     HINDI = "hi"
#     MALAY = "ms"
#     TAMIL = "ta"
#     MALAYALAM = "ml"
#     KANNADA = "kn"
#     MARATHI = "mr"
#     GUJARATI = "gu"
#     BHOJPURI = "bho"
    
# Example usage
# lang_code = Language.MALAYALAM.value  # 'ml'
# print(Language["ENGLISH"].value)      # 'en'

