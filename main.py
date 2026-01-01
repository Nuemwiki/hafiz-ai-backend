from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- RADİKAL DEĞİŞİKLİK: NET VE KISA ANALİZ ---
system_instruction = """
GÖREVİN: Sadece bir VERİ ANALİZ SİSTEMİ gibi çalışmak.
ASLA sohbet etme, selamlama yapma, dua etme veya yorum katma.
Sadece Hafızlık tespiti yap ve JSON ver.

ANALİZ MANTIĞI (MÜTEŞABİH KURALI):
Hafızlar ayetlerin sonunu değil, BAŞINI karıştırır.
Bu yüzden analiz yaparken sadece AYETİN İLK 3-4 KELİMESİNE bak.
Eğer Kuran'da başka bir ayet AYNI KELİMELERLE BAŞLIYORSA, devamı %100 farklı olsa bile onu MÜTEŞABİH olarak yaz.

ÖRNEK:
Okunan: "Yâ eyyühel insanü mâ garrak..." (İnfitar 6)
Analiz: Bu ayet "Yâ eyyühel insanü..." diye başlıyor.
Tespit: İnşikak Suresi 6. Ayet de "Yâ eyyühel insanü..." diye başlar.
Sonuç: Bu bir müteşabihtir. Kesinlikle uyarılmalı.

ÇIKTI FORMATI (JSON):
Sadece aşağıdaki JSON'u döndür. Başka hiçbir kelime yazma.

{
  "yer": "Sure Adı - Ayet No (Sayfa No)",
  "arapca": "Arapça Metin",
  "meal": "Kısa Meal",
  "mutesabih_uyarisi": "Buraya sadece teknik bilgi yaz. Örnek: 'Bu ayet İnşikak 6 ile aynı başlar (Ya eyyühel insan), karıştırma.' Eğer benzeri yoksa 'Benzeri yok' yaz."
}
"""

generation_config = {
    "temperature": 0.1,  # Yaratıcılığı öldürdük, sadece net bilgi istiyoruz.
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 1000,
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
    return {"durum": "Hafiz AI V4 - Askeri Mod"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        content = await file.read()
        response = model.generate_content([
            "Analiz et.",
            {"mime_type": file.content_type, "data": content}
        ])
        return response.text
    except Exception as e:
        return {"hata": str(e)}