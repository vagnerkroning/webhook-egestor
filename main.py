from fastapi import FastAPI, Request
from supabase import create_client
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/webhook-egestor")
async def webhook(request: Request):
    data = await request.json()

    print("📩 RECEBIDO:", data)

    try:
        supabase.table("eg_webhook_logs").insert({
            "evento": data.get("tipo", "desconhecido"),
            "dados": data
        }).execute()

        print("✅ SALVO NO SUPABASE")

    except Exception as e:
        print("❌ ERRO AO SALVAR:", str(e))

    return {"status": "recebido"}
