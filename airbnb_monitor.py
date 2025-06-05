# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import requests
import json
import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AirbnbMonitor:
    def __init__(self):
        # Email configuration - these will be set as environment variables
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')  # App password for Gmail
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # File to store previously seen listings
        self.data_file = 'seen_listings.json'
        
        # Your Airbnb search URL
        self.search_url = os.getenv('AIRBNB_SEARCH_URL')
        
        # Load previously seen listings
        self.seen_listings = self.load_seen_listings()
    
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
        """Fetch current listings from Airbnb search"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        try:
            response = requests.get(self.search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            current_listings = []
            html_content = response.text
            
            # Try multiple patterns to find real listing data
            import re
            
            # Pattern 1: Look for listing IDs in data attributes
            listing_pattern1 = r'"listing":{"id":"(\d+)".*?"name":"([^"]+)"'
            matches1 = re.findall(listing_pattern1, html_content)
            
            # Pattern 2: Look for room data
            listing_pattern2 = r'"room":{"id":"(\d+)".*?"name":"([^"]+)"'
            matches2 = re.findall(listing_pattern2, html_content)
            
            # Pattern 3: Look for listing objects
            listing_pattern3 = r'"id":"(\d+)".*?"title":"([^"]+)".*?"roomType"'
            matches3 = re.findall(listing_pattern3, html_content)
            
            # Combine all matches and filter out obvious non-listings
            all_matches = matches1 + matches2 + matches3
            
            for listing_id, name in all_matches:
                # Filter out obvious non-listing data
                if (len(listing_id) > 6 and  # Real listing IDs are usually long
                    name not in ['treatment', 'control', 'flags', 'roles'] and  # Filter out test data
                    not name.startswith('*') and  # Filter out technical terms
                    len(name) > 3):  # Real listings have meaningful names
                    
                    current_listings.append({
                        'id': listing_id,
                        'name': name,
                        'url': f'https://www.airbnb.com/rooms/{listing_id}'
                    })
            
            # Remove duplicates based on ID
            seen_ids = set()
            unique_listings = []
            for listing in current_listings:
                if listing['id'] not in seen_ids:
                    seen_ids.add(listing['id'])
                    unique_listings.append(listing)
            
            logger.info(f"Found {len(unique_listings)} listings")
            
            # If we found very few listings, it might mean the page structure changed
            if len(unique_listings) < 3:
                logger.warning("Found fewer than 3 listings - this might indicate an issue with the scraping")
                # Let's also try a simpler pattern
                simple_pattern = r'data-testid="listing-(\d+)"'
                simple_matches = re.findall(simple_pattern, html_content)
                for listing_id in simple_matches[:10]:  # Limit to first 10
                    unique_listings.append({
                        'id': listing_id,
                        'name': f'Airbnb Listing {listing_id}',
                        'url': f'https://www.airbnb.com/rooms/{listing_id}'
                    })
            
            return unique_listings
            
        except requests.RequestException as e:
            logger.error(f"Error fetching listings: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
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
            
            # Set charset to handle special characters
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
                body += f"""
                <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                    <h3>{clean_name}</h3>
                    <p><strong>Listing ID:</strong> {listing['id']}</p>
                    <p><a href="{listing['url']}" style="color: #ff5a5f; text-decoration: none;">📍 View Listing</a></p>
                </div>
                """
            
            body += f"""
            <br>
            <p style="color: #666; font-size: 12px;">
                Alert sent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, self.recipient_email, text)
            server.quit()
            
            logger.info(f"Email notification sent for {len(new_listings)} new listings")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
    
    def check_for_new_listings(self):
        """Main function to check for new listings"""
        logger.info("Checking for new listings...")
        
        current_listings = self.get_listings()
        if not current_listings:
            logger.warning("No listings found - this might indicate an issue with the scraping")
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
    
    def run_continuous(self, interval_minutes=30):
        """Run the monitor continuously"""
        logger.info(f"Starting continuous monitoring (checking every {interval_minutes} minutes)")
        
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

def main():
    # Verify required environment variables
    required_vars = ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECIPIENT_EMAIL', 'AIRBNB_SEARCH_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these environment variables before running the script")
        return
    
    monitor = AirbnbMonitor()
    
    # You can choose to run once or continuously
    # For testing, use run_once()
    # For production, use run_continuous()
    
    # Run once for testing
    #monitor.run_once()
    
    #Uncomment the line below for continuous monitoring
    monitor.run_continuous(interval_minutes=30)

if __name__ == "__main__":
    main()