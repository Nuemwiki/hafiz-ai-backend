from fastapi import FastAPI, UploadFile, File
import google.generativeai as genai
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# 1. Çevresel Değişkenleri Yükle (.env dosyasını okur)
load_dotenv()

# 2. API Anahtarını Al
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("GOOGLE_API_KEY bulunamadı! Lütfen .env dosyasını kontrol et.")

# 3. Google Gemini'yi Ayarla
genai.configure(api_key=api_key)

# --- HAFIZ AYARI (SYSTEM INSTRUCTION) ---
# Senin eski kodundaki "Lafız bakımından benzerlik" mantığını buraya işledik.
system_instruction = """
Sen, Kuran-ı Kerim konusunda uzman, kıraat ve hafızlık eğitimi veren tecrübeli bir "Hafız Hocası"sın. 
Görevin: Sana gönderilen ses dosyasındaki Kuran tilavetini dinlemek ve bir Hafız öğrencisine JSON formatında net bir geri bildirim vermektir.

ANALİZ KURALLARI:
1.  **Sure, Ayet ve Sayfa Tespiti:** Okunan ayetin hangi sure, kaçıncı ayet olduğunu ve yaklaşık sayfa numarasını tespit et.
2.  **Arapça Metin:** Ayetin orijinal Arapça metnini yaz.
3.  **Meal:** Kısa ve anlaşılır Türkçe mealini yaz.
4.  **MÜTEŞABİH (EN ÖNEMLİ KISIM):**
    * Kullanıcı bir HAFIZDIR. Sadece manası benzeyenleri değil, özellikle **LAFIZ (Söz/Kelime dizilişi)** bakımından benzer olan ayetleri tespit et.
    * Öğrencinin okurken "acaba hangisiydi?" diye karıştırabileceği, başı veya sonu benzeyen ayetleri hatırlat.
    * Örnek: "Bu ayetin başı ... suresindeki ... ayetle aynı başlar, karıştırma!" gibi uyarılar yap.
    * Eğer lafız bakımından (kelime olarak) belirgin bir benzeri yoksa, bunu belirt.

CEVAP FORMATI (JSON):
Cevabı sadece aşağıdaki JSON formatında ver, başka bir şey yazma:
{
  "baslik": "Sure Adı - Ayet No (Sayfa No)",
  "arapca": "Arapça Metin Buraya",
  "meal": "Türkçe Meal Buraya",
  "mutesabih_notu": "Buraya hafızlık uyarını yaz. Hangi sureyle karışabilir? Lafız benzerliği nedir? Samimi bir hoca üslubuyla uyar.",
  "genel_yorum": "Hacım maşallah ağzına sağlık... diye başlayan kısa motive edici yorum."
}
"""

generation_config = {
    "temperature": 0.3, # Daha kesin cevaplar için düşürdük
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=generation_config,
    system_instruction=system_instruction,
)

# 4. FastAPI Uygulamasını Başlat
app = FastAPI()

# CORS Ayarları (Her yerden erişime izin ver - Mobil uygulama için gerekli)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"Mesaj": "Hafız AI Sunucusu Çalışıyor! (Hafız Modu Aktif)"}

@app.post("/analiz-et")
async def analiz_et(file: UploadFile = File(...)):
    try:
        # 1. Dosyayı oku
        content = await file.read()

        # 2. Gemini'ye gönder
        response = model.generate_content([
            "Bu tilaveti bir hafız hocası gözüyle analiz et.",
            {"mime_type": file.content_type, "data": content}
        ])

        # 3. Cevabı döndür
        return response.text

    except Exception as e:
        return {"hata": str(e)}