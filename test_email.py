import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_email():
    # Email configuration - clean any potential hidden characters
    sender_email = os.getenv('SENDER_EMAIL', '').strip()
    sender_password = os.getenv('SENDER_PASSWORD', '').strip()
    recipient_email = os.getenv('RECIPIENT_EMAIL', '').strip()
    
    print(f"Sender email: '{sender_email}'")
    print(f"Recipient email: '{recipient_email}'")
    print(f"Password length: {len(sender_password)} characters")
    print(f"Password set: {'Yes' if sender_password else 'No'}")
    
    # Check for problematic characters
    for i, char in enumerate(sender_email):
        if ord(char) > 127:
            print(f"❌ Found non-ASCII character in sender email at position {i}: {repr(char)}")
    
    if not all([sender_email, sender_password, recipient_email]):
        print("❌ Missing email configuration in .env file")
        return False
    
    try:
        # Create simple test message with only ASCII characters
        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "Airbnb Monitor Email Test"
        
        # Simple ASCII-only body
        body = f"""
        <h2>Email Test Successful!</h2>
        <p>This is a test email from your Airbnb monitor script.</p>
        <p>If you received this, your email configuration is working correctly!</p>
        <p>Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        """
        
        # Attach with explicit UTF-8 encoding
        html_part = MIMEText(body.encode('utf-8'), 'html', 'utf-8')
        msg.attach(html_part)
        
        print("Connecting to Gmail...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        
        print("Logging in...")
        server.login(sender_email, sender_password)
        
        print("Sending email...")
        # Use send_message instead of sendmail for better encoding handling
        server.send_message(msg, from_addr=sender_email, to_addrs=[recipient_email])
        server.quit()
        
        print("✅ Email sent successfully!")
        print("Check your inbox (and spam folder) for the test email.")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("Check your Gmail app password - it should be 16 characters")
        return False
    except UnicodeEncodeError as e:
        print(f"❌ Unicode encoding error: {e}")
        print("There are special characters in your email configuration")
        return False
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

if __name__ == "__main__":
    test_email()