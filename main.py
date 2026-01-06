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

# --- ÖZEL SAYFA HARİTASI (BAKARA, AL-İ İMRAN VS.) ---
OZEL_SAYFA_HARITASI = {
    # BAKARA (Sayfa 2'den 49'a kadar)
    2: [
        1, 6, 17, 25, 30, 38, 49, 58, 62, 70, 77, 84, 89, 94, 102, 106, 113, 120, 127, 135,
        142, 146, 154, 164, 170, 177, 182, 187, 191, 197, 203, 211, 216, 220, 225, 231, 234,
        238, 246, 249, 253, 257, 259, 263, 265, 270, 275, 282, 283
    ],
    # AL-İ İMRAN (Sayfa 50'den 76'ya kadar)
    3: [
        1, 10, 16, 23, 30, 38, 46, 53, 62, 71, 78, 84, 92, 101, 109, 116, 122, 133, 141, 149,
        154, 158, 166, 174, 181, 187, 
    ],
    # NİSA (Sayfa 77'den 106'ya kadar)
    4: [
        1, 7, 12, 15, 20, 24, 27, 34, 38, 45, 52, 60, 66, 75, 80, 87, 92, 95, 102, 106, 114,
        122, 128, 135, 141, 148, 155, 163, 171, 186
    ],
    # MAİDE (Sayfa 106'dan 127'ye kadar)
    5: [
        1, 3, 6, 10, 14, 18, 24, 32, 37, 42, 46, 51, 58, 65, 71, 77, 83, 90, 96, 104, 109, 114
    ]

# --- SİSTEM TALİMATI (MÜTEŞABİH ODAKLI) ---
system_instruction = """
GÖREVİN: Ses kaydındaki Kuran ayetlerini tespit et ve listele.

HAYATİ KURALLAR:
1. MÜTEŞABİH (BENZER) AYETLER İÇİN "ARAMA MOTORU" GİBİ ÇALIŞ:
   - Eğer okunan kısım Kuran'da birden fazla surede geçiyorsa (Örn: "Ya eyyühellezine amenu", "Ya eyyühel insan"), ASLA TEK BİR SONUÇ DÖNME.
   - Bu ibarenin geçtiği TÜM sure ve ayet numaralarını bul ve hepsini listeye ekle.
   - Amacımız "En iyi tahmin" değil, "Tüm olasılıkları listelemek".

2. KELİME HASSASİYETİ:
   - "Ya eyyühel İNSAN" ile "Ya eyyühen NAS" ayrımına dikkat et.
   - Sadece duyduğun kelimelerin birebir eşleştiği yerleri getir.

3. SALLAMA YASAK:
   - Ses anlaşılamıyorsa boş liste [] dön.

ÇIKTI FORMATI (JSON LİSTESİ):
[
  { "sure_no": 82, "ayet_no": 6, "sure_adi": "İnfitar", "arapca": "...", "meal": "..." },
  { "sure_no": 84, "ayet_no": 6, "sure_adi": "İnşikak", "arapca": "...", "meal": "..." }
]
"""

# --- CACHE (2.0 Flash) ---
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
    return {"durum": "Hafiz AI - Mutesabih Avcisi Modu"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...), x_user_id: str = Header(None, alias="X-User-ID"), x_premium: str = Header("false", alias="X-Premium")):
    try:
        # Limit Kontrol
        kullanici_id = x_user_id or "anonim"
        is_premium = x_premium.lower() == "true"
        izin_var, limit_bilgisi = limit_kontrol(kullanici_id, is_premium)
        if not izin_var: raise HTTPException(status_code=429, detail=limit_bilgisi)
        
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        # --- PROMPT GÜNCELLEMESİ (ÇOK SERT) ---
        prompt = """
        Bu sesi dinle. 
        Eğer ses, "Ya eyyühellezine amenu" veya "Ya eyyühel insan" gibi Kuran'da çok sık geçen bir kalıp ise:
        TEK BİR SONUÇ DÖNME. Bu ifadenin geçtiği tüm ayetleri ve sureleri ayrı ayrı listele.
        Eğer ses uzun ve belirginse (devamı okunuyorsa) sadece o ayeti dön.
        Ama ses kısa bir kalıpsa hepsini listelemen zorunludur.
        """

        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": content}
        ])
        
        sonuclar = json.loads(response.text)

        # --- SAYFA HESAPLAMA MOTORU (ÖZEL HARİTALI) ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")
            
            if not sure_no or sure_no == 0: continue

            hesaplanan_sayfa = 1

            # 1. YÖNTEM: ÖZEL HARİTA (Bakara, Ali İmran vs.)
            if sure_no in OZEL_SAYFA_HARITASI:
                baslangic_sayfasi = SURE_SAYFA_MAP[sure_no]
                ayet_listesi = OZEL_SAYFA_HARITASI[sure_no]
                
                sayfa_farki = 0
                for index, baslangic_ayeti in enumerate(ayet_listesi):
                    if ayet_no >= baslangic_ayeti:
                        sayfa_farki = index 
                    else:
                        break
                
                hesaplanan_sayfa = baslangic_sayfasi + sayfa_farki

            # 2. YÖNTEM: MATEMATİKSEL TAHMİN
            elif sure_no in SURE_SAYFA_MAP:
                baslangic_sayfasi = SURE_SAYFA_MAP[sure_no]
                ek_sayfa = 0
                
                if sure_no >= 78: 
                    if sure_no >= 90: ek_sayfa = 0
                    else: ek_sayfa = int((ayet_no - 1) / 25.0) 
                else: 
                    ek_sayfa = int((ayet_no - 1) / 13.5)
                
                hesaplanan_sayfa = baslangic_sayfasi + ek_sayfa
            
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