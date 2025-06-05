import json
import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AirbnbMonitorSelenium:
    def __init__(self):
        # Email configuration
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # File to store previously seen listings
        self.data_file = 'seen_listings.json'
        
        # Your Airbnb search URL
        self.search_url = os.getenv('AIRBNB_SEARCH_URL')
        
        # Load previously seen listings
        self.seen_listings = self.load_seen_listings()
        
        # WebDriver setup
        self.driver = None
    
    def setup_driver(self):
        """Set up Chrome WebDriver with options to avoid detection"""
        try:
            chrome_options = Options()
            
            # Add options to make the browser less detectable
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # For testing, we'll run in headless mode (no visible browser)
            # Comment out the next line if you want to see the browser
            chrome_options.add_argument("--headless")
            
            # Automatically download and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove automation indicators
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {e}")
            return False
    
    def load_seen_listings(self):
        """Load previously seen listings from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    return set(json.load(f))
            return set()
        except Exception as e:
            logger.error(f"Error loading seen listings: {e}")
            return set()
    
    def save_seen_listings(self):
        """Save seen listings to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(list(self.seen_listings), f)
        except Exception as e:
            logger.error(f"Error saving seen listings: {e}")
    
    def get_listings(self):
        """Fetch current listings using Selenium"""
        if not self.driver:
            if not self.setup_driver():
                return []
        
        try:
            logger.info("Loading Airbnb search page...")
            self.driver.get(self.search_url)
            
            # Wait a bit for the page to load
            time.sleep(5)
            
            # Wait for listings to load
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='card-container']"))
                )
            except:
                logger.warning("Timeout waiting for listings to load")
            
            # Try multiple selectors to find listing cards
            listing_selectors = [
                "[data-testid='card-container']",
                "[data-testid='listing-card-title']",
                "div[itemProp='itemListElement']",
                "a[href*='/rooms/']",
                "div[data-testid='card-container'] a"
            ]
            
            current_listings = []
            
            for selector in listing_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        try:
                            # Try to extract listing URL and ID
                            link_element = element if element.tag_name == 'a' else element.find_element(By.CSS_SELECTOR, "a[href*='/rooms/']")
                            listing_url = link_element.get_attribute('href')
                            
                            if listing_url and '/rooms/' in listing_url:
                                # Extract listing ID from URL
                                listing_id = listing_url.split('/rooms/')[-1].split('?')[0].split('/')[0]
                                
                                # Try to get listing title
                                try:
                                    title_element = element.find_element(By.CSS_SELECTOR, "[data-testid='listing-card-title']")
                                    title = title_element.text.strip()
                                except:
                                    try:
                                        title_element = element.find_element(By.CSS_SELECTOR, "div[data-testid='listing-card-title']")
                                        title = title_element.text.strip()
                                    except:
                                        title = f"Airbnb Listing {listing_id}"
                                
                                # Try to get price
                                price = None
                                price_selectors = [
                                    "[data-testid='price-availability']",
                                    "span._1y74zjx",
                                    "span[data-testid='price']",
                                    "div._1jo4hgw span",
                                    "span",
                                    "div[data-testid='price-availability'] span"
                                ]
                                
                                for price_selector in price_selectors:
                                    try:
                                        price_elements = element.find_elements(By.CSS_SELECTOR, price_selector)
                                        for price_element in price_elements:
                                            price_text = price_element.text.strip()
                                            if price_text and any(currency in price_text for currency in ['kr', '$', '€', '£', 'DKK']):
                                                price = price_text
                                                break
                                        if price:
                                            break
                                    except:
                                        continue
                                
                                # Try to get image
                                image_url = None
                                image_selectors = [
                                    "img[data-testid='listing-card-image']",
                                    "img[data-original]",
                                    "img[src*='airbnb']",
                                    "picture img",
                                    "img"
                                ]
                                
                                for img_selector in image_selectors:
                                    try:
                                        img_element = element.find_element(By.CSS_SELECTOR, img_selector)
                                        src = img_element.get_attribute('src') or img_element.get_attribute('data-original')
                                        if src and ('airbnb' in src or 'https://' in src):
                                            image_url = src
                                            break
                                    except:
                                        continue
                                
                                if listing_id and len(listing_id) > 3:  # Valid listing ID
                                    current_listings.append({
                                        'id': listing_id,
                                        'name': title or f"Listing {listing_id}",
                                        'url': listing_url,
                                        'price': price,
                                        'image_url': image_url
                                    })
                        
                        except Exception as e:
                            continue  # Skip this element if we can't extract data
                    
                    if current_listings:
                        break  # If we found listings with this selector, stop trying others
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            # Remove duplicates based on ID
            seen_ids = set()
            unique_listings = []
            for listing in current_listings:
                if listing['id'] not in seen_ids:
                    seen_ids.add(listing['id'])
                    unique_listings.append(listing)
            
            logger.info(f"Found {len(unique_listings)} unique listings")
            
            return unique_listings
            
        except Exception as e:
            logger.error(f"Error fetching listings with Selenium: {e}")
            return []
    
    def send_notification(self, new_listings):
        """Send email notification for new listings"""
        if not new_listings:
            return
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Subject'] = f"🏠 {len(new_listings)} New Airbnb Listing(s) Found!"
            msg.set_charset('utf-8')
            
            # Create email body
            body = f"""
            <h2>New Airbnb Listings Found!</h2>
            <p>Found {len(new_listings)} new listing(s) matching your search criteria:</p>
            <br>
            """
            
            for listing in new_listings:
                # Clean the listing name to avoid encoding issues
                clean_name = listing['name'].encode('ascii', 'ignore').decode('ascii') if listing['name'] else f"Listing {listing['id']}"
                price_display = listing.get('price', 'Price not available')
                image_url = listing.get('image_url', '')
                
                # Create the listing HTML with image and price
                listing_html = f"""
                <div style="border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; background-color: #fafafa;">
                    <div style="display: flex; align-items: flex-start; gap: 15px;">
                """
                
                # Add image if available
                if image_url:
                    listing_html += f"""
                        <div style="flex-shrink: 0;">
                            <img src="{image_url}" alt="Property image" style="width: 120px; height: 90px; object-fit: cover; border-radius: 6px; border: 1px solid #ddd;">
                        </div>
                    """
                
                listing_html += f"""
                        <div style="flex-grow: 1;">
                            <h3 style="margin: 0 0 8px 0; color: #222; font-size: 16px;">{clean_name}</h3>
                            <p style="margin: 5px 0; color: #666; font-size: 14px;"><strong>Price:</strong> <span style="color: #ff5a5f; font-weight: bold;">{price_display}</span></p>
                            <p style="margin: 5px 0; color: #666; font-size: 14px;"><strong>ID:</strong> {listing['id']}</p>
                            <p style="margin: 10px 0 0 0;"><a href="{listing['url']}" style="color: #ff5a5f; text-decoration: none; font-weight: bold; background-color: #fff; padding: 8px 16px; border: 2px solid #ff5a5f; border-radius: 4px; display: inline-block;">📍 View Listing</a></p>
                        </div>
                    </div>
                </div>
                """
                
                body += listing_html
            
            body += f"""
            <br>
            <p style="color: #666; font-size: 12px;">
                Alert sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
            """
            
            # Attach with explicit UTF-8 encoding
            html_part = MIMEText(body.encode('utf-8'), 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            
            # Use send_message for better encoding handling
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email notification sent for {len(new_listings)} new listings")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    def check_for_new_listings(self):
        """Main function to check for new listings"""
        logger.info("Checking for new listings...")
        
        current_listings = self.get_listings()
        if not current_listings:
            logger.warning("No listings found - this might indicate an issue")
            return
        
        new_listings = []
        current_ids = set()
        
        for listing in current_listings:
            listing_id = listing['id']
            current_ids.add(listing_id)
            
            if listing_id not in self.seen_listings:
                new_listings.append(listing)
                logger.info(f"New listing found: {listing['name']} (ID: {listing_id})")
        
        # Update seen listings
        self.seen_listings.update(current_ids)
        self.save_seen_listings()
        
        # Send notification if new listings found
        if new_listings:
            self.send_notification(new_listings)
            logger.info(f"Found {len(new_listings)} new listings")
        else:
            logger.info("No new listings found")
    
    def run_once(self):
        """Run the monitor once"""
        try:
            self.check_for_new_listings()
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")
        finally:
            if self.driver:
                self.driver.quit()
    
    def run_continuous(self, interval_minutes=30):
        """Run the monitor continuously"""
        logger.info(f"Starting continuous monitoring (checking every {interval_minutes} minutes)")
        
        try:
            while True:
                try:
                    self.check_for_new_listings()
                    logger.info(f"Sleeping for {interval_minutes} minutes...")
                    time.sleep(interval_minutes * 60)
                except KeyboardInterrupt:
                    logger.info("Monitoring stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying
        finally:
            if self.driver:
                self.driver.quit()

def main():
    # Verify required environment variables
    required_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL', 'AIRBNB_SEARCH_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these environment variables before running the script")
        return
    
    monitor = AirbnbMonitorSelenium()
    
    # Run once for testing
    monitor.run_once()
    
    # Uncomment the line below for continuous monitoring
    # monitor.run_continuous(interval_minutes=30)

if __name__ == "__main__":
    main()