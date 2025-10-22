import os
import sys
import asyncio
from telethon import TelegramClient, Button
from dotenv import load_dotenv

# === Load ENV ===
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
foto_channel = int(os.getenv("FOTO_CHANNEL"))
link_channel = int(os.getenv("LINK_CHANNEL"))
target_channel = int(os.getenv("TARGET_CHANNEL"))
delay_seconds = int(os.getenv("DELAY_SECONDS", "60"))

# === Global State ===
is_running = False
custom_delays = None
button_title = "🎬 TONTON DSINI"
button_link = "https://example.com"

# === Utility ===
def load_texts(filename="teks.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("❌ File teks.txt tidak ditemukan!")
        return []

def extract_link(msg):
    text = msg.message or ""
    for word in text.split():
        if word.startswith("http://") or word.startswith("https://") or word.startswith("www."):
            return word.strip()
    return None

async def send_post(client, foto_msg, link_msg, teks, index, total):
    global button_title, button_link
    media = foto_msg.photo or foto_msg.video or foto_msg.file
    if not media:
        print(f"⚠️ [{index+1}] Tidak ada media, dilewati.")
        return
    url = extract_link(link_msg)
    if not url:
        print(f"⚠️ [{index+1}] Tidak ada link, dilewati.")
        return
    caption = f"{teks}\n\ntonton dsini\n{url}"
    buttons = [[Button.url(button_title, button_link)]]
    await client.send_file(target_channel, file=media, caption=caption, buttons=buttons)
    print(f"📤 [{index+1}/{total}] Terkirim: {teks[:40]}...")

async def start_posting(client, texts, foto_msgs, link_msgs):
    global is_running, custom_delays
    total = min(len(foto_msgs), len(link_msgs), len(texts))
    print(f"📦 Siap mengirim {total} posting...\n")
    is_running = True
    for i in range(total):
        if not is_running:
            print("⏸️ Dihentikan oleh user (/off)")
            break
        await send_post(client, foto_msgs[i], link_msgs[i], texts[i], i, total)
        if i < total - 1:
            delay = (custom_delays[i] if (custom_delays and i < len(custom_delays)) else delay_seconds)
            print(f"⏳ Delay {delay} detik...")
            await asyncio.sleep(delay)
    print("🚀 Semua posting selesai atau dihentikan.")

async def handle_command(cmd, client):
    global is_running, custom_delays, button_title, button_link
    if cmd.startswith("/setting"):
        parts = cmd.split()[1:]
        try:
            custom_delays = [int(p) for p in parts]
            print(f"⚙️ Delay custom diatur: {custom_delays}")
        except ValueError:
            print("❌ Format salah. Contoh: /setting 60 30 120")
    elif cmd.startswith("/judul"):
        title = cmd.replace("/judul", "", 1).strip()
        if title:
            button_title = title
            print(f"🆕 Judul tombol diubah jadi: {button_title}")
        else:
            print("❌ Format salah. Contoh: /judul 🎬 Tonton Sekarang")
    elif cmd.startswith("/link"):
        link = cmd.replace("/link", "", 1).strip()
        if link.startswith("http://") or link.startswith("https://") or link.startswith("www."):
            button_link = link
            print(f"🔗 Link tombol diubah jadi: {button_link}")
        else:
            print("❌ Format salah. Contoh: /link https://example.com")
    elif cmd == "/on":
        is_running = True
        print("✅ Mode ON aktif.")
    elif cmd == "/off":
        is_running = False
        print("🛑 Mode OFF — Bot dijeda.")
    elif cmd == "/help":
        print("\n=== DAFTAR COMMAND ===")
        print("/start   → mulai posting dari urutan 1")
        print("/setting <angka...> → ubah delay (contoh: /setting 60 30 90)")
        print("/judul <teks> → ubah teks tombol")
        print("/link <url> → ubah link tombol")
        print("/on → aktifkan bot")
        print("/off → hentikan bot sementara")
        print("/help → tampilkan bantuan")
        print("/exit → keluar dari bot\n")
    elif cmd == "/exit":
        print("👋 Keluar dari bot.")
        sys.exit(0)
    elif cmd == "/start":
        texts = load_texts()
        if not texts:
            print("⚠️ teks.txt kosong / tidak ditemukan.")
            return
        foto_msgs = [m async for m in client.iter_messages(foto_channel, limit=len(texts))]
        link_msgs = [m async for m in client.iter_messages(link_channel, limit=len(texts))]
        foto_msgs.reverse()
        link_msgs.reverse()
        await start_posting(client, texts, foto_msgs, link_msgs)
    else:
        print("❓ Perintah tidak dikenal. Gunakan /help untuk daftar lengkap.")

async def main():
    async with TelegramClient("autoposter_session", api_id, api_hash) as client:
        print("✅ Login berhasil.")
        print("\nKetik /help untuk melihat semua command.\n")
        while True:
            try:
                cmd = input("CMD> ").strip()
                await handle_command(cmd, client)
            except KeyboardInterrupt:
                print("\n🛑 Keluar dari bot.")
                break
            except Exception as e:
                print("❌ Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
