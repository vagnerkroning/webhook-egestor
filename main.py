from fastapi import FastAPI, Request
from supabase import create_client
import requests
import os
from datetime import datetime

print("🔥 main.py carregou", flush=True)

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EGESTOR_TOKEN = os.getenv("EGESTOR_TOKEN")  # personal token

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL não definida")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY não definida")
if not EGESTOR_TOKEN:
    raise ValueError("EGESTOR_TOKEN não definido")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def to_float(valor, padrao=0.0):
    try:
        if valor is None or valor == "":
            return padrao
        return float(valor)
    except Exception:
        return padrao


def to_str(valor, padrao=""):
    if valor is None:
        return padrao
    return str(valor)


def get_access_token():
    url = "https://api.egestor.com.br/api/oauth/access_token"

    payload = {
        "grant_type": "personal",
        "personal_token": EGESTOR_TOKEN
    }

    r = requests.post(url, json=payload, timeout=60)

    if r.status_code != 200:
        log(f"❌ erro auth eGestor: {r.status_code} | {r.text}")
        return None

    body = r.json()
    token = body.get("access_token")

    if not token:
        log("❌ access_token não veio na resposta")
        return None

    return token


def buscar_produto(codigo):
    access_token = get_access_token()
    if not access_token:
        return None

    url = f"https://api.egestor.com.br/api/v1/produtos/{codigo}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers, timeout=60)

    if response.status_code == 200:
        return response.json()

    log(f"❌ erro ao buscar produto {response.status_code} | {response.text}")
    return None


def salvar_produto_final(produto):
    registro = {
        "id_origem": to_str(produto.get("codigo")),
        "codigo": to_str(produto.get("codigo")),
        "nome": produto.get("descricao"),
        "categoria_id": to_str(produto.get("codCategoria")),
        "categoria_nome": None,
        "unidade": produto.get("unidadeTributada"),
        "valor_venda": to_float(produto.get("precoVenda")),
        "custo": to_float(produto.get("precoCusto")),
        "estoque": to_float(produto.get("estoque")),
        "situacao": "OK",
    }

    supabase.table("eg_produtos").upsert(
        registro,
        on_conflict="id_origem"
    ).execute()

    log("✅ SALVO PRODUTO COMPLETO EM eg_produtos")


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/webhook-egestor")
async def webhook(request: Request):
    print("🔥 entrou no webhook", flush=True)
    data = await request.json()

    log(f"📩 RECEBIDO: {data}")

    module = data.get("module")
    action = data.get("action")
    codigo = data.get("codigo")

    try:
        if module == "produtos":
            supabase.table("eg_webhook_produtos").insert({
                "dados": data,
                "action": action
            }).execute()

            log("✅ SALVO NA TABELA eg_webhook_produtos")

            if codigo:
                produto = buscar_produto(codigo)

                if produto:
                    log(f"🔥 PRODUTO COMPLETO: {produto}")
                    salvar_produto_final(produto)
                else:
                    log("⚠️ não foi possível buscar produto completo")

        elif module == "vendas":
            supabase.table("eg_webhook_vendas").insert({
                "dados": data,
                "action": action
            }).execute()
            log("✅ SALVO NA TABELA eg_webhook_vendas")

        elif module in ["financeiro", "financeiros"]:
            supabase.table("eg_webhook_financeiros").insert({
                "dados": data,
                "action": action
            }).execute()
            log("✅ SALVO NA TABELA eg_webhook_financeiros")

        else:
            supabase.table("eg_webhook_logs").insert({
                "evento": module or "desconhecido",
                "dados": data
            }).execute()
            log("✅ SALVO NA TABELA eg_webhook_logs")

    except Exception as e:
        log(f"❌ erro no webhook: {str(e)}")

    return {"status": "ok"}
