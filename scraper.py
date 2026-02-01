
import asyncio
import logging
from playwright.async_api import async_playwright, Page
from models import Deal, engine
from sqlmodel import Session, select
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEARCH_URLS = {
    "mydealz": "https://www.mydealz.de/search/deals?merchant-id=3",
    "pepper": "https://nl.pepper.com/search/aanbiedingen?merchant-id=1538",
    "dealabs": "https://www.dealabs.com/search/bons-plans?merchant-id=36"
}

class DealScraper:
    def __init__(self):
        pass

    async def scrape_site(self, context, source: str, url: str):
        logger.info(f"Scraping {source} from {url}")
        page = await context.new_page()
        try:
            await page.goto(url, timeout=90000, wait_until="domcontentloaded")
            
            # Wait for the deals list to appear (increased timeout for slower VPS/Cloudflare challenges)
            await page.wait_for_selector(".threadGrid", timeout=60000)
            
            # Scroll down a bit to ensure lazy loading triggers if needed (usually 1st page is enough)
            await page.evaluate("window.scrollTo(0, 1000)")
            await asyncio.sleep(5) # Increased wait time for stability

            deals_data = await self.parse_deals(page, source)
            self.save_deals(deals_data)
            logger.info(f"Successfully scraped {len(deals_data)} deals from {source}")
            
        except Exception as e:
            logger.error(f"Error scraping {source}: {e}")
            # Take a screenshot for debugging if running locally or accessible
            # await page.screenshot(path=f"error_{source}.png")
        finally:
            await page.close()

    async def parse_deals(self, page: Page, source: str):
        deals = []
        # Select all deal cards (they usually have class 'thread')
        deal_elements = await page.query_selector_all("article.thread")
        
        for el in deal_elements:
            try:
                # Title
                title_el = await el.query_selector(".thread-title a")
                if not title_el:
                    continue
                title = await title_el.inner_text()
                link = await title_el.get_attribute("href")
                
                # Temperature (hotness)
                temp_el = await el.query_selector(".vote-temp")
                temperature = await temp_el.inner_text() if temp_el else "0°"
                
                # Price
                price_el = await el.query_selector(".thread-price")
                price = await price_el.inner_text() if price_el else None
                
                # Original Price
                # Sometimes in strikethrough text next to price
                original_price_el = await el.query_selector(".thread-price--old")
                original_price = await original_price_el.inner_text() if original_price_el else None

                # Image
                img_el = await el.query_selector("img.thread-image")
                image_url = await img_el.get_attribute("src") if img_el else None
                if image_url and "data:image" in image_url:
                     # Try to get data-src if it's lazy loaded
                     image_url = await img_el.get_attribute("data-src")

                # Merchant (should be Amazon, but good to verify or store)
                # On these search pages, it's implied by the query, but we can check the merchant link if needed
                
                # Construct Deal object
                deal = Deal(
                    source=source,
                    title=title.strip(),
                    price=price.strip() if price else None,
                    original_price=original_price.strip() if original_price else None,
                    image_url=image_url,
                    deal_url=link,
                    temperature=temperature.strip(),
                    currency="€" # All 3 sites use Euro
                )
                deals.append(deal)
                
            except Exception as e:
                logger.error(f"Error parsing deal element: {e}")
                continue
                
        return deals

    def save_deals(self, deals: list[Deal]):
        with Session(engine) as session:
            for deal in deals:
                # Check duplication by deal_url
                existing = session.exec(select(Deal).where(Deal.deal_url == deal.deal_url)).first()
                if existing:
                    # Update price/temp if changed
                    existing.price = deal.price
                    existing.temperature = deal.temperature
                    existing.timestamp = datetime.utcnow()
                    session.add(existing)
                else:
                    session.add(deal)
            session.commit()

    async def run(self):
        async with async_playwright() as p:
            # Determine if we run headless (default true)
            # Add args to reduce detection
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            
            # Use a more realistic context setup
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="de-DE"
            )
            
            tasks = []
            for source, url in SEARCH_URLS.items():
                tasks.append(self.scrape_site(context, source, url))
            
            await asyncio.gather(*tasks)
            await browser.close()

if __name__ == "__main__":
    scraper = DealScraper()
    asyncio.run(scraper.run())
