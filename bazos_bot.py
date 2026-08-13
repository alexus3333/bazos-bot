import os
import re
import time
import threading
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

# Flask server pre Render (aby služba nezdochla)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot beží!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==================== KONFIGURÁCIA ====================
TELEGRAM_BOT_TOKEN = "8560776124:AAGGfg1rud3GL11WmUKGVKA9kzDmtVfP_BM"
TELEGRAM_CHAT_ID = "8992331753"
GEMINI_API_KEY = "AQ.Ab8RN6JIDC-0Gtx-63GsbRGgpURBm1M2qdUIR9Ug1V4N6WZIQ"

MAX_PRICE = 500  # Maximálna cena v EUR
SEEN_FILE = "seen_ids.txt"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "sk-SK,sk;q=0.9,en-US;q=0.8,en;q=0.7"
}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Chyba pri posielaní správ na Telegram: {e}")

def load_seen_ids():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_id(item_id):
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(f"{item_id}\n")

def check_bazos():
    url = "https://sport.bazos.sk/?hledat=bicykel"
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            print(f"Bazoš vrátil kód: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        inzeraty = soup.find_all("div", class_="inzeraty")
        if not inzeraty:
            inzeraty = soup.find_all("div", class_="inzeratydirekt")

        if not inzeraty:
            print("Na stránke sa nenašli žiadne inzeráty.")
            return

        seen_ids = load_seen_ids()
        nasiel_nove = False

        for inz in inzeraty:
            link_tag = inz.find("a", href=True)
            if not link_tag or "/inzerat/" not in link_tag["href"]:
                continue

            title_tag = inz.find("h2")
            title = title_tag.text.strip() if title_tag else link_tag.text.strip()
            link = "https://sport.bazos.sk" + link_tag["href"]
            
            match = re.search(r"/inzerat/(\d+)/", link)
            if not match:
                continue
            item_id = match.group(1)

            if item_id in seen_ids:
                continue

            price_tag = inz.find("div", class_="inzeratycena")
            price_text = price_tag.text.strip() if price_tag else ""
            price_match = re.search(r"(\d[\d\s]*)", price_text.replace(" ", ""))
            price = int(price_match.group(1)) if price_match else 0

            if 0 < price <= MAX_PRICE:
                nasiel_nove = True
                desc_tag = inz.find("div", class_="popis")
                desc = desc_tag.text.strip() if desc_tag else ""

                prompt = f"Si expert na bicykle. Posúď túto ponuku z Bazošu:\nNázov: {title}\nCena: {price} EUR\nPopis: {desc}\nJe to výhodná kúpa za túto cenu? Napíš krátke 2-3 vetové zhodnotenie v slovenčine."
                try:
                    ai_response = model.generate_content(prompt)
                    ai_analysis = ai_response.text.strip()
                except Exception as e:
                    ai_analysis = "AI sa nepodarilo vyhodnotiť inzerát."

                msg = f"🚲 <b>Nový bicykel na Bazoši!</b>\n\n<b>{title}</b>\n💰 Cena: {price} EUR\n🔗 <a href='{link}'>Otvoriť inzerát</a>\n\n🤖 <b>AI Hodnotenie:</b>\n{ai_analysis}"
                send_telegram_message(msg)
                print(f"Odoslaný inzerát: {title}")

                save_seen_id(item_id)

        if not nasiel_nove:
            print("Kontrola dokončená - žiadne nové výhodné bicykle.")

    except Exception as e:
        print(f"Chyba pri kontrole: {e}")

def bot_loop():
    print(f"Bot bol spustený a sleduje bicykle do {MAX_PRICE} EUR...")
    while True:
        print("Kontrolujem Bazoš...")
        check_bazos()
        time.sleep(120)

if __name__ == "__main__":
    # Spustenie bota v samostatnom vlákne
    t = threading.Thread(target=bot_loop)
    t.daemon = True
    t.start()
    
    # Spustenie Flask servera pre Render
    run_flask()
