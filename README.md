1. Membuat perintah di gemini untuk membuat aplikasi menggunakan python
2. Memasukan file dalam folder terstruktur di local
3. Upload ke Repostori Github
4. Masuk ke Pythonanywhere ke console bash lalu clone -- > git clone https://github.com/yogiwicaksonocdm/scanwajah
5. Masuk ke direktori project --> cd scanwajah
6. Buat Virtual Environment khusus -- > mkvirtualenv --python=/usr/bin/python3.10 --system-site-packages absensi-
7. Install Package flask --> pip install --no-cache-dir Flask
8. Uji coba import library --> python -c "import face_recognition, flask, PIL, numpy; print('>>> SEMUA MODULE BERHASIL DIMUAT! <<<')"
9. Setup Web App di Tab Web PythonAnywhere :
	Konfigurasi Manual Configuration di tab Web.
	Buka tab Web > klik Add a new web app.
	Pilih Manual configuration > pilih Python 3.10.Setelah selesai, 
	isi form konfigurasi:	Source code: /home/yogiwicaksonodm/scanwajah
						Working directory: /home/yogiwicaksonodm/scanwajah
						Virtualenv: /home/yogiwicaksonodm/.virtualenvs/absensi-env (atau cukup ketik absensi-env)
10.Edit WSGI Configuration File:
	Hubungkan web server ke file app.py.
	Di tab Web, klik link WSGI configuration file (/var/www/yogiwicaksonodm_pythonanywhere_com_wsgi.py).
	--> 
import os
import sys

project_home = '/home/yogiwicaksonodm/scanwajah'
if project_home not in sys.path:
  sys.path.insert(0, project_home)

from app import app as application

11. Aktifkan Force HTTPS & Reload App
	:Izin akses kamera laptop/HP pengguna.
	Kembali ke tab Web.
	Pada bagian Security, aktifkan toggle Force HTTPS.
	Klik tombol hijau Reload yogiwicaksonodm.pythonanywhere.com.
	Buka website di [https://yogiwicaksonodm.pythonanywhere.com]
	(https://yogiwicaksonodm.pythonanywhere.com) untuk mulai mendaftarkan siswa dan melakukan scan absensi wajah.

12. Penambahan fitur cukup cd ~/scanwajah --> git pull origin main
