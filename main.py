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

# --- HARİTA (Bunu ekliyoruz ki sayfa hatasız olsun) ---
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
    91: 595, 92: 596, 93: 596, 94: 597, 95: 597, 96: 598, 97: 599, 98: 599, 99: 600, 100: 600,
    101: 601, 102: 601, 103: 602, 104: 602, 105: 602, 106: 603, 107: 603, 108: 603, 109: 604, 110: 604,
    111: 604, 112: 605, 113: 605, 114: 605
}

# --- SİSTEM TALİMATI (GÜÇLENDİRİLDİ) ---
# "sure_no" eklendi ama odak noktası yine ses analizi yapıldı.
system_instruction = """
GÖREVİN: Ses dosyasındaki Kuran okumasını analiz et ve ayeti bul.

ÇOK ÖNEMLİ KURALLAR:
1. SES ANALİZİ ÖNCELİĞİ: Sesteki kelimeleri çok dikkatli ayırt et. 
   - Özellikle "Ya Eyyühel İnsan" ile "Ya Eyyühennas" gibi benzer duyulan yerleri karıştırma.
   - Sadece duyduğun kelimelere odaklan, tahmin yürütme.

2. Eğer net bir Kuran tilaveti DUYAMIYORSAN boş liste döndür: []

3. FORMAT VE DETAYLAR:
   - "sure_no": Surenin Kuran'daki sıra numarası (1-114).
   - "satir_no": Ayfa düzenine (15 satır) göre tahmini satır.
   - Sayfa numarası tahmini yapmana gerek yok (Onu biz halledeceğiz).

4. MÜTEŞABİH KONTROLÜ:
   - Okunan ayet birden fazla surede geçiyorsa hepsini listele.

İSTENEN FORMAT (JSON):
[
  {
    "sure_no": 82,
    "sure_adi": "İnfitar",
    "ayet_no": 6,
    "satir_no": "5",
    "arapca": "...",
    "meal": "..."
  }
]
"""

# MODEL (Dokunmadık, senin 2.5 Lite)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite", 
    system_instruction=system_instruction,
    generation_config={
        "temperature": 0.0, 
        "response_mime_type": "application/json"
    }
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"durum": "Hafiz AI - Hassas Kulak Modu"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        # PROMPT: Sure No istiyoruz ama sesi vurguluyoruz.
        response = model.generate_content([
            "Bu sesi analiz et. Duyduğun kelimeleri 'İnsan', 'Nas' gibi benzerliklere dikkat ederek ayırt et. Sure numarasını (sure_no) mutlaka JSON'a ekle.",
            {"mime_type": mime_type, "data": content}
        ])
        
        sonuclar = json.loads(response.text)

        # --- SAYFA DÜZELTME MOTORU ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")

            # Haritadan kesin sayfayı çekelim
            if sure_no and sure_no in SURE_SAYFA_MAP:
                baslangic_sayfasi = SURE_SAYFA_MAP[sure_no]
                ek_sayfa = 0
                if ayet_no > 15: 
                    ek_sayfa = int(ayet_no / 13) 
                
                hesaplanan_sayfa = min(604, int(baslangic_sayfasi + ek_sayfa))
                item["sayfa_no"] = hesaplanan_sayfa
            
            # Eğer haritada yoksa AI ne dediyse o (veya varsayılan 1)
            elif "sayfa_no" not in item:
                item["sayfa_no"] = 1

            final_sonuclar.append(item)
        
        return final_sonuclar

    except Exception as e:
        return {"hata": str(e)}