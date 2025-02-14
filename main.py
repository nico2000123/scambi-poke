from fastapi import FastAPI, HTTPException, Depends, Cookie, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from pydantic import BaseModel

app = FastAPI()

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./cardswap.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modello per utenti
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    password = Column(String)

# Modello per le carte
class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", foreign_keys=[owner_id])

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Funzione per ottenere la sessione del database
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schema per il login
class LoginRequest(BaseModel):
    user_name: str
    password: str

# Schema per registrare un utente
class RegisterRequest(BaseModel):
    user_name: str
    password: str

# Schema per aggiungere una carta
class CardRequest(BaseModel):
    name: str
    user_name: str

# Funzione per ottenere o creare un utente
def get_or_create_user(db: Session, name: str, password: str):
    user = db.query(User).filter(User.name == name).first()
    if not user:
        user = User(name=name, password=password)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.password != password:
        raise HTTPException(status_code=401, detail="Incorrect password")
    return user

@app.get("/", response_class=HTMLResponse)
def get_index():
    return HTMLResponse(content=open("static/index.html").read())

@app.post("/login/")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = get_or_create_user(db, data.user_name, data.password)
    response = JSONResponse(content={"message": f"Logged in as {data.user_name}"})
    response.set_cookie(key="user_name", value=data.user_name)
    return response

@app.post("/register/")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.name == data.user_name).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    new_user = User(name=data.user_name, password=data.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}

@app.post("/cards/")
def add_card(data: CardRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.user_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db_card = Card(name=data.name, owner_id=user.id)
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    
    return {"message": f"Card '{data.name}' added for user '{data.user_name}'"}

@app.get("/cards/{user_name}")
def get_user_cards(user_name: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == user_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    cards = db.query(Card).filter(Card.owner_id == user.id).all()
    return {"user": user_name, "cards": [card.name for card in cards]}

@app.delete("/cards/")
def delete_card(data: CardRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == data.user_name).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    card = db.query(Card).filter(Card.name == data.name, Card.owner_id == user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    db.delete(card)
    db.commit()
    
    return {"message": f"Card '{data.name}' removed for user '{data.user_name}'"}
