import asyncio
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events

# === Load .env ===
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
FOTO_CHANNEL = int(os.getenv("FOTO_CHANNEL"))
LINK_CHANNEL = int(os.getenv("LINK_CHANNEL"))
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL")
INTERVAL_MINUTES = int(os.getenv("FORWARD_INTERVAL_MINUTES", "30"))
START_FROM_ID = int(os.getenv("START_FROM_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))


PROGRESS_FILE = Path("progress.json")
NAMA_FILE = Path("teks.txt")

is_running = False
interval_minutes = INTERVAL_MINUTES
start_from_id = START_FROM_ID
forward_task = None
nama_index = 0


# === Baca nama dari teks.txt ===
def load_nama_list():
    if not NAMA_FILE.exists():
        print("⚠️ File teks.txt tidak ditemukan.")
        return []
    with open(NAMA_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f.readlines() if x.strip()]


# === Simpan & baca progress ===
def load_progress():
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
            return int(data.get("last_id", 0)), int(data.get("nama_index", 0))
        except Exception:
            return 0, 0
    return 0, 0


def save_progress(last_id, nama_idx):
    PROGRESS_FILE.write_text(json.dumps({"last_id": last_id, "nama_index": nama_idx}), encoding="utf-8")


# === Ambil link dari teks ===
def extract_link(text):
    if not text:
        return None
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(1) if match else None


# === Format caption ===
def format_caption(nama, link):
    return f"{nama}\n\ntonton dasini\n{link}"


# === Proses kirim ===
async def autopost(client: TelegramClient, foto_channel, link_channel, target):
    global is_running, interval_minutes, start_from_id, forward_task, nama_index

    nama_list = load_nama_list()
    if not nama_list:
        print("⚠️ Tidak ada nama di teks.txt.")
        return

    try:
        last_saved, nama_idx = load_progress()
        nama_index = nama_idx

        foto_msgs = [m async for m in client.iter_messages(foto_channel, reverse=True)]
        link_msgs = [m async for m in client.iter_messages(link_channel, reverse=True)]

        total = min(len(foto_msgs), len(link_msgs), len(nama_list))
        print(f"📦 Menemukan {total} postingan siap dikirim.\n")

        for i in range(total):
            if not is_running:
                print("⏸️ Bot dihentikan.")
                break

            foto_msg = foto_msgs[i]
            link_msg = link_msgs[i]
            nama = nama_list[nama_index % len(nama_list)]

            link = extract_link(link_msg.text or "")
            if not link:
                print(f"⚠️ Link kosong pada pesan ke-{i+1}, dilewati.")
                continue

            media = foto_msg.photo or foto_msg.video
            if not media:
                print(f"⚠️ Media kosong pada pesan ke-{i+1}, dilewati.")
                continue

            caption = format_caption(nama, link)

            try:
                await client.send_file(target, file=media, caption=caption)
                print(f"✅ [{i+1}/{total}] {nama} terkirim.")
                nama_index = (nama_index + 1) % len(nama_list)
                save_progress(foto_msg.id, nama_index)
                await asyncio.sleep(interval_minutes * 60)
            except Exception as e:
                print(f"[WARN] Gagal kirim posting ke-{i+1}: {e}")

        print("✅ Semua postingan selesai.")
    finally:
        forward_task = None
        is_running = False


# === Fungsi utama ===
async def main():
    global is_running, interval_minutes, start_from_id, forward_task

    client = TelegramClient("autopost_foto_link_nama_session", API_ID, API_HASH)
    await client.start()

    foto_channel = await client.get_entity(FOTO_CHANNEL)
    link_channel = await client.get_entity(LINK_CHANNEL)
    target = await client.get_entity(TARGET_CHANNEL)

    print("=" * 60)
    print("🚀 AUTOPOST FOTO + LINK + NAMA (Full Auto, Single CMD)")
    print(f"📤 FOTO_CHANNEL : {FOTO_CHANNEL}")
    print(f"🔗 LINK_CHANNEL : {LINK_CHANNEL}")
    print(f"📥 TARGET_CHANNEL : {TARGET_CHANNEL}")
    print(f"⏱️ Interval : {interval_minutes} menit")
    print("=" * 60)

    @client.on(events.NewMessage(from_users=OWNER_ID))
    async def command_handler(event):
        global is_running, interval_minutes, start_from_id, forward_task

        cmd = event.raw_text.strip()
        args = cmd.lower().split()

        if cmd == "/on":
            if is_running or forward_task:
                await event.reply("⚠️ Sudah aktif.")
            else:
                is_running = True
                forward_task = asyncio.create_task(autopost(client, foto_channel, link_channel, target))
                await event.reply("✅ Bot mulai kirim postingan otomatis.")

        elif cmd == "/off":
            is_running = False
            if forward_task:
                forward_task.cancel()
                forward_task = None
            await event.reply("🛑 Bot dihentikan.")

        elif cmd.startswith("/setting"):
            if len(args) == 2 and args[1].isdigit():
                val = int(args[1])
                interval_minutes = val
                await event.reply(f"✅ Interval diubah ke {val} menit.")
            else:
                await event.reply("⚙️ Gunakan: /setting <menit>")

        elif cmd == "/status":
            status = "🟢 Aktif" if is_running else "🔴 Nonaktif"
            await event.reply(
                f"📊 Status: {status}\n"
                f"⏱️ Interval: {interval_minutes} menit\n"
                f"🏷️ Nama index: {nama_index}\n"
                f"📸 Foto: {FOTO_CHANNEL}\n"
                f"🔗 Link: {LINK_CHANNEL}\n"
                f"📥 Target: {TARGET_CHANNEL}"
            )

        else:
            await event.reply("❓ /on | /off | /status | /setting <menit>")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
