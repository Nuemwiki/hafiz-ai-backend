from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- EKLEME 1: TÜRKİYE (AYFA) MUSHAFI HARİTASI ---
# Bu harita, hangi surenin hangi sayfada başladığını kesin olarak bilir.
SURE_SAYFA_MAP = {
    1: 1, 2: 2, 3: 50, 4: 77, 5: 106, 6: 128, 7: 151, 8: 177, 9: 187, 10: 208,
    11: 221, 12: 235, 13: 249, 14: 255, 15: 262, 16: 267, 17: 282, 18: 293, 19: 305, 20: 312,
    21: 322, 22: 332, 23: 342, 24: 350, 25: 359, 26: 367, 27: 377, 28: 385, 29: 396, 30: 404,
    31: 411, 32: 415, 33: 418, 34: 428, 35: 434, 36: 440, 37: 446, 38: 453, 39: 458, 40: 467,
    41: 477, 42: 483, 43: 489, 44: 496, 45: 499, 46: 502, 47: 507, 48: 511, 49: 515, 50: 518,
    51: 520, 52: 523, 53: 526, 54: 528, 55: 531, 56: 534, 57: 537, 58: 542, 59: 545, 60: 549,
    61: 551, 62: 553, 63: 554, 64: 556, 65: 558, 66: 560, 67: 562, 68: 564, 69: 566, 70: 568,
    71: 570, 72: 572, 73: 574, 74: 575, 75: 577, 76: 578, 77: 580, 78: 582, 79: 583, 80: 585,
    81: 586, 82: 587, 83: 587, 84: 589, 85: 590, 86: 591, 87: 591, 88: 592, 89: 593, 90: 594,
    91: 595, 92: 595, 93: 596, 94: 596, 95: 597, 96: 597, 97: 598, 98: 598, 99: 599, 100: 599,
    101: 600, 102: 600, 103: 601, 104: 601, 105: 601, 106: 602, 107: 602, 108: 602, 109: 603, 110: 603,
    111: 603, 112: 604, 113: 604, 114: 604
}

# --- SİSTEM TALİMATI (ORİJİNAL KOD KORUNDU) ---
# Sadece JSON formatına "sure_no" ekledim ki haritadan bakabilelim.
system_instruction = """
GÖREVİN: Ses dosyasındaki Kuran okumasını analiz et ve ayeti bul.

ÇOK ÖNEMLİ KURALLAR:
1. Ses kaydını dinle. Eğer net bir Kuran tilaveti DUYAMIYORSAN (sadece gürültü, sessizlik veya konuşma varsa):
   KESİNLİKLE boş bir JSON dizisi döndür: []
   ASLA tahmin yürütme.

2. SAYFA STANDARDI (TÜRKİYE - AYFA):
   - Sayfa numaralarını verirken KESİNLİKLE "Türkiye Hafızlık Düzeni (Ayfa/Berkenar - 604 Sayfa)" baskısını esas al.
   - Medine Mushafı'nı DEĞİL, Türkiye'deki sarı sayfa düzenini kullan.

3. SATIR TAHMİNİ (YENİ GÖREV):
   - Bulduğun ayetin, standart 15 satırlı Ayfa sayfasında MUHTEMELEN hangi satırda olduğunu tahmin et