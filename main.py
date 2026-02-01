
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select, desc
from models import Deal, engine, create_db_and_tables
from scraper import DealScraper
import asyncio
import logging
from contextlib import asynccontextmanager

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifecycle manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    # Schedule a background scrape on startup if DB is empty? 
    # Or just let user trigger it. Let's trigger one for convenience.
    asyncio.create_task(run_scraper_background())
    yield

app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

async def run_scraper_background():
    logger.info("Starting background scrape...")
    scraper = DealScraper()
    await scraper.run()
    logger.info("Background scrape finished.")

@app.get("/")
async def read_root(request: Request, source: str = None):
    with Session(engine) as session:
        query = select(Deal).order_by(desc(Deal.timestamp))
        if source:
            query = query.where(Deal.source == source)
        deals = session.exec(query).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "deals": deals,
        "current_source": source
    })

@app.get("/api/refresh")
async def refresh_deals(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper_background)
    return {"message": "Scraping started in background"}
