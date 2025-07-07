from flask import Flask, request, Response, render_template_string, abort
import threading, time, os

app = Flask(__name__)

UPLOAD_TOKEN = os.getenv("UPLOAD_TOKEN", "changeme")  # ESP → /upload
FLAG_TOKEN   = os.getenv("FLAG_TOKEN",   "changeme")  # dashboard & ESP → /flag /request

latest_lock  = threading.Lock()
latest_jpeg  = b""
need_frame   = False

# ───────── HTML dashboard ─────────
HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BUBT VTS+ Snapshot Viewer</title>
  <style>
    body {
      background: #111;
      color: #eee;
      text-align: center;
      font-family: sans-serif;
      margin: 0;
      padding: 0;
    }
    button {
      padding: 0.6em 1.4em;
      font-size: 1.1em;
      margin-top: 10px;
      background: #222;
      color: #fff;
      border: 1px solid #444;
      cursor: pointer;
    }
    img {
      max-width: 96%;
      border: 2px solid #666;
      margin-top: 12px;
    }
    .credits {
      font-size: 14px;
      color: #ccc;
      margin-top: 20px;
    }
  </style>
  <script>
    const token = 'changeme'; // replace this dynamically if templated

    function ask() {
      fetch('/request?token=' + token)
        .then(() => {
          document.getElementById('img').src = '/latest?' + Date.now();
        });
    }

    // If you want polling instead of manual button:
    // setInterval(() => ask(), 100);
  </script>
</head>
<body>
  <h2>BUBT VTS+ Snapshot Dashboard</h2>
  <button onclick="ask()">📸 Update Frame</button><br>
  <img id="img" src="/latest"><br>

  <div class="credits">
    🛠 Developed by<br>
    👨‍💻 Rakib Hasan  👨‍💻 Sahadat Sani  👨‍🔬 A B M Shawkat Ali
  </div>
</body>
</html>
"""

# ESP → POST /upload  (JPEG)
@app.route("/upload", methods=["POST"])
def upload():
    if request.args.get("token") != UPLOAD_TOKEN:
        abort(401, "bad token")
    data = request.get_data()
    if data[:2] != b'\xff\xd8':
        abort(400, "no jpeg")
    global latest_jpeg, need_frame
    with latest_lock:
        latest_jpeg = data
        need_frame  = False          # clear flag
    return "OK", 200

# ESP → GET /flag  (returns "1" or "0")
@app.route("/flag")
def flag():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    return ("1" if need_frame else "0"), 200

# Dashboard → /request  (sets flag)
@app.route("/request")
def request_frame():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    global need_frame
    need_frame = True
    return "OK", 200

# Browser fetches latest still
@app.route("/latest")
def latest():
    if not latest_jpeg:
        abort(404, "no image yet")
    return Response(latest_jpeg, mimetype="image/jpeg")

# Viewer page
@app.route("/")
def view():
    return render_template_string(HTML, flag=FLAG_TOKEN)
