from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- HARİTA (AYNEN KORUNDU) ---
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

# --- SİSTEM TALİMATI ---
system_instruction = """
GÖREVİN: Ses kaydındaki Kuran ayetlerini tespit et.

KURALLAR VE YASAKLAR:
1. "KOPYA ÇEKMEK" YASAK: Sana verilen örnek JSON formatındaki verileri sakın çıktı olarak verme. Sadece duyduğun sesi analiz et.
2. SALLAMAK YASAK: Eğer seste net bir Arapça Kuran tilaveti yoksa, sadece gürültü veya anlaşılmaz sesler varsa, KESİNLİKLE boş liste [] döndür.
3. KELİME ANALİZİ: "Ya Eyyühel İnsan" ve "Ya Eyyühennas" gibi benzer kelimelere dikkat et.

4. MÜTEŞABİH (BENZER) AYETLER - ÇOK ÖNEMLİ:
   - Okunan kısım Kuran'da birden fazla surede geçiyorsa, SADECE BİRİNİ DEĞİL, HEPSİNİ LİSTELE.

ÇIKTI FORMATI (JSON LİSTESİ):
[
  {
    "sure_no": 0, 
    "ayet_no": 0,
    "sure_adi": "Surenin Adı",
    "satir_no": "Tahmini Satır (1-15)",
    "arapca": "Ayetin Metni",
    "meal": "Meali"
  }
]
"""

# --- CACHE ---
try:
    cached_content = genai.caching.CachedContent.create(
        model="gemini-2.0-flash-exp", # 2.0 Flash (Native Audio)
        system_instruction=system_instruction,
        ttl=timedelta(hours=1),
    )
    model = genai.GenerativeModel.from_cached_content(
        cached_content=cached_content,
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
    )
except Exception:
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp", 
        system_instruction=system_instruction,
        generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
    )

# --- LİMİT SİSTEMİ ---
kullanici_limitler = defaultdict(lambda: {"tarih": None, "kullanim": 0, "premium": False})
GUNLUK_LIMIT_UCRETSIZ = 3

def limit_kontrol(kullanici_id: str, is_premium: bool = False):
    bugun = datetime.now().date()
    kayit = kullanici_limitler[kullanici_id]
    if kayit["tarih"] != bugun:
        kayit["tarih"] = bugun
        kayit["kullanim"] = 0
        kayit["premium"] = is_premium
    
    if is_premium or kayit["premium"]: return True, None
    if kayit["kullanim"] >= GUNLUK_LIMIT_UCRETSIZ:
        return False, {"limit_doldu": True, "kalan": 0, "limit": GUNLUK_LIMIT_UCRETSIZ}
    
    kayit["kullanim"] += 1
    return True, {"limit_doldu": False, "kalan": GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"], "limit": GUNLUK_LIMIT_UCRETSIZ}

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
    return {"durum": "Hafiz AI - Sayfa Hesaplama Duzeltildi"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...), x_user_id: str = Header(None, alias="X-User-ID"), x_premium: str = Header("false", alias="X-Premium")):
    try:
        kullanici_id = x_user_id or "anonim"
        is_premium = x_premium.lower() == "true"
        izin_var, limit_bilgisi = limit_kontrol(kullanici_id, is_premium)
        if not izin_var: raise HTTPException(status_code=429, detail=limit_bilgisi)
        
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        response = model.generate_content([
            "Bu sesi dinle. Arapça kelimeleri tespit et. Müteşabihleri bul. Kuran değilse boş dön.",
            {"mime_type": mime_type, "data": content}
        ])
        
        sonuclar = json.loads(response.text)

        # --- YENİ: GELİŞMİŞ SAYFA HESAPLAMA MOTORU ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")
            
            if sure_no == 0 or sure_no is None: continue

            if sure_no in SURE_SAYFA_MAP:
                baslangic_sayfasi = SURE_SAYFA_MAP[sure_no]
                ek_sayfa = 0
                
                # --- AYET YOĞUNLUĞUNA GÖRE HESAP ---
                if sure_no == 2: # BAKARA: Çok uzun ayetler (Ortalama 6-7 ayet/sayfa)
                    ek_sayfa = int((ayet_no - 1) / 7.0)
                
                elif sure_no in [3, 4, 5]: # ALİ İMRAN, NİSA, MAİDE (Ortalama 8-9 ayet/sayfa)
                    ek_sayfa = int((ayet_no - 1) / 9.0)
                
                elif sure_no in [6, 7, 8, 9]: # ENAM, ARAF... (Ortalama 10 ayet/sayfa)
                    ek_sayfa = int((ayet_no - 1) / 10.0)
                
                elif sure_no >= 78: # NEBE'DEN SONRA: Çok kısa ayetler, sayfa değişimi yavaş
                    # Burada ayet no'ya göre değil, sayfa başlarına göre manuel kaydırma daha iyi ama
                    # basit bir oran (30 ayet/sayfa gibi) yaklaşık doğru verir.
                    if sure_no >= 90: ek_sayfa = 0 # Genelde tek sayfa
                    else: ek_sayfa = int((ayet_no - 1) / 25.0) 
                
                else: # GENEL ORTALAMA (13-14 ayet/sayfa)
                    ek_sayfa = int((ayet_no - 1) / 13.5)
                
                hesaplanan_sayfa = min(604, int(baslangic_sayfasi + ek_sayfa))
                item["sayfa_no"] = hesaplanan_sayfa
            else:
                item["sayfa_no"] = 1

            final_sonuclar.append(item)
        
        return {"sonuclar": final_sonuclar, "limit_bilgisi": limit_bilgisi}

    except HTTPException: raise
    except Exception as e: return {"hata": str(e)}

@app.post("/video-izlendi")
async def video_izlendi(x_user_id: str = Header(None, alias="X-User-ID")):
    kullanici_id = x_user_id or "anonim"
    bugun = datetime.now().date()
    kayit = kullanici_limitler[kullanici_id]
    if kayit["tarih"] != bugun:
        kayit["tarih"] = bugun
        kayit["kullanim"] = 0
    if kayit["kullanim"] > 0: kayit["kullanim"] -= 1
    return {"basarili": True, "kalan": GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"]}

@app.get("/limit-durumu")
async def limit_durumu(x_user_id: str = Header(None, alias="X-User-ID")):
    kullanici_id = x_user_id or "anonim"
    bugun = datetime.now().date()
    kayit = kullanici_limitler[kullanici_id]
    if kayit["tarih"] != bugun: kalan = GUNLUK_LIMIT_UCRETSIZ
    else: kalan = max(0, GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"])
    return {"kalan": kalan, "limit": GUNLUK_LIMIT_UCRETSIZ}