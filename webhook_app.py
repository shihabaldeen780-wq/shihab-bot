import os
from flask import Flask
from bot import init_db, SERVICE_ID if "SERVICE_ID" in dir() else "29418"

try:
    from bot import SERVICE_ID, COMMIT_HASH
    COMMIT = COMMIT_HASH
except:
    SERVICE_ID = os.getenv("SERVICE_ID","29418")
    COMMIT = os.getenv("COMMIT_HASH","21606b7")

app = Flask(__name__)
try:
    init_db()
except: pass

@app.route("/")
def home():
    return f"<h1>Shakhoof711 - @Gh_317_bot - Service #{SERVICE_ID}</h1><p>commit {COMMIT} - تطوير واجهة شهاب ومركز المحتوى - كل مميزات وعد + شاخوف</p><p style=\"color:green\">service: {SERVICE_ID} started<br>بوت شهاب جاهز للعمل - @Gh_317_bot<br>Application started</p>"

@app.route("/health")
def health():
    return {"service": SERVICE_ID, "bot": "Gh_317_bot", "commit": COMMIT, "status": "ready"}

if __name__ == "__main__":
    port = int(os.getenv("PORT","8101"))
    print(f"service: {SERVICE_ID} started")
    print("بوت شهاب - Gh_317_bot جاهز")
    app.run(host="::", port=port)
