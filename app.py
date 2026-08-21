import base64
from datetime import datetime
import io
import json
import sqlite3
from flask import Flask, jsonify, redirect, render_template, request, url_for
import numpy as np
from PIL import Image

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
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id)
            )
        """)


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
  logs = conn.execute("""
        SELECT a.id, s.nisn, s.name, a.timestamp 
        FROM attendance a 
        JOIN students s ON a.student_id = s.id 
        ORDER BY a.timestamp DESC LIMIT 10
    """).fetchall()
  return render_template("dashboard.html", students=students, logs=logs)


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


# --- ROUTE SCAN ABSENSI ---
@app.route("/scan")
def scan_page():
  return render_template("scan.html")


@app.route("/api/verify-face", methods=["POST"])
def verify_face():
  data = request.get_json()
  image_data = data.get("image")

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

  for student in students:
    known_encoding = np.array(json.loads(student["face_encoding"]))
    # Toleransi default 0.6 (semakin kecil semakin ketat)
    match = face_recognition.compare_faces(
        [known_encoding], target_encoding, tolerance=0.5
    )

    if match[0]:
      # Rekam absensi ke tabel
      conn.execute(
          "INSERT INTO attendance (student_id) VALUES (?)", (student["id"],)
      )
      conn.commit()
      return jsonify({
          "status": "success",
          "nisn": student["nisn"],
          "name": student["name"],
          "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      })

  return (
      jsonify(
          {"status": "unknown", "message": "Wajah tidak dikenali dalam sistem"}
      ),
      200,
  )


if __name__ == "__main__":
  app.run(debug=True)