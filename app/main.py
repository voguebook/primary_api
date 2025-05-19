from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router

from dotenv import load_dotenv


app = FastAPI(title="Fashion catalog API", version="1.0")

app = FastAPI(default_response_class=JSONResponse)

is_running = False


app.include_router(v1_router, prefix="/api/v1")  # For editing feeds


load_dotenv()
