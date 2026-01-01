from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Gizli şifreleri (API Key) yükle
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Eğer anahtar yoksa uyarı ver (Güvenlik önlemi)
if not api_key:
    print("HATA: API Key bulunamadı! .env dosyasını kontrol et.")
else:
    genai.configure(api_key=api_key)

# 2. Modeli Seç (En ucuz ve hızlı olan Flash modeli)
model = genai.GenerativeModel("models/gemini-2.5-flash")

# 3. Uygulamayı Başlat
app = FastAPI()

# --- BURASI BİZİM KAPIMIZ ---
@app.get("/")
def ana_sayfa():
    return {"Mesaj": "Hafız AI Sunucusu Çalışıyor! Hoş geldin."}

@app.post("/analiz-et")
async def ses_analiz(file: UploadFile = File(...)):
    try:
        # Gelen ses dosyasını oku
        ses_verisi = await file.read()
        
        # Gemini'ye gidecek emir (Prompt)
        prompt = """
        Bu bir Kuran tilavetidir. Hafız bir öğrenci okuyor.
        Lütfen şunları yap:
        1. Hangi sure ve ayet olduğunu tespit et.
        2. Okunan Arapça metni yaz.
        3. Mealini yaz.
        4. Müteşabih (benzer) ayetler varsa uyar, yoksa 'Benzerlik yok' de.
        Cevabı güzel bir metin olarak ver.
        """
        
        # Gemini'ye sor
        response = model.generate_content([
            prompt,
            {'mime_type': file.content_type, 'data': ses_verisi}
        ])
        
        # Cevabı geri gönder
        return {"sonuc": response.text}

    except Exception as hata:
        return {"hata": str(hata)}