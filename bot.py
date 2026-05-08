"""
adhahi.dz Wilaya Availability Monitor Bot
Scrapes the registration page every 60 seconds and sends a Telegram
notification whenever any wilaya changes its booking status.
"""

import asyncio
import json
import os
import logging
from datetime import datetime
from playwright.async_api import async_playwright
import httpx

# ─────────────────────────────────────────────
#  CONFIG — fill these in before running
# ─────────────────────────────────────────────
TELEGRAM_TOKEN  = "8478971910:AAEg10f-Netd_0MtGiyE5dc5S5Op94yGSc4"
TELEGRAM_CHAT_ID = "6327936488"
TARGET_URL      = "https://adhahi.dz/register"
CHECK_INTERVAL  = 60                            # seconds between checks
STATE_FILE      = "wilaya_state.json"           # persists state across restarts
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


async def send_telegram(message: str):
    """Send a message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            log.info("Telegram message sent ✓")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


async def scrape_wilayas(page) -> dict:
    """
    Navigate to the page, open the wilaya dropdown, and return a dict:
      { "تلمسان": "غير متوفر", "الجزائر": "متاح", ... }
    """
    await page.goto(TARGET_URL, wait_until="networkidle", timeout=30_000)

    # Click the wilaya input to open the dropdown list
    wilaya_input = page.locator("#reg-wilaya")
    await wilaya_input.click()

    # Wait for at least one list item to appear
    await page.wait_for_selector("ul[role='listbox'] li[role='option']", timeout=10_000)

    # Extract all options
    items = await page.locator("ul[role='listbox'] li[role='option']").all()

    wilaya_status = {}
    for item in items:
        text = (await item.inner_text()).strip()
        is_disabled = await item.get_attribute("aria-disabled")

        # Text format: "تلمسان — حجز غير متوفر حاليًا"  or  "تلمسان — متاح للحجز"
        if " — " in text:
            wilaya, status = text.split(" — ", 1)
        else:
            wilaya = text
            status = "غير متوفر" if is_disabled == "true" else "متاح"

        wilaya_status[wilaya.strip()] = status.strip()

    return wilaya_status


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_change_message(changes: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"🔔 <b>تغيير في حالة الحجز — adhahi.dz</b>", f"🕐 {now}\n"]

    for ch in changes:
        wilaya  = ch["wilaya"]
        old_val = ch["old"]
        new_val = ch["new"]

        # Detect if it became available
        is_available = "غير متوفر" not in new_val and "unavailable" not in new_val.lower()

        icon = "✅" if is_available else "❌"
        lines.append(f"{icon} <b>{wilaya}</b>")
        lines.append(f"   قبل: {old_val}")
        lines.append(f"   بعد: {new_val}\n")

    lines.append(f'🔗 <a href="{TARGET_URL}">سجّل الآن</a>')
    return "\n".join(lines)


async def monitor():
    log.info("Starting adhahi.dz monitor...")
    await send_telegram(
        f"🤖 <b>بوت المراقبة شغّال</b>\n"
        f"يتحقق كل {CHECK_INTERVAL} ثانية من توفر الحجز على adhahi.dz\n"
        f"سيتم إشعارك فور فتح أي ولاية 🇩🇿"
    )

    previous_state = load_state()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        while True:
            try:
                log.info("Scraping wilaya list...")
                current_state = await scrape_wilayas(page)
                log.info(f"Found {len(current_state)} wilayas")

                changes = []

                if previous_state:
                    for wilaya, new_status in current_state.items():
                        old_status = previous_state.get(wilaya, "")
                        if old_status and old_status != new_status:
                            changes.append({
                                "wilaya": wilaya,
                                "old": old_status,
                                "new": new_status,
                            })
                            log.info(f"CHANGE: {wilaya} | {old_status} → {new_status}")
                else:
                    log.info("First run — saving baseline state (no notification)")

                if changes:
                    msg = build_change_message(changes)
                    await send_telegram(msg)

                save_state(current_state)
                previous_state = current_state

            except Exception as e:
                log.error(f"Scrape error: {e}")
                await send_telegram(f"⚠️ خطأ في المراقبة:\n<code>{e}</code>")
                # Reload page on error
                try:
                    await page.reload()
                except:
                    page = await context.new_page()

            log.info(f"Sleeping {CHECK_INTERVAL}s...")
            await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(monitor())
