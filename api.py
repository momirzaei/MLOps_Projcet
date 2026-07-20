from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from sql_agent import initialize_groq_sql_agent
from dotenv import load_dotenv

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    status: str

app = FastAPI(
    title="Retail SQL Agent API",
    description="API for natural language querying of the Medallion Gold Layer",
    version="1.0.0"
)

sql_agent = None

DATABASE_URI = "sqlite:///retail_gold.db"

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing! Please check your .env file.")

@app.on_event("startup")
async def startup_event():
    global sql_agent
    print(" Initializing the Groq SQL Agent...")
    sql_agent = initialize_groq_sql_agent(DATABASE_URI, GROQ_API_KEY, tracker=None)
    print("Agent is ready to serve requests!")

#API Endpoints
@app.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    if not sql_agent:
        raise HTTPException(status_code=500, detail="Agent is not initialized.")
    
    try:
        response = sql_agent.invoke({"input": request.question})
        
        final_answer = response.get('output', 'No answer generated.')
        return QueryResponse(answer=final_answer, status="success")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "active", "agent_loaded": sql_agent is not None}