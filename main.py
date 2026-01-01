from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# .env dosyasını yükle
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı! .env dosyanı kontrol et.")

genai.configure(api_key=api_key)

# --- GEMINI AYARLARI ---
system_instruction = """
GÖREVİN: Profesyonel bir Kuran Analiz Motoru olarak çalışmak.
Ses dosyasındaki okunan ayeti tespit et.
Bu ayetin Kuran-ı Kerim'in TAMAMINDA geçtiği BÜTÜN yerleri (veya birebir lafız benzerlerini) bul.

ÖNEMLİ KURALLAR:
1. Eğer Rahman Suresi'ndeki gibi tekrar eden bir ayetse, 31 kere geçiyorsa 31'ini de listele.
2. Eğer tek bir yerse, tek bir obje içeren liste döndür.
3. Çıktı formatı KESİNLİKLE sadece saf bir JSON Dizisi (Array) olmalı.
4. Sayfa numaralarını Diyanet/Medine (604 sayfa) standardına göre ver.

İSTENEN JSON FORMATI:
[
  {
    "sure_adi": "Rahman Suresi",
    "ayet_no": 13,
    "sayfa_no": 531,
    "arapca": "Arapça Metni Buraya",
    "meal": "Türkçe Meali Buraya"
  }
]
SADECE JSON DÖNDÜR. YORUM YAPMA.
"""

generation_config = {
    "temperature": 0.0, # Sıfır hata toleransı
    "top_p": 0.95,
    "max_output_tokens": 4000,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash", 
    generation_config=generation_config,
    system_instruction=system_instruction,
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
    return {"durum": "Hafiz AI - Veritabanısız Mod (Anlık Analiz)"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        # 1. Dosyayı Gemini'ye gönder
        content = await file.read()
        
        # Dosya tipine göre mime_type belirle (mp3, wav, m4a vs.)
        mime_type = file.content_type or "audio/mp3" 

        response = model.generate_content([
            "Bu kayıttaki ayeti bul ve tüm tekrarlarını listele.",
            {"mime_type": mime_type, "data": content}
        ])
        
        # 2. Gelen JSON verisini parse et ve direkt kullanıcıya dön
        try:
            results = json.loads(response.text)
            return results
        except json.JSONDecodeError:
            return {"hata": "Model JSON üretmedi", "raw": response.text}

    except Exception as e:
        return {"hata": str(e)}
    # Hafiz AI Guncellendi - Veritabanisiz Mod