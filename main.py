from fastapi import FastAPI, Request
from supabase import create_client
import requests
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EGESTOR_TOKEN = os.getenv("EGESTOR_TOKEN")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def buscar_produto(codigo):
    url = f"https://api.egestor.com.br/api/v1/produtos/{codigo}"

    headers = {
        "Authorization": f"Bearer {EGESTOR_TOKEN}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print("❌ erro ao buscar produto", response.text)
        return None


@app.post("/webhook-egestor")
async def webhook(request: Request):
    data = await request.json()

    print("📩 RECEBIDO:", data)

    # ✅ AGORA CORRETO
    supabase.table("eg_webhook_produtos").insert({
        "dados": data,
        "action": data.get("action")
    }).execute()

    if data.get("module") == "produtos":
        codigo = data.get("codigo")

        if codigo:
            produto = buscar_produto(codigo)

            if produto:
                print("🔥 PRODUTO COMPLETO:", produto)

                supabase.table("eg_produtos").upsert(produto).execute()

                print("✅ SALVO PRODUTO COMPLETO")

    return {"status": "ok"}
