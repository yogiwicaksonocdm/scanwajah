import base64
from datetime import datetime, timezone, timedelta
import io
import json
import sqlite3
from flask import Flask, jsonify, redirect, render_template, request, url_for
import numpy as np
from PIL import Image


# Timezone default (WIB)
DEFAULT_TZ = "Asia/Jakarta"


def get_time_for_tz(tz_name):
  """Mendapatkan waktu sekarang berdasarkan nama timezone."""
  try:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(tz_name))
  except Exception:
    # Fallback: kembali ke UTC+7 (WIB)
    return datetime.now(timezone.utc) + timedelta(hours=7)


def get_jakarta_time():
  return get_time_for_tz(DEFAULT_TZ)


# Catatan: pastikan library face_recognition terpasang via pip
import face_recognition

app = Flask(__name__)
DB_NAME = "database.db"


def get_db():
  conn = sqlite3.connect(DB_NAME)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  with get_db() as conn:
    conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nisn TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                face_encoding TEXT NOT NULL
            )
        """)
    conn.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta'
            )
        """)
    # Tambah kolom location_id ke attendance jika belum ada
    try:
      conn.execute("ALTER TABLE attendance ADD COLUMN location_id INTEGER")
    except sqlite3.OperationalError:
      pass  # Kolom sudah ada

    conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                location_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id),
                FOREIGN KEY (location_id) REFERENCES locations (id)
            )
        """)

    # Insert lokasi default jika belum ada
    existing = conn.execute("SELECT COUNT(*) as cnt FROM locations").fetchone()["cnt"]
    if existing == 0:
      default_locations = [
        ("Gedung Utama", "Asia/Jakarta"),
        ("Gedung Barat", "Asia/Jakarta"),
        ("Gedung Timur", "Asia/Jakarta"),
      ]
      for loc_name, tz in default_locations:
        conn.execute(
          "INSERT OR IGNORE INTO locations (name, timezone) VALUES (?, ?)",
          (loc_name, tz),
        )

    conn.commit()


init_db()


def decode_image(base64_string):
  if "," in base64_string:
    base64_string = base64_string.split(",")[1]
  img_data = base64.b64decode(base64_string)
  img = Image.open(io.BytesIO(img_data)).convert("RGB")
  return np.array(img)


# --- ROUTE DASHBOARD (CRUD SISWA) ---
@app.route("/")
def dashboard():
  conn = get_db()
  students = conn.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
  locations = conn.execute("SELECT * FROM locations ORDER BY id ASC").fetchall()
  logs = conn.execute("""
        SELECT a.id, s.nisn, s.name, a.timestamp,
               COALESCE(l.name, '-') AS location_name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        LEFT JOIN locations l ON a.location_id = l.id
        ORDER BY a.timestamp DESC LIMIT 10
    """).fetchall()
  return render_template(
    "dashboard.html", students=students, logs=logs, locations=locations
  )


@app.route("/student/add", methods=["POST"])
def add_student():
  nisn = request.form.get("nisn")
  name = request.form.get("name")
  image_data = request.form.get("image_data")

  if not nisn or not name or not image_data:
    return (
        jsonify({"status": "error", "message": "Semua field wajib diisi!"}),
        400,
    )

  try:
    rgb_frame = decode_image(image_data)
    encodings = face_recognition.face_encodings(rgb_frame)

    if not encodings:
      return (
          jsonify({
              "status": "error",
              "message": "Wajah tidak terdeteksi. Silakan coba lagi.",
          }),
          400,
      )

    encoding_json = json.dumps(encodings[0].tolist())

    conn = get_db()
    conn.execute(
        "INSERT INTO students (nisn, name, face_encoding) VALUES (?, ?, ?)",
        (nisn, name, encoding_json),
    )
    conn.commit()
    return jsonify({"status": "success", "message": "Siswa berhasil disimpan!"})
  except sqlite3.IntegrityError:
    return (
        jsonify(
            {"status": "error", "message": "NISN sudah terdaftar di database."}
        ),
        400,
    )
  except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/student/delete/<int:id>", methods=["POST"])
def delete_student(id):
  conn = get_db()
  conn.execute("DELETE FROM attendance WHERE student_id = ?", (id,))
  conn.execute("DELETE FROM students WHERE id = ?", (id,))
  conn.commit()
  return redirect(url_for("dashboard"))


# --- ROUTE LOKASI ---
@app.route("/location/add", methods=["POST"])
def add_location():
  name = request.form.get("name")
  timezone_val = request.form.get("timezone", DEFAULT_TZ)
  if not name:
    return jsonify({"status": "error", "message": "Nama lokasi wajib diisi!"}), 400
  try:
    conn = get_db()
    conn.execute(
        "INSERT INTO locations (name, timezone) VALUES (?, ?)",
        (name, timezone_val),
    )
    conn.commit()
    return jsonify({"status": "success", "message": "Lokasi berhasil ditambahkan!"})
  except sqlite3.IntegrityError:
    return jsonify({"status": "error", "message": "Nama lokasi sudah ada."}), 400
  except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/location/delete/<int:id>", methods=["POST"])
def delete_location(id):
  conn = get_db()
  conn.execute("DELETE FROM attendance WHERE location_id = ?", (id,))
  conn.execute("DELETE FROM locations WHERE id = ?", (id,))
  conn.commit()
  return redirect(url_for("dashboard"))


@app.route("/api/locations")
def api_locations():
  conn = get_db()
  rows = conn.execute("SELECT id, name, timezone FROM locations ORDER BY id ASC").fetchall()
  return jsonify([dict(r) for r in rows])


# --- ROUTE SCAN ABSENSI ---
@app.route("/scan")
def scan_page():
  conn = get_db()
  locations = conn.execute("SELECT id, name FROM locations ORDER BY id ASC").fetchall()
  return render_template("scan.html", locations=locations)


@app.route("/api/verify-face", methods=["POST"])
def verify_face():
  data = request.get_json()
  image_data = data.get("image")
  location_id = data.get("location_id")

  if not image_data:
    return jsonify({"status": "error", "message": "Frame tidak valid"}), 400

  rgb_frame = decode_image(image_data)
  unknown_encodings = face_recognition.face_encodings(rgb_frame)

  if not unknown_encodings:
    return (
        jsonify({
            "status": "not_found",
            "message": "Wajah tidak terdeteksi di kamera",
        }),
        200,
    )

  target_encoding = unknown_encodings[0]

  conn = get_db()
  students = conn.execute("SELECT id, nisn, name, face_encoding FROM students").fetchall()

  # Tentukan timezone berdasarkan lokasi yang dipilih
  scan_tz = DEFAULT_TZ
  location_name = ""
  if location_id:
    loc = conn.execute("SELECT name, timezone FROM locations WHERE id = ?", (location_id,)).fetchone()
    if loc:
      scan_tz = loc["timezone"]
      location_name = loc["name"]

  for student in students:
    known_encoding = np.array(json.loads(student["face_encoding"]))
    # Toleransi default 0.5 (semakin kecil semakin ketat)
    match = face_recognition.compare_faces(
        [known_encoding], target_encoding, tolerance=0.5
    )

    if match[0]:
      # Cek apakah siswa sudah absen hari ini
      now_local = get_time_for_tz(scan_tz)
      today_str = now_local.strftime("%Y-%m-%d")
      already_absent = conn.execute(
          "SELECT id FROM attendance WHERE student_id = ? AND timestamp LIKE ?",
          (student["id"], today_str + "%"),
      ).fetchone()
      if already_absent:
        return jsonify({
            "status": "already_absent",
            "message": f'{student["name"]} sudah absen hari ini.',
            "nisn": student["nisn"],
            "name": student["name"],
        }), 200

      # Rekam absensi dengan waktu lokal sesuai lokasi
      now_str = now_local.strftime("%Y-%m-%d %H:%M:%S")
      conn.execute(
          "INSERT INTO attendance (student_id, location_id, timestamp) VALUES (?, ?, ?)",
          (student["id"], location_id, now_str),
      )
      conn.commit()
      return jsonify({
          "status": "success",
          "nisn": student["nisn"],
          "name": student["name"],
          "time": now_str,
          "location": location_name or "-",
      })

  return (
      jsonify(
          {"status": "unknown", "message": "Wajah tidak dikenali dalam sistem"}
      ),
      200,
  )


if __name__ == "__main__":
  app.run(debug=True)
