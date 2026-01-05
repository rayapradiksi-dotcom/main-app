# 📡 Aplikasi Chat TCP/IP (Client–Server)

Aplikasi ini merupakan sistem **chat berbasis TCP/IP** dengan arsitektur **client–server** yang dikembangkan menggunakan bahasa pemrograman **Python**.  
Aplikasi mendukung komunikasi **pesan private**, **pesan broadcast**, serta mampu melayani banyak client secara **concurrent (multithreading)**.

Proyek ini dibuat untuk memenuhi **Ujian Akhir Semester (UAS)** Mata Kuliah **Komunikasi Data**  
Program Studi **D-III Teknik Komputer**.

---

## 📌 Fitur Utama

- Koneksi client–server menggunakan protokol **TCP**
- Pengiriman pesan **private**
- Pengiriman pesan **broadcast**
- Mendukung banyak client secara bersamaan (multithreading)
- Optimasi struktur data menggunakan **Dictionary (Hash Map)**
- Kompleksitas waktu akses data **O(1)**
- Penambahan **timestamp** pada pesan

---

## 🧱 Arsitektur Sistem

### Server
- Menerima koneksi client
- Menyimpan daftar client online
- Meneruskan pesan private dan broadcast
- Mengelola thread dan sinkronisasi data

### Client
- Menghubungkan diri ke server
- Mengirim pesan
- Menerima pesan secara real-time

Komunikasi menggunakan **socket TCP (SOCK_STREAM)** yang bersifat reliable dan connection-oriented.

---

## ⚙️ Require

- Python 3.x
- socket
- threading
- datetime
- TCP/IP
- customtkinter
- matplotlib

---

## 🚀 Cara Menjalankan Program
### Menjalankan Server
```bash
python chatserver.py
python chatclient.py
```
---
