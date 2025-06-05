import requests
import os
from dotenv import load_dotenv
load_dotenv()

# Your Airbnb search URL
search_url = os.getenv('AIRBNB_SEARCH_URL')

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

print("Fetching page...")
response = requests.get(search_url, headers=headers, timeout=30)
html_content = response.text

print(f"Page status: {response.status_code}")
print(f"Page size: {len(html_content)} characters")

# Save the HTML to a file so we can examine it
with open('debug_page.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("HTML saved to debug_page.html")

# Look for different patterns
import re

# Check if it's a blocked page
if "blocked" in html_content.lower() or "captcha" in html_content.lower():
    print("❌ Page might be blocked or requires captcha")

# Look for any room/listing references
room_patterns = [
    r'data-testid="listing-(\d+)"',
    r'"listing_id":"(\d+)"',
    r'"room_id":"(\d+)"',
    r'"id":"(\d+)".*?"pdp_type":".*?"',
    r'href="/rooms/(\d+)',
]

print("\n=== Looking for listing patterns ===")
for i, pattern in enumerate(room_patterns):
    matches = re.findall(pattern, html_content)
    print(f"Pattern {i+1}: Found {len(matches)} matches")
    if matches:
        print(f"  Sample matches: {matches[:5]}")

# Look for the word "Airbnb" to confirm we're on the right page
if "airbnb" in html_content.lower():
    print("✅ We're on an Airbnb page")
else:
    print("❌ This doesn't seem to be an Airbnb page")

# Check for JavaScript content (Airbnb is heavily JS-based)
if "window.__INITIAL_STATE__" in html_content:
    print("✅ Found JavaScript state data")
else:
    print("❌ No JavaScript state found - page might not be loading properly")

# Look for any error messages
error_patterns = ["Access denied", "Something went wrong", "Page not found", "blocked"]
for error in error_patterns:
    if error.lower() in html_content.lower():
        print(f"❌ Found error: {error}")

print("\n=== Next steps ===")
print("1. Check the debug_page.html file to see what we actually got")
print("2. If it's blocked, we might need to use a different approach")
print("3. If it has data, we can adjust our parsing patterns")