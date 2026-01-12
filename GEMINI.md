# MoonTele: Telegram Automation CLI (Lite)

Versi ringkas dan efisien dari alat otomatisasi Telegram yang berfokus pada manajemen target cerdas dan pengiriman pesan massal.

## 🚀 Fitur Utama

1.  **Smart Target Detection (Deteksi Otomatis)**:
    *   Tidak perlu lagi memilih grup secara manual dari daftar panjang.
    *   Cukup tempel **Link Pesan** dari grup, channel, atau topik forum. Kode akan otomatis mendeteksi Chat ID dan Topic ID.
    *   Mendukung penambahan target via **User ID** untuk chat pribadi.
2.  **Manajemen Template**:
    *   Simpan daftar target ke dalam grup (template) agar bisa digunakan kembali dengan satu klik.
    *   Mendukung banyak template per akun.
3.  **Broadcast Engine**:
    *   Kirim pesan massal ke banyak target sekaligus.
    *   Dua mode input: **Teks Manual** atau **Forward via Link** (mendukung Foto, Video, Album, dan File).
    *   Dilengkapi dengan sistem **Delay** untuk menghindari deteksi spam oleh Telegram.
4.  **Multi-Account Support**:
    *   Kelola dan berpindah antar banyak akun Telegram dengan mudah.

## 🛠️ Persyaratan Sistem

*   **Lingkungan**: Python 3.x (Berjalan optimal di Termux Ubuntu).
*   **Library**: `telethon`, `rich`.

## 📂 Struktur File

*   `MoonTele.py`: Script utama aplikasi.
*   `accounts.json`: Menyimpan kredensial API akun-akun Anda.
*   `target_templates.json`: Menyimpan daftar target berdasarkan akun masing-masing.
*   `session_*.session`: File sesi enkripsi Telegram untuk login otomatis.

## 📖 Cara Penggunaan

1.  Jalankan aplikasi: `python3 MoonTele.py`
2.  **Manajemen Akun**: Tambahkan akun baru menggunakan API ID dan API Hash dari [my.telegram.org](https://my.telegram.org).
3.  **Membuat Template**: 
    *   Pilih menu `Manage Target Templates`.
    *   Pilih `Create New Template`.
    *   Tempel link pesan dari grup target. Contoh: `https://t.me/grup_a/123`.
    *   Ketik `done` jika sudah selesai menambahkan target.
4.  **Broadcast**:
    *   Pilih menu `Send Message / Broadcast`.
    *   Pilih template yang sudah dibuat.
    *   Pilih sumber pesan (Ketik manual atau ambil dari link pesan lain).
    *   Tentukan delay (disarankan minimal 5 detik).

---
*Dikembangkan untuk efisiensi dan kemudahan penggunaan di lingkungan CLI.*
