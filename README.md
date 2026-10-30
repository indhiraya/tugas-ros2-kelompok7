# Tugas Kelompok ROS2: Distributed Digit Relay (Turtlesim)

## Anggota Kelompok

| Nama | NRP |
|------|-----|
| Muhammad Khibban I'tishom | 5025231126 |
| Zaky Fathurrahman | 5025231105 |
| Azhar Hafiz Andanianto | 5025231118 |
| Irfan Priyo Putranto | 5025231230 |
| Rachmat Ramadhan | 5025231193 |
| Indhira Ayu Puspita Ningrum | 5025231316 |

## Langkah Pengerjaan

1. **Isi tabel anggota** di atas, lalu commit dan push.
2. **Clone repo ini sebagai folder `src` di workspace** (bukan di dalam `src`):
   ```bash
   mkdir -p ~/ros2_ws && cd ~/ros2_ws
   git clone <URL_REPO_KELOMPOK> src
   ```
3. **Buat package** di dalam `~/ros2_ws/src` dan kerjakan tugas sesuai deskripsi di bawah.
4. **Build** dari root workspace:
   ```bash
   cd ~/ros2_ws
   colcon build
   source install/setup.bash
   ```
5. **Jalankan** seluruh sistem dengan satu perintah:
   ```bash
   ros2 launch <nama_package> relay.launch.py
   ```
6. **Commit dan push** dari `~/ros2_ws/src`. Setiap anggota commit bagiannya sendiri dengan akun GitHub masing-masing:
   ```bash
   cd ~/ros2_ws/src
   git add .
   git commit -m "deskripsi perubahan"
   git push
   ```

---

### 1. Deskripsi Tugas

Buatlah sebuah sistem terdistribusi multi-node pada ROS2 di mana setiap anggota kelompok mengontrol satu node independen untuk menggambar urutan angka yang terus bertambah (incrementing counter) secara bergantian di dalam `turtlesim`. Seluruh koordinasi giliran antar-node wajib berjalan otomatis menggunakan mekanisme komunikasi ROS2 (topic/service) tanpa intervensi manual atau hardcoded delay.

### 2. Alur Mekanisme & Siklus

Sistem akan berjalan tepat sebanyak **2 siklus penuh** sebelum berhenti otomatis:

* **Siklus 1 (Angka $1 \dots N$):**
  * Node Anggota 1 aktif, bergerak ke Slot 1, dan menggambar angka `1`.
  * Setelah selesai, Node Anggota 1 mengirimkan token/sinyal giliran ke Anggota 2 melalui ROS2.
  * Node Anggota 2 bergerak ke Slot 2, menggambar angka `2`, dan mengoper giliran ke anggota berikutnya.
  * ...proses berlanjut berurutan hingga Anggota $N$ menggambar angka $N$.
* **Transisi Siklus (Clear Canvas):**
  * Ketika Anggota $N$ selesai, giliran dikembalikan ke Anggota 1.
  * Sebelum memulai siklus kedua, Anggota 1 memanggil service `/clear` milik turtlesim untuk membersihkan kanvas.
* **Siklus 2 (Angka $(N+1) \dots 2N$):**
  * Anggota 1 menggambar angka $(N+1)$ di Slot 1.
  * Anggota 2 menggambar angka $(N+2)$ di Slot 2, berlanjut hingga Anggota $N$ selesai menggambar $2N$.
* **Terminasi / Selesai:**
  * Setelah Anggota $N$ menyelesaikan gambar di siklus 2, sistem harus berhenti secara anggun (graceful shutdown atau node masuk ke state idle).

### 3. Tata Letak Kanvas & Skala (Layout Constraint)

Kanvas turtlesim berukuran terbatas (koordinat sekitar $0.0$ hingga $11.0$):

* **Format Penempatan Bebas:** Tata letak penempatan angka **dibebaskan**, namun sangat disarankan menggunakan format **2 baris** (misal: baris atas untuk anggota 1–4/5, baris bawah untuk anggota berikutnya) atau **grid $3 \times 3$**.
* **Kerapian:** Angka **tidak boleh menabrak batas dinding kanvas** dan **tidak boleh tumpang tindih (overlap)**, terutama saat memasuki angka 2 digit pada Siklus 2. Mahasiswa diperbolehkan menyesuaikan kecepatan gerak, durasi, atau scaling koordinat masing-masing node.

### 4. Ketentuan Teknis

1. **Pembagian Workload:** Git commit history harus mencerminkan kontribusi masing-masing anggota.
2. **Sinkronisasi Giliran:** Node berkomunikasi melalui topic dengan pesan yang mencakup minimal status giliran:
   * `current_number` (int)
   * `active_member` (int)

   Node harus tetap berada dalam kondisi diam (idle) hingga gilirannya tiba.
3. **Manajemen Pena & Reset:**
   * Setiap anggota wajib menggunakan warna pena yang berbeda (atur via service `/turtle1/set_pen`).
   * Pena wajib diangkat (`off: 1`) saat kura-kura berpindah antar-posisi slot agar tidak meninggalkan coretan liar.
   * Penghapusan kanvas antar-siklus wajib menggunakan pemanggilan service `/clear`.
4. **Master Launch File:** Seluruh sistem (node `turtlesim_node` beserta seluruh node anggota) harus dapat dijalankan secara bersamaan hanya dengan **satu perintah launch**:
   ```bash
   ros2 launch <nama_package> relay.launch.py
   ```
