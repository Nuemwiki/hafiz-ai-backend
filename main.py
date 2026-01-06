from fastapi import FastAPI, UploadFile, File, Header, HTTPException
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from collections import defaultdict

# --- VERİ SETİ ---
from kuran_data import SURE_BASLANGIC_SAYFASI, SURE_SAYFA_DURAKLARI

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- SİSTEM TALİMATI (KATİ MÜTEŞABİH KURALI) ---
system_instruction = """
GÖREVİN: Ses kaydındaki Kuran ayetlerini tespit et ve JSON listesi olarak döndür.

ÇOK ÖNEMLİ - MÜTEŞABİH(BENZER) AYET YÖNETİMİ:
1. MODELİN, "KULLANICI MUHTEMELEN BUNU KASTETTİ" DEMESİ YASAKTIR.
2. Eğer okunan ifade kısa bir kalıpsa (Örn: "Ve ma min dabbetin", "Ya eyyühellezine amenu", "Küllü nefsin zaikatül mevt"), bu kelimelerin geçtiği TÜM ayetleri listelemek ZORUNDASIN.
3. Sadece en meşhur olanı değil, kenarda köşede kalmış benzerleri de getir.

ÖRNEK SENARYO:
- Ses: "Ve ma min dabbetin"
- Yanlış Davranış: Sadece Hud 6. ayeti verip bitirmek.
- DOĞRU DAVRANIŞ: 
  [
    {"sure_adi": "Hud", "ayet_no": 6, "arapca": "Ve ma min dabbetin..."},
    {"sure_adi": "Hud", "ayet_no": 56, "arapca": "...ma min dabbetin illa..."},
    {"sure_adi": "Nahl", "ayet_no": 61, "arapca": "...ma tereke aleyha min dabbetin..."},
    {"sure_adi": "Fatır", "ayet_no": 45, "arapca": "...min dabbetin..."}
  ]
  (İçinde "min dabbetin" geçenleri tarayıp listele).

DİĞER KURALLAR:
- Ses anlaşılmıyorsa boş liste [] dön.

ÇIKTI FORMATI (SADECE JSON):
[
  { "sure_no": 11, "ayet_no": 6, "sure_adi": "Hud", "arapca": "...", "meal": "..." }
]
"""

# --- CACHE ---
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
    return {"durum": "Hafiz AI - Kati Mutesabih Modu"}

# --- JSON TEMİZLEYİCİ ---
def clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...), x_user_id: str = Header(None, alias="X-User-ID"), x_premium: str = Header("false", alias="X-Premium")):
    try:
        # Limit
        kullanici_id = x_user_id or "anonim"
        is_premium = x_premium.lower() == "true"
        izin_var, limit_bilgisi = limit_kontrol(kullanici_id, is_premium)
        if not izin_var: raise HTTPException(status_code=429, detail=limit_bilgisi)
        
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        # PROMPT (Modeli zorluyoruz)
        response = model.generate_content([
            "Bu sesi dinle. Eğer okunan kısım Kuran'da birden fazla yerde geçiyorsa (Müteşabih ise), ASLA tek sonuç verme. Hepsini listele. Cevap sadece saf JSON olsun.",
            {"mime_type": mime_type, "data": content}
        ])
        
        cleaned_text = clean_json_response(response.text)
        try:
            sonuclar = json.loads(cleaned_text)
        except json.JSONDecodeError:
            return {"sonuclar": [], "hata": "JSON format hatası", "limit_bilgisi": limit_bilgisi}

        # --- SAYFA HESAPLAMA MOTORU ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")
            
            if not sure_no or sure_no == 0: continue

            hesaplanan_sayfa = 1

            if sure_no in SURE_SAYFA_DURAKLARI and sure_no in SURE_BASLANGIC_SAYFASI:
                baslangic_sayfasi = SURE_BASLANGIC_SAYFASI[sure_no]
                ayet_listesi = SURE_SAYFA_DURAKLARI[sure_no]
                
                sayfa_farki = 0
                for index, baslangic_ayeti in enumerate(ayet_listesi):
                    if ayet_no >= baslangic_ayeti:
                        sayfa_farki = index
                    else:
                        break 
                
                hesaplanan_sayfa = baslangic_sayfasi + sayfa_farki
            
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