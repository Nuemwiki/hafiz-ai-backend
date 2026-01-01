from fastapi import FastAPI, UploadFile, File, HTTPException
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# .env yükle
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı!")

genai.configure(api_key=api_key)

# --- SYSTEM INSTRUCTION (GÜNCELLENDİ) ---
# Rahman suresi hatasını engellemek için kuralları sertleştirdik.
system_instruction = """
GÖREVİN: Ses dosyasındaki Kuran okumasını analiz etmek ve hangi ayet olduğunu bulmak.

KURALLAR:
1. Ses net değilse, gürültüden ibaretse veya Kuran okunmuyorsa:
   KESİNLİKLE boş bir JSON dizisi döndür: []
   ASLA "Rahman Suresi" örneğini veya uydurma bir cevap verme.
   
2. Eğer ayet tespit edilirse:
   Bu ayetin Kuran'ı Kerim'deki TÜM tekrarlarını bul.
   Sayfa numaralarını Diyanet/Medine (604 sayfa) standardına göre ver.

İSTENEN FORMAT (Sadece tespit başarılıysa):
[
  {
    "sure_adi": "Fatiha Suresi",
    "ayet_no": 1,
    "sayfa_no": 1,
    "arapca": "Elhamdulillahi...",
    "meal": "Hamd alemlerin rabbine..."
  }
]

SADECE JSON DÖNDÜR. YORUM EKLEME.
"""

generation_config = {
    "temperature": 0.0, # Sıfır yaratıcılık, tam itaat.
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
    return {"durum": "Hafiz AI - Limitsiz Mod Aktif"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        print(f"Dosya alındı: {file.filename}") # Loglara yaz
        
        content = await file.read()
        
        # Dosya boş mu kontrol et
        if len(content) < 1000: # 1KB'dan küçükse ses değildir
            return []

        mime_type = "audio/mp3" # Genelleme yapıyoruz, Gemini anlar.

        response = model.generate_content([
            "Bu kayıttaki ayeti bul. Duyamıyorsan boş liste dön.",
            {"mime_type": mime_type, "data": content}
        ])
        
        print("Gemini Cevabı:", response.text) # Loglara cevabı yaz

        try:
            results = json.loads(response.text)
            return results
        except json.JSONDecodeError:
            # Bazen JSON bozuk gelirse boş dönelim ki uygulama çökmesin
            print("JSON Hatası oluştu")
            return []

    except Exception as e:
        print(f"Sunucu Hatası: {str(e)}")
        return {"hata": str(e)}