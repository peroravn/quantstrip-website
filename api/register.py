from http.server import BaseHTTPRequestHandler
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

# Email configuration - UPDATE THESE
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_USER = "info@yquantstrip.com"  # Your Office 365 email
SMTP_PASSWORD = "Elsakatten1#"      # Your Office 365 password
FROM_EMAIL = "info@quantstrip.com"

supabase: Client = create_client(supabase_url, supabase_key)

def send_test_email(to_email, name):
    """Send a simple test email"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Welcome to Quantstrip - Test Email'
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Simple text content
        text = f"""
        Hello {name},
        
        Thank you for registering at Quantstrip!
        
        This is a test email to confirm our email system is working.
        
        Best regards,
        The Quantstrip Team
        """
        
        # Simple HTML content
        html = f"""
        <html>
        <body>
            <h2>Hello {name},</h2>
            <p>Thank you for registering at Quantstrip!</p>
            <p>This is a test email to confirm our email system is working.</p>
            <p>Best regards,<br>The Quantstrip Team</p>
        </body>
        </html>
        """
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True, "Email sent successfully"
    except Exception as e:
        return False, str(e)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Enable CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            
            # Validate input
            if not name or not email:
                response = {
                    'success': False,
                    'error': 'Name and email are required'
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Insert into Supabase
            result = supabase.table('users').insert({
                'name': name,
                'email': email
            }).execute()
            
            # Try to send test email
            email_success, email_message = send_test_email(email, name)
            
            if email_success:
                response = {
                    'success': True,
                    'message': f'Registration successful! A test email has been sent to {email}',
                    'email_sent': True
                }
            else:
                response = {
                    'success': True,
                    'message': f'Registration successful, but email failed: {email_message}',
                    'email_sent': False,
                    'email_error': email_message
                }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            response = {
                'success': False,
                'error': str(e)
            }
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        # Handle preflight request
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()