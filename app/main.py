from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import httpx
import os

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*.mosstuff.de"], allow_methods=["*"], allow_headers=["*"])

TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET")

api_token_answer = os.getenv("API_TOKEN_ANSWER")

api_token_black = os.getenv("API_TOKEN_BLACKLIST")

Base = declarative_base()
engine = create_engine("sqlite:///./questions.db")
SessionLocal = sessionmaker(bind=engine)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(String)
    name = Column(String, default="unknown")
    answer = Column(String, default="")


Base.metadata.create_all(bind=engine)


@app.post("/submit_question")
async def submit_question(question: str = Form(...), name: str = Form(...), turnstile_token: str = Form(...)):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET, "response": turnstile_token}
        )
        if not res.json().get("success"):
            raise HTTPException(status_code=400, detail="Invalid CAPTCHA")
    db = SessionLocal()
    db_question = Question(question=question, name=name)
    db.add(db_question)
    db.commit()
    db.refresh(db_question)
    return {"id": db_question.id}


@app.get("/questions")
def get_questions():
    db = SessionLocal()
    return db.query(Question).all()


class AnswerInput(BaseModel):
    id: int
    answer: str
    pw: str


@app.post("/set_answer")
def set_answer(answer_data: AnswerInput):
    if answer_data.pw == api_token_answer:
        db = SessionLocal()
        question = db.query(Question).filter(Question.id == answer_data.id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        question.answer = answer_data.answer
        db.commit()
        return {"status": "success"}
    else:
        raise HTTPException(status_code=403, detail="PW is wrong!")

class RemoveQuestionInput(BaseModel):
    id: int
    pw: str

@app.post("/delete_question")
def delete_question(question: RemoveQuestionInput):
    if question.pw == api_token_black:
        db = SessionLocal()
        question = db.query(Question).filter(Question.id == question.id).first()
        if question:
            db.delete(question)
            db.commit()
            return {"status": "success"}
        else:
            raise HTTPException(status_code=404, detail="Question not found!")
    else:
        raise HTTPException(status_code=403, detail="PW is wrong!")
