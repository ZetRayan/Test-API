
from fastapi import FastAPI

app = FastAPI(title="Test API")

@app.get("/")
def ping():
    return {"status": "Docker работает"}
