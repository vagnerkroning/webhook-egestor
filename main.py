from fastapi import FastAPI, Request
from supabase import create_client
from datetime import datetime
import os

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL não definida")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY não definida")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/webhook-egestor")
async def webhook(request: Request):
    data = await request.json()

    log(f"📩 RECEBIDO: {data}")

    module = data.get("module", "desconhecido")
    action = data.get("action", "desconhecido")

    try:
        # 1) salva log bruto geral
        supabase.table("eg_webhook_logs").insert({
            "evento": module,
            "dados": data
        }).execute()

        tabela_destino = None

        # 2) salva bruto por módulo
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
            log(f"✅ SALVO NA TABELA {tabela_destino}")
        else:
            log(f"⚠️ módulo sem tabela específica: {module}")

        # 3) grava na tabela final quando for produto
        if module == "produtos":
            produto = data.get("data", {})

            if not produto:
                log("⚠️ webhook de produto sem campo data")
            else:
                produto_id = produto.get("id") or produto.get("codigo")
                nome = produto.get("nome") or produto.get("descricao")
                codigo = produto.get("codigo")
                preco = (
                    produto.get("preco_venda")
                    or produto.get("precoVenda")
                    or produto.get("valor_venda")
                    or produto.get("preco")
                    or 0
                )
                custo = (
                    produto.get("preco_custo")
                    or produto.get("precoCusto")
                    or produto.get("custo")
                    or 0
                )
                categoria = (
                    produto.get("categoria")
                    or produto.get("categoria_nome")
                    or produto.get("nomeCategoria")
                    or ""
                )

                if produto_id:
                    supabase.table("eg_produtos").upsert({
                        "id": str(produto_id),
                        "nome": nome,
                        "codigo": str(codigo) if codigo is not None else None,
                        "preco": preco,
                        "custo": custo,
                        "categoria": categoria,
                        "updated_at": datetime.utcnow().isoformat()
                    }).execute()

                    log("🔥 PRODUTO ATUALIZADO NA TABELA FINAL eg_produtos")
                else:
                    log("⚠️ produto sem id/codigo, não foi possível gravar em eg_produtos")

        log("✅ SALVO NO SUPABASE")
        return {"status": "recebido"}

    except Exception as e:
        log(f"❌ ERRO AO SALVAR: {str(e)}")
        return {"status": "erro", "detalhe": str(e)}
