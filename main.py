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

# --- SAYFA HARİTASI (SENİN İSTEDİĞİN SABİT YAPI) ---
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

# --- SİSTEM TALİMATI (HAFİZ DİSİPLİNİ MODU) ---
system_instruction = """
GÖREVİN: Ses dosyasındaki Kuran tilavetini analiz et.

KATİ KURALLAR:
1. "SALLAMA" YASAK: Ses kaydındaki Arapça kelimeleri %100 net duymuyorsan, gürültü varsa veya emin değilsen KESİNLİKLE boş liste [] döndür. Asla "şuna benziyor" diye tahmin yürütme. Yanlış cevap vermektense cevap vermemek daha iyidir.

2. KELİME AYRIMI:
   - "Ya eyyühel İNSAN" ile "Ya eyyühen NAS" gibi fonetik olarak benzeyen yerlere ÇOK DİKKAT ET.
   - Sadece duyduğun kelimenin birebir geçtiği ayeti bul.

3. MÜTEŞABİH (BENZER) AYETLER:
   - Okunan ayet Kuran'da birden fazla yerde geçiyorsa (Müteşabih ise), SADECE İLKİNİ DEĞİL, GEÇTİĞİ TÜM YERLERİ listele.
   - Örneğin "Veylül lil müsallin" okunduysa, hem Maun suresindeki yerini hem de varsa benzerlerini kontrol et.
   - Listede her bir eşleşme ayrı bir obje olarak yer almalı.

4. ÇIKTI FORMATI:
   - "sure_no": Surenin 1-114 arası numarası.
   - "satir_no": Ayfa (Berkenar) mushafına göre 1-15 arası tahmini satır.
   - "sayfa_no": Bunu BOŞ bırakabilirsin veya 0 yazabilirsin (Biz dışarıda hesaplayacağız).

İSTENEN FORMAT (JSON):
[
  {
    "sure_no": 82,
    "ayet_no": 6,
    "sure_adi": "İnfitar",
    "satir_no": "5",
    "arapca": "...",
    "meal": "..."
  },
  {
    "sure_no": 99,
    "ayet_no": 1,
    "sure_adi": "Zilzal", 
    "satir_no": "1",
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
        "temperature": 0.0, # Yaratıcılık sıfır, sadece gerçekler.
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
    return {"durum": "Hafiz AI - Disiplinli Mod (Sallama Yok)"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        # PROMPT: Müteşabih uyarısını buraya da ekledik.
        response = model.generate_content([
            "Bu sesi analiz et. Müteşabih (tekrar eden veya benzer) ayetler varsa HEPSİNİ ayrı ayrı listele. Emin değilsen boş liste dön.",
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
            
            # Eğer haritada yoksa ve AI tahmin etmemişse 1. sayfayı ver
            elif "sayfa_no" not in item:
                item["sayfa_no"] = 1

            final_sonuclar.append(item)
        
        return final_sonuclar

    except Exception as e:
        return {"hata": str(e)}