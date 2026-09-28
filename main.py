from fastapi import FastAPI
from routers import ur

app = FastAPI()

app.include_router(ur.router)
