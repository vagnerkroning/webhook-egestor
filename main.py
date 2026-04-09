from fastapi import FastAPI, Request
from supabase import create_client
import requests
import os
import time
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

    try:
        r = requests.post(url, json=payload, timeout=60)
    except Exception as e:
        log(f"❌ erro auth eGestor (conexão): {str(e)}")
        return None

    if r.status_code != 200:
        log(f"❌ erro auth eGestor: {r.status_code} | {r.text}")
        return None

    body = r.json()
    token = body.get("access_token")

    if not token:
        log("❌ access_token não veio na resposta")
        return None

    return token


def api_get(endpoint, tentativas=4):
    for tentativa in range(1, tentativas + 1):
        access_token = get_access_token()
        if not access_token:
            log(f"❌ sem access_token para {endpoint}")
            return None

        url = f"https://api.egestor.com.br/api/v1/{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)
        except Exception as e:
            log(f"❌ erro de conexão em {endpoint} | tentativa {tentativa}/{tentativas} | {str(e)}")
            if tentativa < tentativas:
                time.sleep(tentativa * 2)
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            espera = tentativa * 3
            log(f"⚠️ limite da API em {endpoint} | 429 | tentativa {tentativa}/{tentativas} | aguardando {espera}s")
            time.sleep(espera)
            continue

        if response.status_code in [404, 410]:
            log(f"⚠️ {endpoint} não encontrado | {response.status_code} | {response.text}")
            return None

        log(f"❌ erro ao buscar {endpoint} | {response.status_code} | {response.text}")
        return None

    log(f"❌ falha final ao buscar {endpoint} após {tentativas} tentativas")
    return None


def buscar_produto(codigo):
    return api_get(f"produtos/{codigo}")


def buscar_venda(codigo):
    return api_get(f"vendas/{codigo}")


def buscar_financeiro(codigo):
    """
    Tenta primeiro recebimentos, depois pagamentos.
    Retorna (tipo, detalhe)
    tipo = 'recebimento' ou 'pagamento'
    """
    receb = api_get(f"recebimentos/{codigo}")
    if receb:
        return "recebimento", receb

    pag = api_get(f"pagamentos/{codigo}")
    if pag:
        return "pagamento", pag

    return None, None


def buscar_plano_conta_nome(codigo):
    if not codigo:
        return ""

    detalhe = api_get(f"planoContas/{codigo}")
    if not detalhe:
        return ""

    return detalhe.get("nome", "")


def buscar_categoria_nome(cod_categoria):
    if cod_categoria is None or cod_categoria == "":
        return None

    resp = api_get(f"categorias/{cod_categoria}")
    if not resp:
        return None

    return resp.get("nome") or resp.get("descricao")


def salvar_pendencia(tipo, codigo, payload=None, motivo=""):
    try:
        supabase.table("eg_webhook_pendencias").insert({
            "tipo": tipo,
            "codigo": to_str(codigo),
            "motivo": motivo,
            "dados": payload or {},
            "created_at_manual": datetime.now().isoformat()
        }).execute()
        log(f"📝 pendência salva | tipo={tipo} | codigo={codigo} | motivo={motivo}")
    except Exception as e:
        log(f"❌ erro ao salvar pendência {tipo}/{codigo}: {str(e)}")


