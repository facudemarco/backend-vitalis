from fastapi import FastAPI
import uvicorn
from routers.contact import router as routerContact
from routers.login import router as routerLogin
from routers.users import router as routerUsers
from routers.companies import router as routerCompanies
from routers.patients import router as routerPatients
from routers.medical_records import router as routerMedicalRecords
from routers.studies import router as routerStudies
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(root_path="/MdpuF8KsXiRArNlHtl6pXO2XyLSJMTQ8_Vitalis/api")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "https://saludvitalis.org",
    "https://www.saludvitalis.org",
    "https://vitalis-website.vercel.app",
    "http://saludvitalis.org",
    "http://www.saludvitalis.org",
    "http://127.0.0.1:8000",
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
app.include_router(routerLogin)
app.include_router(routerUsers)
app.include_router(routerCompanies)
app.include_router(routerPatients)
app.include_router(routerMedicalRecords)
app.include_router(routerStudies)
