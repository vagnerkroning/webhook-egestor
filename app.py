from flask import Flask, request, jsonify
import os
import requests
from datetime import datetime

app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
EGESTOR_WEBHOOK_TOKEN = os.getenv("EGESTOR_WEBHOOK_TOKEN", "").strip()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

@app.route("/", methods=["GET"])
def home():
    return {"status": "ok"}

@app.route("/webhook-egestor", methods=["POST"])
def webhook():
    token = request.headers.get("X-Token", "")

    if token != EGESTOR_WEBHOOK_TOKEN:
        log("Token inválido")
        return {"error": "unauthorized"}, 401

    data = request.json
    log(f"Recebido: {data}")

    registro = {
        "evento": "webhook",
        "payload": data,
        "recebido_em": datetime.utcnow().isoformat()
    }

    requests.post(
        f"{SUPABASE_URL}/rest/v1/eg_webhook_logs",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json"
        },
        json=registro
    )

    return {"ok": True}