def salvar_produto_final(produto):
    categoria_id = to_str(produto.get("codCategoria"))
    categoria_nome = buscar_categoria_nome(categoria_id) if categoria_id else None

    registro = {
        "id_origem": to_str(produto.get("codigo")),
        "codigo": to_str(produto.get("codigo")),
        "nome": produto.get("descricao"),
        "categoria_id": categoria_id,
        "categoria_nome": categoria_nome if categoria_nome else "MERCADO",
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


def salvar_venda_final(venda):
    registro = {
        "id_origem": to_str(venda.get("codigo") or venda.get("id")),
        "data_venda": to_str(venda.get("dtVenda"))[:10] if venda.get("dtVenda") else None,
        "numero": to_str(venda.get("numDoc") or venda.get("numero")),
        "cliente_id": to_str(venda.get("codContato")),
        "cliente_nome": venda.get("nomeContato") or venda.get("cliente_nome") or "Cliente não identificado",
        "valor_total": to_float(venda.get("valorTotal") or venda.get("valor_total") or venda.get("valor")),
        "desconto": to_float(venda.get("desconto")),
        "acrescimo": to_float(venda.get("acrescimo")),
        "situacao": to_str(venda.get("situacao") or "OK"),
        "forma_pagamento": to_str(venda.get("nomeFormaPgto") or venda.get("forma_pagamento")),
    }

    supabase.table("eg_vendas").upsert(
        registro,
        on_conflict="id_origem"
    ).execute()

    log("✅ SALVO VENDA COMPLETA EM eg_vendas")


def salvar_itens_venda(venda):
    venda_id = to_str(venda.get("codigo") or venda.get("id"))
    itens = venda.get("produtos") or []

    if not itens:
        log("⚠️ venda sem itens")
        return

    for item in itens:
        produto_id = to_str(item.get("codProduto"))
        quantidade = to_float(item.get("quant") or item.get("quantidade"))
        valor_unitario = to_float(item.get("preco") or item.get("valorUnitario"))
        item_id = to_str(item.get("codigo") or f"{venda_id}_{produto_id}")

        categoria_id = None
        categoria_nome = None

        if produto_id:
            produto = buscar_produto(produto_id)
            if produto:
                categoria_id = to_str(produto.get("codCategoria"))
                categoria_nome = buscar_categoria_nome(categoria_id)

        registro = {
            "id_origem": item_id,
            "venda_id": venda_id,
            "produto_id": produto_id,
            "produto_nome": item.get("descricao"),
            "categoria_id": categoria_id,
            "categoria_nome": categoria_nome if categoria_nome else "MERCADO",
            "quantidade": quantidade,
            "valor_unitario": valor_unitario,
            "valor_total": quantidade * valor_unitario,
        }

        supabase.table("eg_venda_itens").upsert(
            registro,
            on_conflict="id_origem"
        ).execute()

    log("✅ SALVOS ITENS DA VENDA EM eg_venda_itens")


def salvar_financeiro_final(tipo, fin):
    codigo = to_str(fin.get("codigo") or fin.get("id"))
    data = to_str(
        fin.get("dtVenc")
        or fin.get("dtRec")
        or fin.get("dtPgto")
        or fin.get("data")
    )[:10]

    plano_conta_id = to_str(fin.get("codPlanoContas"))
    plano_conta_nome = buscar_plano_conta_nome(plano_conta_id)

    registro = {
        "id_origem": codigo,
        "data": data,
        "contato_id": to_str(fin.get("codContato")),
        "contato_nome": (
            fin.get("nomeContato")
            or fin.get("contatoNome")
            or "Não identificado"
        ),
        "plano_conta_id": plano_conta_id,
        "plano_conta_nome": plano_conta_nome,
        "valor": to_float(fin.get("valor")),
        "situacao": to_str(fin.get("situacao")),
        "origem": tipo,
    }

    if tipo == "recebimento":
        supabase.table("eg_recebimentos").upsert(
            registro,
            on_conflict="id_origem"
        ).execute()
        log("✅ SALVO FINANCEIRO EM eg_recebimentos")

    elif tipo == "pagamento":
        supabase.table("eg_pagamentos").upsert(
            registro,
            on_conflict="id_origem"
        ).execute()
        log("✅ SALVO FINANCEIRO EM eg_pagamentos")


def processar_produto_com_retry(codigo, payload=None):
    produto = buscar_produto(codigo)

    if produto:
        log(f"🔥 PRODUTO COMPLETO: {produto}")
        salvar_produto_final(produto)
        return True

    salvar_pendencia(
        tipo="produto",
        codigo=codigo,
        payload=payload,
        motivo="falha ao buscar produto completo"
    )
    return False


def processar_financeiro_com_retry(codigo, payload=None):
    tipo, fin = buscar_financeiro(codigo)

    if fin:
        log(f"🔥 FINANCEIRO COMPLETO ({tipo}): {fin}")
        salvar_financeiro_final(tipo, fin)
        return True

    salvar_pendencia(
        tipo="financeiro",
        codigo=codigo,
        payload=payload,
        motivo="não encontrado em recebimentos nem pagamentos"
    )
    return False


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
                ok = processar_produto_com_retry(codigo, payload=data)
                if not ok:
                    log("⚠️ não foi possível buscar produto completo")

        elif module == "vendas":
            supabase.table("eg_webhook_vendas").insert({
                "dados": data,
                "action": action
            }).execute()

            log("✅ SALVO NA TABELA eg_webhook_vendas")

            if codigo:
                venda = buscar_venda(codigo)

                if venda:
                    log(f"🔥 VENDA COMPLETA: {venda}")
                    salvar_venda_final(venda)
                    salvar_itens_venda(venda)
                else:
                    salvar_pendencia(
                        tipo="venda",
                        codigo=codigo,
                        payload=data,
                        motivo="falha ao buscar venda completa"
                    )
                    log("⚠️ não foi possível buscar venda completa")

        elif module in ["financeiro", "financeiros"]:
            supabase.table("eg_webhook_financeiros").insert({
                "dados": data,
                "action": action
            }).execute()
            log("✅ SALVO NA TABELA eg_webhook_financeiros")

            if codigo:
                ok = processar_financeiro_com_retry(codigo, payload=data)
                if not ok:
                    log("⚠️ não foi possível buscar financeiro completo")

        else:
            supabase.table("eg_webhook_logs").insert({
                "evento": module or "desconhecido",
                "dados": data
            }).execute()
            log("✅ SALVO NA TABELA eg_webhook_logs")

    except Exception as e:
        log(f"❌ erro no webhook: {str(e)}")
        salvar_pendencia(
            tipo=module or "desconhecido",
            codigo=codigo,
            payload=data,
            motivo=f"erro no webhook: {str(e)}"
        )

    return {"status": "ok"}
