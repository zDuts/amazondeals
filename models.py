
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Session

class Deal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str  # mydealz, pepper, dealabs
    title: str
    price: Optional[str] = None
    original_price: Optional[str] = None
    image_url: Optional[str] = None
    deal_url: str
    temperature: Optional[str] = None
    merchant_id: Optional[str] = None
    currency: str = "€"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Composite unique constraint could be useful, but for now we'll rely on the deal_url for uniqueness checks during scrape

DATABASE_URL = "sqlite:///./deals.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
