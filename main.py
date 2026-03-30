from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/webhook-egestor")
async def webhook(request: Request):
    data = await request.json()
    print("📩 RECEBIDO:", data)
    return {"status": "recebido"}
