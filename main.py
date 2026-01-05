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

# --- SİSTEM TALİMATI ---
system_instruction = """
GÖREVİN: Ses kaydındaki Kuran ayetlerini tespit et.

KURALLAR:
1. SALLAMAK YASAK: Emin değilsen boş liste [] dön.
2. MÜTEŞABİH KONTROLÜ: Okunan ayet birden fazla yerde geçiyorsa hepsini listele.
3. KELİME ANALİZİ: "İnsan/Nas", "Halak/Felak" gibi ayrımlara dikkat et.

ÇIKTI FORMATI (JSON):
[
  { "sure_no": 0, "ayet_no": 0, "sure_adi": "...", "arapca": "...", "meal": "..." }
]
"""

# --- MODEL (2.0 Flash - Native Audio) ---
try:
    cached_content = genai.caching.CachedContent.create(
        model="gemini-2.0-flash-exp",
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

# --- SAYFA HARİTALARI (KESİN ÇÖZÜM) ---
# Buradaki listeler, o surenin sayfalarının BAŞLANGIÇ ayetleridir.
# Örn: Bakara 3. sayfa 6. ayetle başlar. 4. sayfa 17. ayetle başlar.
OZEL_SAYFA_HARITASI = {
    # BAKARA (Sayfa 2'den 49'a kadar)
    2: [
        1, 6, 17, 25, 30, 38, 49, 58, 62, 70, 77, 84, 89, 94, 102, 106, 113, 120, 127, 135,
        142, 146, 154, 164, 170, 177, 182, 187, 191, 197, 203, 211, 216, 220, 225, 231, 234,
        238, 246, 249, 253, 257, 259, 263, 265, 270, 275, 282, 283, 286
    ],
    # AL-İ İMRAN (Sayfa 50'den 76'ya kadar)
    3: [
        1, 10, 16, 23, 30, 38, 46, 53, 62, 71, 78, 84, 92, 101, 109, 116, 122, 133, 141, 149,
        154, 158, 166, 174, 181, 190, 200
    ],
    # NİSA (Sayfa 77'den 106'ya kadar)
    4: [
        1, 7, 12, 15, 20, 24, 27, 34, 38, 45, 52, 60, 66, 75, 80, 87, 92, 95, 102, 106, 114,
        117, 122, 128, 135, 141, 148, 155, 163, 171
    ],
    # MAİDE (Sayfa 106'dan 127'ye kadar)
    5: [
        1, 6, 10, 14, 18, 24, 32, 37, 42, 46, 51, 58, 65, 71, 78, 83, 90, 96, 104, 109, 114
    ]
}

# Diğer sureler için Başlangıç Sayfası
SURE_BASLANGIC_SAYFASI = {
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
    return {"durum": "Hafiz AI - Ozel Harita Modu"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...), x_user_id: str = Header(None, alias="X-User-ID"), x_premium: str = Header("false", alias="X-Premium")):
    try:
        # Limit Kontrolü
        kullanici_id = x_user_id or "anonim"
        is_premium = x_premium.lower() == "true"
        izin_var, limit_bilgisi = limit_kontrol(kullanici_id, is_premium)
        if not izin_var: raise HTTPException(status_code=429, detail=limit_bilgisi)
        
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        response = model.generate_content([
            "Bu sesi dinle. Arapça kelimeleri ve ayetleri tespit et. Müteşabih (benzer) ayetler varsa hepsini listele.",
            {"mime_type": mime_type, "data": content}
        ])
        
        sonuclar = json.loads(response.text)

        # --- SAYFA HESAPLAMA MOTORU (DÜZELTİLDİ) ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")
            
            if not sure_no or sure_no == 0: continue

            hesaplanan_sayfa = 1

            # 1. YÖNTEM: ÖZEL HARİTA (Bakara, Ali İmran vs. için kesin çözüm)
            if sure_no in OZEL_SAYFA_HARITASI:
                baslangic_sayfasi = SURE_BASLANGIC_SAYFASI[sure_no]
                ayet_listesi = OZEL_SAYFA_HARITASI[sure_no]
                
                sayfa_farki = 0
                for index, baslangic_ayeti in enumerate(ayet_listesi):
                    if ayet_no >= baslangic_ayeti:
                        sayfa_farki = index # Hangi aralıkta olduğunu bulur
                    else:
                        break # Aradığımız ayeti geçtik, döngüden çık
                
                hesaplanan_sayfa = baslangic_sayfasi + sayfa_farki

            # 2. YÖNTEM: MATEMATİKSEL TAHMİN (Diğer sureler için)
            elif sure_no in SURE_BASLANGIC_SAYFASI:
                baslangic_sayfasi = SURE_BASLANGIC_SAYFASI[sure_no]
                ek_sayfa = 0
                
                if sure_no >= 78: # Kısa sureler (Nebe sonrası)
                    if sure_no >= 90: ek_sayfa = 0
                    else: ek_sayfa = int((ayet_no - 1) / 25.0) 
                else: # Standart sureler (13-14 ayet/sayfa)
                    ek_sayfa = int((ayet_no - 1) / 13.5)
                
                hesaplanan_sayfa = baslangic_sayfasi + ek_sayfa
            
            # Sınırlandırma (Max 604)
            hesaplanan_sayfa = min(604, hesaplanan_sayfa)
            
            item["sayfa_no"] = hesaplanan_sayfa
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