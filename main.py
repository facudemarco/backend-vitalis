from fastapi import FastAPI
import uvicorn
from routers.contact import router as routerContact
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(root_path="/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://saludvitalis.org",
    "https://www.saludvitalis.org",
    "http://saludvitalis.org",
    "http://www.saludvitalis.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


IS_PROD = os.getenv("ENV") == "production"
print(IS_PROD)

@app.get("/")
async def root():
    return {"message": "API Vitalis by iWeb Technology. 2025 All rights reserved."}

app.include_router(routerContact)
