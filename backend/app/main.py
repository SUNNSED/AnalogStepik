from fastapi import FastAPI
from app.api.routers import auth, submissions
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url="/openapi.json"
)

# Подключаем роутеры
app.include_router(auth.router)
app.include_router(submissions.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Analog Stepik API"}
