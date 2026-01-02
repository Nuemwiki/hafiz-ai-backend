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

# --- SİSTEM TALİMATI (MÜTEŞABİH İÇİN GÜÇLENDİRİLDİ) ---
# Kodun yapısı aynı, sadece talimatı netleştirdik.
system_instruction = """
GÖREVİN:Ses dosyasındaki Kuran okumasını analiz et ve ayeti bul.

ÇOK ÖNEMLİ KURALLAR:
1. Ses kaydını dinle. Eğer net bir Kuran tilaveti DUYAMIYORSAN (sadece gürültü, sessizlik veya konuşma varsa):
   KESİNLİKLE boş bir JSON dizisi döndür: []
   ASLA tahmin yürütme.

2. MÜTEŞABİH VE TEKRAR KONTROLÜ:
   - Eğer okunan ayet Kuran'da birden fazla yerde geçiyorsa (Örn: "Vellezine...", "Febi eyyi alai..." gibi), SADECE BİRİNİ DEĞİL, hepsini tespit et.
   - Bulduğun tüm benzer ayetleri listeye ayrı ayrı ekle.
   - Diyanet/Medine (604 sayfa) standardına göre sayfa numarasını 'sayfa_no' olarak her sonuç için MUTLAKA ekle.

İSTENEN FORMAT (Sadece JSON Listesi):
[
  {
    "sure_adi": "Bakara Suresi",
    "ayet_no": 10,
    "sayfa_no": 3,
    "arapca": "...",
    "meal": "..."
  },
  {
    "sure_adi": "Münafıkun Suresi",
    "ayet_no": 2,
    "sayfa_no": 554,
    "arapca": "...",
    "meal": "..."
  }
]
"""

# SENİN İSTEDİĞİN MODEL (AYNEN KORUNDU)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=system_instruction,
    generation_config={
        "temperature": 0.0, # Sıfır hata toleransı (Aynen korundu)
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
    return {"durum": "Hafiz AI - 2.5 Flash Mutesabih Modu"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # Dosya türünü olduğu gibi ilet
        mime_type = file.content_type or "audio/m4a"

        # PROMPT GÜNCELLEMESİ: Buraya da "hepsini listele" uyarısını ekledik.
        response = model.generate_content([
            "Bu sesi analiz et. Kuran yoksa boş liste dön. Okunan ayet müteşabih ise (birden fazla yerde geçiyorsa) hepsini listele.",
            {"mime_type": mime_type, "data": content}
        ])
        
        # JSON temizliği ve dönüş
        return json.loads(response.text)

    except Exception as e:
        return {"hata": str(e)}