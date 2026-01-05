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

# --- SİSTEM TALİMATI (AYNEN KORUNDU) ---
system_instruction = """
GÖREVİN: Ses kaydındaki Kuran ayetlerini tespit et.

KURALLAR VE YASAKLAR:
1. "KOPYA ÇEKMEK" YASAK: Sana verilen örnek JSON formatındaki verileri (0, Örnek Sure vb.) sakın çıktı olarak verme. Sadece duyduğun sesi analiz et.
2. SALLAMAK YASAK: Eğer seste net bir Arapça Kuran tilaveti yoksa, sadece gürültü veya anlaşılmaz sesler varsa, KESİNLİKLE boş liste [] döndür. Rastgele bir ayet atma.
3. KELİME ANALİZİ: "Ya Eyyühel İnsan" ve "Ya Eyyühennas" gibi benzer kelimelere dikkat et. Duyduğun kelimeler tam olarak hangi ayette geçiyorsa onu bul.

4. MÜTEŞABİH (BENZER) AYETLER - ÇOK ÖNEMLİ:
   - Okunan kısım Kuran'da birden fazla surede geçiyorsa, SADECE BİRİNİ DEĞİL, HEPSİNİ LİSTELE.
   - Örn: "Veylül lil müsallin" hem Maun'da hem başka yerde benzer geçebilir. Hepsini ver.

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

# --- YENİ: CONTEXT CACHING ---
try:
    cached_content = genai.caching.CachedContent.create(
        model="gemini-2.5-flash",
        system_instruction=system_instruction,
        ttl=timedelta(hours=1),  # 1 saat cache'te kalır
    )
    print(f"✅ Cache oluşturuldu: {cached_content.name}")
    
    model = genai.GenerativeModel.from_cached_content(
        cached_content=cached_content,
        generation_config={
            "temperature": 0.0, 
            "response_mime_type": "application/json"
        }
    )
except Exception as e:
    print(f"⚠️ Cache oluşturulamadı, normal model kullanılıyor: {e}")
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", 
        system_instruction=system_instruction,
        generation_config={
            "temperature": 0.0, 
            "response_mime_type": "application/json"
        }
    )

# --- YENİ: LİMİT SİSTEMİ ---
kullanici_limitler = defaultdict(lambda: {"tarih": None, "kullanim": 0, "premium": False})
GUNLUK_LIMIT_UCRETSIZ = 3  # 5'ten 3'e düşürüldü

def temizle_eski_kayitlar():
    """Eski tarihlerin verilerini temizle"""
    bugun = datetime.now().date()
    silinecekler = [k for k, v in kullanici_limitler.items() 
                    if v.get("tarih") != bugun]
    for k in silinecekler:
        del kullanici_limitler[k]

def limit_kontrol(kullanici_id: str, is_premium: bool = False):
    """Kullanıcının limitini kontrol et"""
    temizle_eski_kayitlar()
    bugun = datetime.now().date()
    
    kayit = kullanici_limitler[kullanici_id]
    
    # Tarih değiştiyse sıfırla
    if kayit["tarih"] != bugun:
        kayit["tarih"] = bugun
        kayit["kullanim"] = 0
        kayit["premium"] = is_premium
    
    # Premium kullanıcılar sınırsız
    if is_premium or kayit["premium"]:
        return True, None
    
    # Limit kontrolü
    if kayit["kullanim"] >= GUNLUK_LIMIT_UCRETSIZ:
        kalan = 0
        return False, {
            "limit_doldu": True,
            "kalan": kalan,
            "limit": GUNLUK_LIMIT_UCRETSIZ,
            "mesaj": "Günlük limitiniz doldu. Video izleyerek devam edebilirsiniz."
        }
    
    # Kullanımı artır
    kayit["kullanim"] += 1
    kalan = GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"]
    
    return True, {
        "limit_doldu": False,
        "kalan": kalan,
        "limit": GUNLUK_LIMIT_UCRETSIZ
    }

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
    return {
        "durum": "Hafiz AI - Context Caching + Limit Sistemi",
        "cache_aktif": True,
        "gunluk_limit": GUNLUK_LIMIT_UCRETSIZ
    }

@app.post("/analiz-et")
async def analiz_et(
    file: UploadFile = File(...),
    x_user_id: str = Header(None, alias="X-User-ID"),
    x_premium: str = Header("false", alias="X-Premium")
):
    try:
        # Kullanıcı ID kontrolü
        kullanici_id = x_user_id or "anonim"
        is_premium = x_premium.lower() == "true"
        
        # Limit kontrolü
        izin_var, limit_bilgisi = limit_kontrol(kullanici_id, is_premium)
        
        if not izin_var:
            raise HTTPException(status_code=429, detail=limit_bilgisi)
        
        # Ses dosyasını oku
        content = await file.read()
        mime_type = file.content_type or "audio/m4a"

        # PROMPT (Aynen korundu)
        prompt = """
        Bu sesi dinle. 
        1. Duyduğun Arapça kelimeleri tam olarak tespit et.
        2. Bu kelimelerin geçtiği TÜM sure ve ayetleri bul (Müteşabih kontrolü yap).
        3. Eğer seste Kuran okunmuyorsa boş liste [] dön. ASLA tahmin yürütme.
        """

        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": content}
        ])
        
        sonuclar = json.loads(response.text)

        # --- YENİ: DAHA DOĞRU SAYFA HESAPLAMA ---
        final_sonuclar = []
        for item in sonuclar:
            sure_no = item.get("sure_no")
            ayet_no = item.get("ayet_no")
            
            if sure_no == 0 or sure_no is None:
                continue

            if sure_no and sure_no in SURE_SAYFA_MAP:
                baslangic_sayfasi = SURE_SAYFA_MAP[sure_no]
                
                # Daha akıllı sayfa hesaplama
                # Her sayfada ortalama 15 satır var
                # Kısa sureler için daha hassas hesaplama
                if sure_no >= 78:  # Kısa sureler (Nebe'den sonra)
                    ek_sayfa = 0  # Genelde aynı sayfada kalır
                elif ayet_no <= 7:
                    ek_sayfa = 0  # İlk ayetler başlangıç sayfasında
                elif ayet_no <= 20:
                    ek_sayfa = 1  # 8-20 arası ayetler +1 sayfa
                else:
                    # Uzun sureler için orantılı hesaplama
                    ek_sayfa = int((ayet_no - 1) / 13)
                
                hesaplanan_sayfa = min(604, int(baslangic_sayfasi + ek_sayfa))
                item["sayfa_no"] = hesaplanan_sayfa
            else:
                item["sayfa_no"] = 1

            final_sonuclar.append(item)
        
        # Limit bilgisini sonuçla birlikte gönder
        return {
            "sonuclar": final_sonuclar,
            "limit_bilgisi": limit_bilgisi
        }

    except HTTPException:
        raise
    except Exception as e:
        return {"hata": str(e)}

@app.post("/video-izlendi")
async def video_izlendi(x_user_id: str = Header(None, alias="X-User-ID")):
    """Video izlendiğinde +1 hak ver"""
    kullanici_id = x_user_id or "anonim"
    bugun = datetime.now().date()
    
    kayit = kullanici_limitler[kullanici_id]
    
    if kayit["tarih"] != bugun:
        kayit["tarih"] = bugun
        kayit["kullanim"] = 0
    
    # Limiti azalt (yani hak ver)
    if kayit["kullanim"] > 0:
        kayit["kullanim"] -= 1
    
    kalan = GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"]
    
    return {
        "basarili": True,
        "mesaj": "Video izleme hakkınız eklendi!",
        "kalan": kalan,
        "limit": GUNLUK_LIMIT_UCRETSIZ
    }

@app.get("/limit-durumu")
async def limit_durumu(x_user_id: str = Header(None, alias="X-User-ID")):
    """Kullanıcının mevcut limit durumunu sorgula"""
    kullanici_id = x_user_id or "anonim"
    bugun = datetime.now().date()
    
    kayit = kullanici_limitler[kullanici_id]
    
    if kayit["tarih"] != bugun:
        kalan = GUNLUK_LIMIT_UCRETSIZ
    else:
        kalan = max(0, GUNLUK_LIMIT_UCRETSIZ - kayit["kullanim"])
    
    return {
        "kalan": kalan,
        "limit": GUNLUK_LIMIT_UCRETSIZ,
        "premium": kayit.get("premium", False)
    }

# Uygulama kapanırken cache'i temizle
@app.on_event("shutdown")
def cleanup():
    try:
        if 'cached_content' in globals():
            cached_content.delete()
            print("✅ Cache temizlendi")
    except:
        pass