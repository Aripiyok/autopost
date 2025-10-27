import asyncio
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError

# === Load .env ===
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
FOTO_CHANNEL = int(os.getenv("FOTO_CHANNEL"))
LINK_CHANNEL = int(os.getenv("LINK_CHANNEL"))
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL")
INTERVAL_MINUTES = float(os.getenv("FORWARD_INTERVAL_MINUTES", "0.5"))  # default 30 detik
START_FROM_ID = int(os.getenv("START_FROM_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

PROGRESS_FILE = Path("progress.json")
NAMA_FILE = Path("teks.txt")

# === Global State ===
is_running = False
interval_minutes = INTERVAL_MINUTES
start_from_index = START_FROM_ID
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
            return int(data.get("last_index", 0)), int(data.get("nama_index", 0))
        except Exception:
            return 0, 0
    return 0, 0


def save_progress(last_index, nama_idx):
    PROGRESS_FILE.write_text(
        json.dumps({"last_index": last_index, "nama_index": nama_idx}),
        encoding="utf-8"
    )


# === Ambil link dari teks ===
def extract_link(text):
    if not text:
        return None
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(1) if match else None


# === Format caption ===
def format_caption(nama, link):
    return f"{nama}\n\ntonton dasini\n{link}"


# === Cari index berdasarkan link ===
async def find_index_by_link(client: TelegramClient, link_channel, target_link: str):
    print(f"🔍 Mencari link '{target_link}' di channel link...")
    msgs = [m async for m in client.iter_messages(link_channel, reverse=False)]
    for i, msg in enumerate(msgs):
        found = extract_link(msg.text or "")
        if found and target_link in found:
            print(f"✅ Link ditemukan di urutan {i}")
            return i
    print("⚠️ Link tidak ditemukan di channel.")
    return None


# === Proses autopost ===
async def autopost(client: TelegramClient, foto_channel, link_channel, target, start_index=0):
    global is_running, interval_minutes, forward_task, nama_index

    if not is_running:
        print("⚠️ Autopost dibatalkan karena bot tidak aktif.")
        return

    nama_list = load_nama_list()
    if not nama_list:
        print("⚠️ Tidak ada nama di teks.txt.")
        is_running = False
        return

    try:
        foto_msgs = [m async for m in client.iter_messages(foto_channel, reverse=False)]
        link_msgs = [m async for m in client.iter_messages(link_channel, reverse=False)]
    except Exception as e:
        print(f"[ERROR] Gagal ambil pesan: {e}")
        is_running = False
        return

    total = min(len(foto_msgs), len(link_msgs), len(nama_list))
    if start_index >= total:
        print(f"⚠️ Start index {start_index} melebihi total pesan ({total}).")
        is_running = False
        return

    print(f"📦 Menemukan {total} postingan siap dikirim. Mulai dari urutan {start_index + 1}\n")

    for i in range(start_index, total):
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

        caption = format_caption(nama, link)

        try:
            file_path = await foto_msg.download_media(file=f"temp_{foto_msg.id}")
            if not file_path:
                print(f"⚠️ Media gagal diunduh pada pesan ke-{i+1}, dilewati.")
                continue

            await client.send_file(target, file=file_path, caption=caption)
            os.remove(file_path)

            print(f"✅ [{i+1}/{total}] {nama} terkirim.")
            nama_index = (nama_index + 1) % len(nama_list)
            save_progress(i, nama_index)
            await asyncio.sleep(interval_minutes * 60)

        except FloodWaitError as e:
            print(f"🚨 Flood wait {e.seconds}s — menunggu...")
            await asyncio.sleep(e.seconds + 5)

        except RPCError as e:
            if "file reference" in str(e).lower():
                print(f"⚠️ File reference expired di pesan {i+1}, mencoba ulang...")
                try:
                    file_path = await foto_msg.download_media(file=f"temp_retry_{foto_msg.id}")
                    await client.send_file(target, file=file_path, caption=caption)
                    os.remove(file_path)
                except Exception as err:
                    print(f"[WARN] Gagal ulang kirim pesan {i+1}: {err}")
            else:
                print(f"[RPC ERROR] {e}")
                await asyncio.sleep(5)

        except Exception as e:
            if "PersistentTimestampOutdatedError" in str(e):
                print("⚠️ Telegram desync, lanjut tanpa menghentikan bot...")
                continue
            print(f"[WARN] Gagal kirim posting ke-{i+1}: {e}")
            await asyncio.sleep(10)

    print("✅ Semua postingan selesai.")
    if i + 1 >= total:
        is_running = False
    forward_task = None


# === Fungsi utama ===
async def main():
    global is_running, interval_minutes, start_from_index, forward_task

    client = TelegramClient("auto_poster_session", API_ID, API_HASH)
    await client.start()

    foto_channel = await client.get_entity(FOTO_CHANNEL)
    link_channel = await client.get_entity(LINK_CHANNEL)
    target = await client.get_entity(TARGET_CHANNEL)

    print("=" * 60)
    print("🚀 AUTOPOST FOTO + LINK + NAMA (Stable v3.4)")
    print(f"📤 FOTO_CHANNEL : {FOTO_CHANNEL}")
    print(f"🔗 LINK_CHANNEL : {LINK_CHANNEL}")
    print(f"📥 TARGET_CHANNEL : {TARGET_CHANNEL}")
    print(f"⏱️ Interval : {interval_minutes} menit ({round(interval_minutes*60,2)} detik)")
    print("=" * 60)

    @client.on(events.NewMessage(from_users=OWNER_ID))
    async def command_handler(event):
        global is_running, interval_minutes, start_from_index, forward_task

        text = (event.raw_text or "").strip()
        # 🔒 Abaikan pesan tanpa awalan "/"
        if not text.startswith("/"):
            return

        args = text.split(maxsplit=1)
        cmd = args[0].lower()

        if cmd == "/on":
            if is_running or forward_task:
                await event.reply("⚠️ Bot sudah berjalan.")
                return
            is_running = True
            forward_task = asyncio.create_task(
                autopost(client, foto_channel, link_channel, target, start_from_index)
            )
            await event.reply(f"✅ Bot mulai kirim postingan otomatis dari urutan {start_from_index + 1}.")

        elif cmd == "/off":
            is_running = False
            if forward_task:
                forward_task.cancel()
                forward_task = None
            await event.reply("🛑 Bot dihentikan.")

        elif cmd == "/status":
            status = "🟢 Aktif" if is_running else "🔴 Nonaktif"
            await event.reply(
                f"📊 Status: {status}\n"
                f"⏱️ Interval: {interval_minutes} menit ({round(interval_minutes*60,2)} detik)\n"
                f"▶️ Mulai dari: {start_from_index + 1}\n"
                f"🏷️ Nama index: {nama_index}\n"
                f"📸 Foto: {FOTO_CHANNEL}\n"
                f"🔗 Link: {LINK_CHANNEL}\n"
                f"📥 Target: {TARGET_CHANNEL}"
            )

        elif cmd.startswith("/setting"):
            if len(args) == 2:
                try:
                    val = float(args[1])
                    if val <= 0:
                        await event.reply("⚠️ Interval harus lebih dari 0.")
                        return
                    interval_minutes = val
                    detik = round(val * 60, 2)
                    await event.reply(f"✅ Interval diubah ke {val} menit ({detik} detik).")
                except ValueError:
                    await event.reply("⚙️ Gunakan: /setting <menit> (contoh: /setting 0.05 untuk 3 detik)")
            else:
                await event.reply("⚙️ Gunakan: /setting <menit> (contoh: /setting 0.5 = 30 detik)")

        elif cmd.startswith("/start"):
            if len(args) == 2:
                arg = args[1].strip()
                if arg.isdigit():
                    start_from_index = int(arg)
                    if is_running or forward_task:
                        await event.reply("⚠️ Bot sudah berjalan, matikan dulu dengan /off")
                        return
                    is_running = True
                    forward_task = asyncio.create_task(
                        autopost(client, foto_channel, link_channel, target, start_from_index)
                    )
                    await event.reply(f"🚀 Mulai dari posting ke-{start_from_index + 1}.")
                elif arg.startswith("http"):
                    idx = await find_index_by_link(client, link_channel, arg)
                    if idx is not None:
                        start_from_index = idx
                        is_running = True
                        forward_task = asyncio.create_task(
                            autopost(client, foto_channel, link_channel, target, start_from_index)
                        )
                        await event.reply(f"🚀 Ditemukan link! Mulai dari urutan ke-{idx + 1}.")
                    else:
                        await event.reply("⚠️ Link tidak ditemukan di channel link.")
                else:
                    await event.reply("⚙️ Gunakan: /start <nomor> atau /start <link>")
            else:
                await event.reply("⚙️ Gunakan: /start <nomor> atau /start <link>")

        else:
            await event.reply("❓ /on | /off | /status | /setting <menit> | /start <nomor|link>")

    # === Loop utama dengan auto-reconnect ===
    while True:
        try:
            await client.run_until_disconnected()

        except (OSError, ConnectionError) as e:
            print(f"⚠️ Jaringan terputus: {e}. Reconnect 5 detik...")
            await asyncio.sleep(5)
            try:
                if not await client.is_connected():
                    await client.connect()
                    print("🔁 Client tersambung ulang ke Telegram.")
            except Exception as err:
                print(f"❌ Gagal reconnect: {err}")
            continue

        except Exception as e:
            if "PersistentTimestampOutdatedError" in str(e):
                print("⚠️ Telegram desync: memperbarui timestamp client tanpa memutus event handler...")
                try:
                    await client.connect()
                    print("🔁 Sinkronisasi Telegram berhasil diperbarui.")
                except Exception as err:
                    print(f"❌ Gagal sync ulang: {err}")
                    await asyncio.sleep(5)
                continue

            print(f"[MAIN ERROR] {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
