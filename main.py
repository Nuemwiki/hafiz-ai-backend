from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
# Eğer .env dosyan yoksa API Key'i buraya direkt yazabilirsin test için.
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- SİSTEM TALİMATI ---
# Mevcut yapını koruyoruz, sadece sayfa numarasının kesin gelmesini garantiliyoruz.
system_instruction = """
GÖREVİN: Ses dosyasındaki Kuran okumasını analiz et.

KURALLAR:
1. Ses kaydını dinle. Eğer net bir Kuran tilaveti DUYAMIYORSAN boş liste dön: []
2. Eğer Kuran okunuyorsa:
   - Okunan sureyi ve ayeti tespit et.
   - Bu ayetin bulunduğu sayfayı (Diyanet/Medine 604 sayfa standardına göre) kesinlikle 'sayfa_no' olarak ekle.

İSTENEN FORMAT (JSON):
[
  {
    "sure_adi": "Fatiha Suresi",
    "ayet_no": 1,
    "sayfa_no": 1, 
    "arapca": "Elhamdulillahi...",
    "meal": "Hamd alemlerin rabbine..."
  }
]
"""

# ÖNEMLİ DEĞİŞİKLİK: 
# 'gemini-2.5-flash' sende kota/destek hatası verdiği için 
# bunu en stabil ve geniş kotalı sürüm olan 'gemini-1.5-flash' yaptık.
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
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
    return {"durum": "Hafiz AI Calisiyor"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        
        # Dosya türünü olduğu gibi iletiyoruz
        mime_type = file.content_type or "audio/m4a"

        response = model.generate_content([
            "Bu sesi analiz et. Kuran yoksa boş liste dön.",
            {"mime_type": mime_type, "data": content}
        ])
        
        # Gelen cevabı JSON'a çevirip gönderiyoruz
        # Frontend bu JSON içindeki 'sayfa_no'yu kullanacak.
        return json.loads(response.text)

    except Exception as e:
        return {"hata": str(e)}