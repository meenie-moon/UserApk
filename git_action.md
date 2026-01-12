# Panduan Universal: Build Python ke Android via GitHub Actions
**Created Date:** 12 Jan 2026
**Context:** Rangkuman best-practice untuk menghindari error saat compile APK menggunakan Buildozer & KivyMD di lingkungan CI/CD (GitHub Actions).

## 1. Filosofi Dasar (The Golden Rules)
1.  **Jangan Gunakan `ubuntu-latest`:** Saat ini (2025/2026), `ubuntu-latest` (v24.04) memiliki library sistem yang terlalu baru dan sering gagal mengompilasi `hostpython3`.
    *   ✅ **Gunakan:** `runs-on: ubuntu-22.04` (Stabil).
2.  **Java Versioning:** Android API 33+ (Android 13) mewajibkan Java 17 untuk menjalankan Gradle.
    *   ❌ Java 11 (Default Runner) -> Error `Gradlew failed`.
    *   ✅ **Wajib:** Inject `actions/setup-java@v3` versi 17.
3.  **Hindari Rust (Jika Memungkinkan):** Library seperti `cryptg` membutuhkan compiler Rust/Cargo yang rumit di-setup untuk cross-compilation Android.
    *   ✅ **Solusi:** Gunakan alternatif Pure Python (misal: `pyaes` untuk Telethon).
4.  **Hemat Resource:** GitHub Actions punya batas disk dan waktu.
    *   ✅ Set `android.archs = arm64-v8a` (Hapus `armeabi-v7a` jika target pasar HP modern). Ini menghemat 50% waktu build dan space.

---

## 2. Dependensi Sistem (Apt-Get)
Jangan menginstall sembarang library. Library multimedia (`ffmpeg`, `gstreamer`) di host system sering konflik dan **TIDAK DIBUTUHKAN** untuk build (Buildozer akan mendownload resepnya sendiri).

**Paket Wajib (Essential Only):**
```bash
sudo apt-get install -y \
    build-essential git python3 python3-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    libportmidi-dev libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev \
    libffi-dev libtool libtool-bin autoconf automake libltdl-dev pkg-config \
    libssl-dev libsqlite3-dev libncurses5-dev libncursesw5-dev \
    libreadline-dev libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev \
    liblzma-dev tk-dev
```
*Catatan: `libssl-dev` vital untuk HTTPS, `libsqlite3-dev` vital untuk database.*

---

## 3. Konfigurasi `buildozer.spec` (Checklist)

Pastikan poin-poin ini diatur dengan benar untuk menghindari error umum:

| Setting | Value | Alasan |
| :--- | :--- | :--- |
| `version` | `0.1` | Error jika kosong. |
| `requirements` | `..., pyaes` | **Hidden Dependency!** Telethon butuh ini di Android. |
| `android.api` | `33` | Standar Play Store saat ini. |
| `android.minapi` | `21` | Support Android 5.0+. |
| `android.ndk` | `25b` | Versi stabil untuk API 33. |
| `android.accept_sdk_license` | `True` | Mencegah build hang menunggu input "Yes". |
| `android.enable_androidx` | `True` | **WAJIB** untuk KivyMD modern. Jika `False`, APK gagal install/package. |
| `android.archs` | `arm64-v8a` | Mencegah "Disk Full" di GitHub Actions. |
| `log_level` | `2` | Debugging. Jika log kepanjangan (truncated), turunkan ke `1`. |

---

## 4. Template Workflow (`build.yml`) Teruji

Gunakan struktur ini sebagai basis:

```yaml
name: Build Android APK
on: [push]

jobs:
  build:
    runs-on: ubuntu-22.04  # PENTING: Jangan latest

    steps:
      - uses: actions/checkout@v3

      # Setup Java 17 (Wajib untuk API 33+)
      - name: Set up JDK 17
        uses: actions/setup-java@v3
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install Dependencies
        run: |
          sudo apt-get update
          # Masukkan list apt-get "Paket Wajib" di atas sini
          pip install --upgrade pip
          pip install buildozer cython==0.29.33

      - name: Build with Buildozer
        run: yes | buildozer android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: My-APK
          path: bin/*.apk  # Path biasanya di root bin/, bukan didalam folder project
```

---

## 5. Troubleshooting (Kamus Masalah)

### A. `LT_SYS_SYMBOL_USCORE` / `autoconf failed`
*   **Sebab:** Kekurangan `libtool`, `automake`, atau `autoconf`.
*   **Solusi:** Install paket tersebut via apt-get.

### B. `hostpython3 failed`
*   **Sebab:** Gagal compile Python karena header file kurang (SSL, SQLite, Readline).
*   **Solusi:** Install `libssl-dev`, `libsqlite3-dev`, `libreadline-dev`. Pastikan pakai `ubuntu-22.04`.

### C. `Gradlew failed`
*   **Sebab:** Versi Java tidak kompatibel dengan Gradle Plugin.
*   **Solusi:** Gunakan Java 17 (`actions/setup-java`).

### D. App Force Close (Langsung keluar) saat dibuka
*   **Sebab:** Missing Module di Python (biasanya crypto atau database).
*   **Solusi:**
    *   Cek log `adb logcat | grep python`.
    *   Jika Telethon: Tambahkan `pyaes` di requirements.
    *   Jika KivyMD: Pastikan `pillow` ada.

### E. `Action failed with exit code 137`
*   **Sebab:** Out of Memory (RAM habis).
*   **Solusi:** Kurangi `android.archs` hanya ke satu arsitektur saja (misal `arm64-v8a`).

---

**Pesan untuk AI Masa Depan:**
"Jangan tebak-tebakan library. Scan import code user (`grep "^import" main.py`), lalu petakan ke `requirements` buildozer. Selalu mulai dari Ubuntu 22.04 dan Java 17 untuk Android Development di Cloud."
