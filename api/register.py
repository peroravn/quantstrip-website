from http.server import BaseHTTPRequestHandler
import json
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

# Gmail configuration
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "quantstrip@gmail.com"
SMTP_PASSWORD = "svvpsmnmfcwccrsy"
FROM_EMAIL = SMTP_USER

def send_activation_email(to_email, name, activation_token):
    """Send activation email with token link"""
    try:
        print(f"Attempting to send activation email to {to_email}")
        print(f"SMTP Settings: {SMTP_HOST}:{SMTP_PORT}")
        print(f"From: {FROM_EMAIL}")
        
        # Create the activation link
        activation_link = f"https://quantstrip.com/api/activate?token={activation_token}"
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Activate Your Quantstrip Account'
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Text content
        text = f"""
        Hello {name},
        
        Thank you for registering at Quantstrip!
        
        Please activate your account by clicking the following link:
        {activation_link}
        
        If you didn't register for this account, please ignore this email.
        
        Best regards,
        The Quantstrip Team
        """
        
        # HTML content with styled button
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Hello {name},</h2>
            <p>Thank you for registering at Quantstrip!</p>
            <p>Please activate your account by clicking the button below:</p>
            <p style="margin: 30px 0;">
                <a href="{activation_link}" 
                   style="background-color: #4CAF50; 
                          color: white; 
                          padding: 12px 24px; 
                          text-decoration: none; 
                          border-radius: 4px;
                          display: inline-block;">
                    Activate my account
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link into your browser:<br>
                <a href="{activation_link}">{activation_link}</a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                If you didn't register for this account, please ignore this email.
            </p>
            <p>Best regards,<br>The Quantstrip Team</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        print("Connecting to Gmail SMTP server...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            print("TLS started. Logging in...")
            server.login(SMTP_USER, SMTP_PASSWORD)
            print("Login successful. Sending message...")
            server.send_message(msg)
            print("Message sent!")
        
        return True, "Activation email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"Authentication failed: {str(e)}"
        print(error_msg)
        return False, error_msg
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error: {str(e)}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__} - {str(e)}"
        print(error_msg)
        return False, error_msg

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
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            
            if not name or not email:
                response = {'success': False, 'error': 'Name and email are required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Generate unique activation token
            activation_token = str(uuid.uuid4())
            
            # Insert user with activation token and pending status
            result = supabase.table('users').insert({
                'name': name,
                'email': email,
                'activation_token': activation_token,
                'status': 'pending_activation'
            }).execute()
            
            # Send activation email
            email_success, email_message = send_activation_email(email, name, activation_token)
            
            if email_success:
                response = {
                    'success': True,
                    'message': f'Registration successful! Please check {email} for activation instructions.',
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
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()