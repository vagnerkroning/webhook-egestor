from fastapi import FastAPI, Request
from supabase import create_client
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL não definida")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY não definida")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/webhook-egestor")
async def webhook(request: Request):
    data = await request.json()

    print("📩 RECEBIDO:", data)

    module = data.get("module", "desconhecido")
    action = data.get("action", "desconhecido")

    try:
        # 1) log bruto geral
        supabase.table("eg_webhook_logs").insert({
            "evento": module,
            "dados": data
        }).execute()

        # 2) separação por módulo
        tabela_destino = None

        if module == "produtos":
            tabela_destino = "eg_webhook_produtos"
        elif module == "vendas":
            tabela_destino = "eg_webhook_vendas"
        elif module == "financeiros":
            tabela_destino = "eg_webhook_financeiros"
        elif module == "contatos":
            tabela_destino = "eg_webhook_contatos"

        if tabela_destino:
            supabase.table(tabela_destino).insert({
                "action": action,
                "dados": data
            }).execute()
            print(f"✅ SALVO NA TABELA {tabela_destino}")
        else:
            print(f"⚠️ módulo sem tabela específica: {module}")

        print("✅ SALVO NO SUPABASE")

    except Exception as e:
        print("❌ ERRO AO SALVAR:", str(e))

    return {"status": "recebido"}
