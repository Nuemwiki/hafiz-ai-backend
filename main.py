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

# --- SİSTEM TALİMATI (TÜRKİYE + SATIR TAHMİNİ) ---
# Kodun yapısını bozmadım. 
# Sadece "Satır Numarası Tahmini" özelliğini ekledim.
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
   - Bulduğun ayetin, standart 15 satırlı Ayfa sayfasında MUHTEMELEN hangi satırda olduğunu tahmin et (1 ile 15 arası).
   - Kesin bilemezsen yaklaşık bir aralık veya tek sayı ver (Örn: "2", "7-8", "15" gibi).
   - Bunu "satir_no" alanına yaz.

4. MÜTEŞABİH VE TEKRAR KONTROLÜ:
   - Eğer okunan ayet Kuran'da birden fazla yerde geçiyorsa, SADECE BİRİNİ DEĞİL, hepsini tespit et.
   - Bulduğun tüm benzer ayetleri listeye ayrı ayrı ekle.
   - Sayfa numarasını 'sayfa_no' olarak her sonuç için MUTLAKA ekle.

İSTENEN FORMAT (Sadece JSON Listesi):
[
  {
    "sure_adi": "Bakara Suresi",
    "ayet_no": 10,
    "sayfa_no": 3,
    "satir_no": "12",
    "arapca": "...",
    "meal": "..."
  }
]
"""

# SENİN İSTEDİĞİN MODEL (DOKUNMADIM)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", # Aynen bıraktım
    system_instruction=system_instruction,
    generation_config={
        "temperature": 0.0, # Sıfır hata toleransı
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
    return {"durum": "Hafiz AI - 2.5 Flash Türkiye + Satır Modu"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # Dosya türünü olduğu gibi ilet
        mime_type = file.content_type or "audio/m4a"

        # PROMPT GÜNCELLEMESİ: Satır tahmini isteğini buraya da ekledim.
        response = model.generate_content([
            "Bu sesi analiz et. Kuran yoksa boş liste dön. Okunan ayet müteşabih ise hepsini listele. Sayfa ve SATIR NUMARASINI (tahmini) Türkiye (Ayfa) düzenine göre ver.",
            {"mime_type": mime_type, "data": content}
        ])
        
        # JSON temizliği ve dönüş
        return json.loads(response.text)

    except Exception as e:
        return {"hata": str(e)}