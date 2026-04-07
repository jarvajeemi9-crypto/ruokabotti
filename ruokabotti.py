import asyncio
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ============================================================
# ASETUKSET – muuta nämä omiksi tiedoiksesi!
# ============================================================
BOT_TOKEN = "8453714314:AAHFS4GxZQhwfVQHiaQ40UeJ2IiSDqA2DcM"
CHAT_ID   = 8288984715

RUOKALISTA_URL = "https://kouluruoka.fi/menu/espoo_otaniemenlukio/"

# Ruokailuajat per viikonpäivä
RUOKAILUAJAT = {
    0: "11.40–12.20",   # Maanantai
    1: "11.15–12.00",   # Tiistai
    2: "11.40–12.20",   # Keskiviikko
    3: "12.10–12.40",   # Torstai
    4: "11.15–12.00",   # Perjantai
}

PAIVAT_FI  = ["maanantai", "tiistai", "keskiviikko", "torstai", "perjantai", "lauantai", "sunnuntai"]
PAIVAT_ISO = ["Maanantai", "Tiistai", "Keskiviikko", "Torstai", "Perjantai", "Lauantai", "Sunnuntai"]

# ============================================================
# HAE RUOKA SIVULTA
# ============================================================
def hae_paivan_ruoat() -> dict:
    try:
        r = requests.get(RUOKALISTA_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        return {"virhe": str(e)}

    soup = BeautifulSoup(r.text, "html.parser")
    paiva_fi = PAIVAT_FI[datetime.now().weekday()]

    paivan_h2 = None
    for h2 in soup.find_all("h2"):
        if paiva_fi in h2.get_text().lower():
            paivan_h2 = h2
            break

    if not paivan_h2:
        return {"virhe": "Tänään ei ole ruokalistaa (koulu kiinni?)"}

    lounaat = []
    lounas_lkm = 0

    for tag in paivan_h2.find_next_siblings():
        if tag.name == "h2":
            break
        if tag.name == "div":
            teksti = tag.get_text(" ", strip=True)
            if "henkilöstö" in teksti.lower():
                continue
            if lounas_lkm >= 2:
                continue
            if "kasvis" in teksti.lower():
                otsikko = "Kasvislounas"
            else:
                otsikko = "Lounas"
            # Ruokien nimet ovat h4-tageissa
            ruoat = []
            for h4 in tag.find_all("h4"):
                nimi = h4.get_text(" ", strip=True)
                nimi = re.sub(r"[\(\[][A-ZÄÖÅ\*,\s/]+[\)\]]", "", nimi)
                nimi = re.sub(r"\*", "", nimi).strip()
                if nimi and len(nimi) > 3:
                    ruoat.append(nimi)
            if ruoat:
                lounaat.append({"otsikko": otsikko, "ruoat": ruoat})
                lounas_lkm += 1

    return {"lounaat": lounaat}
# ============================================================
# MUODOSTA TELEGRAM-VIESTI
# ============================================================
def luo_viesti() -> str:
    nyt = datetime.now()
    idx = nyt.weekday()
    paiva = PAIVAT_ISO[idx]
    pvm   = nyt.strftime("%d.%m.%Y")
    aika  = RUOKAILUAJAT.get(idx, "–")

    data = hae_paivan_ruoat()

    if "virhe" in data:
        return f"🍽️ *Otaniemen lukio – {paiva} {pvm}*\n\n⚠️ {data['virhe']}"

    rivit = [
        f"🍽️ *Otaniemen lukio – {paiva} {pvm}*",
        f"🕙 Ilmoitus klo 10:00  |  Ruokailu *{aika}*",
        "",
    ]

    for lounas in data.get("lounaat", []):
        if not lounas["ruoat"]:
            continue
        ots = lounas["otsikko"]
        if "kasvis" in ots.lower():
            rivit.append("🥦 *Kasvislounas*")
        else:
            rivit.append("🍖 *Lounas*")
        for ruoka in lounas["ruoat"]:
            rivit.append(f"   • {ruoka}")
        rivit.append("")

    rivit.append("_Hyvää ruokahalua!_ 😊")
    return "\n".join(rivit)

# ============================================================
# LÄHETÄ VIESTI TELEGRAMIIN
# ============================================================
async def laheta_ruokalista():
    if datetime.now().weekday() >= 5:
        print("Viikonloppu – ei lähetetä.")
        return
    try:
        bot = Bot(token=BOT_TOKEN)
        viesti = luo_viesti()
        await bot.send_message(chat_id=CHAT_ID, text=viesti, parse_mode="Markdown")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Lähetetty!")
    except Exception as e:
        print(f"Virhe: {e}")

# ============================================================
# PÄÄOHJELMA – käynnistää ajastimen
# ============================================================
async def main():
    print("🤖 Ruokabotti käynnistyy...")
    print("   Lähettää arkisin klo 10:00\n")

    scheduler = AsyncIOScheduler(timezone="Europe/Helsinki")
    scheduler.add_job(
        laheta_ruokalista,
        trigger="cron",
        hour=10,
        minute=0,
        day_of_week="mon-fri",
    )
    scheduler.start()

    # Lähetä testilista heti käynnistyksen yhteydessä
    print("Lähetetään testilista nyt...")
    await laheta_ruokalista()

    # Pidä ohjelma käynnissä
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        print("\nBotti pysäytetty.")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())