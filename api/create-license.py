from http.server import BaseHTTPRequestHandler
import json
import smtplib
import hashlib
import base64
from datetime import datetime, timedelta
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


def generate_license_key(user_id, product_id, expires_at):
    """
    Generate a license key in format: QSTR-XXXX-YYYY-ZZZZ-AAAA
    
    Encodes:
    - Product ID (2 digits): 01=Free, 02=Pro
    - User ID (4 digits): 0001-9999
    - Expiration date (8 digits): YYYYMMDD
    
    Args:
        user_id: User ID (integer)
        product_id: Product ID (1=Free, 2=Pro)
        expires_at: Expiration datetime object
        
    Returns:
        str: License key (e.g., "QSTR-ABCD-EFGH-IJKL-ABC1")
    """
    # Format expiration date as YYYYMMDD
    exp_date = expires_at.strftime('%Y%m%d')
    
    # Create data string: ProductID(2) + UserID(4) + ExpirationDate(8) = 14 chars total
    data = f"{product_id:02d}{user_id:04d}{exp_date}"
    
    # Generate checksum (first 4 chars of SHA256 hash, uppercase)
    checksum = hashlib.sha256(data.encode()).hexdigest()[:4].upper()
    
    # Encode the data in base32
    encoded_with_padding = base64.b32encode(data.encode()).decode('utf-8')
    
    # Remove padding for display
    encoded = encoded_with_padding.rstrip('=')
    
    # Split into 4-character chunks
    part1 = encoded[0:4]
    part2 = encoded[4:8]
    part3 = encoded[8:12]
    
    # Format as QSTR-XXXX-YYYY-ZZZZ-AAAA
    license_key = f"QSTR-{part1}-{part2}-{part3}-{checksum}"
    
    return license_key


def send_license_email(to_email, first_name, product_name, license_key, expires_at_formatted):
    """Send email with license key"""
    try:
        print(f"Sending license email to {to_email}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Your {product_name} License Key - Quantstrip'
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Text content
        text = f"""
        Hello {first_name},
        
        Thank you for your purchase!
        
        Your {product_name} license has been generated successfully.
        
        LICENSE KEY: {license_key}
        
        License Details:
        - Product: {product_name}
        - Valid Until: {expires_at_formatted}
        
        To activate your software:
        1. Copy the license key above
        2. Open your Quantstrip software
        3. Enter the license key when prompted
        
        If you have any questions, please don't hesitate to contact our support team.
        
        Best regards,
        The Quantstrip Team
        """
        
        # HTML content
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4CAF50;">Thank You for Your Purchase!</h2>
                <p>Hello {first_name},</p>
                <p>Your <strong>{product_name}</strong> license has been generated successfully.</p>
                
                <div style="background-color: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #333;">Your License Key</h3>
                    <div style="background-color: white; padding: 15px; border: 2px solid #4CAF50; border-radius: 4px; font-family: monospace; font-size: 18px; text-align: center; letter-spacing: 1px;">
                        {license_key}
                    </div>
                </div>
                
                <div style="background-color: #e8f5e9; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <h4 style="margin-top: 0; color: #2e7d32;">License Details</h4>
                    <p style="margin: 5px 0;"><strong>Product:</strong> {product_name}</p>
                    <p style="margin: 5px 0;"><strong>Valid Until:</strong> {expires_at_formatted}</p>
                </div>
                
                <h3>How to Activate</h3>
                <ol>
                    <li>Copy the license key above</li>
                    <li>Open your Quantstrip software</li>
                    <li>Enter the license key when prompted</li>
                </ol>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    If you have any questions, please contact our support team.
                </p>
                
                <p style="margin-top: 20px;">Best regards,<br><strong>The Quantstrip Team</strong></p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print("License email sent successfully!")
        
        return True, "Email sent successfully"
    except Exception as e:
        error_msg = f"Email error: {type(e).__name__} - {str(e)}"
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
            
            email = data.get('email', '').strip()
            product_id = data.get('productId')
            coupon_code = data.get('couponCode')
            
            if not email or not product_id:
                response = {'success': False, 'error': 'Email and product ID are required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Get user info
            user_result = supabase.table('users')\
                .select('*')\
                .eq('email', email)\
                .execute()
            
            if not user_result.data or len(user_result.data) == 0:
                response = {'success': False, 'error': 'User not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            user = user_result.data[0]
            
            # Get product info
            product_result = supabase.table('products')\
                .select('*')\
                .eq('id', product_id)\
                .execute()
            
            if not product_result.data or len(product_result.data) == 0:
                response = {'success': False, 'error': 'Product not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            product = product_result.data[0]
            
            # Calculate expiration date
            expires_at = datetime.now() + timedelta(days=product['duration_days'])
            
            # Generate license key
            license_key = generate_license_key(user['id'], product['id'], expires_at)
            
            # Insert license into database
            license_result = supabase.table('licenses').insert({
                'user_id': user['id'],
                'product_id': product['id'],
                'license_key': license_key,
                'expires_at': expires_at.isoformat(),
                'status': 'active',
                'coupon_used': coupon_code if coupon_code else None
            }).execute()
            
            # If coupon was used, increment usage count
            if coupon_code:
                coupon_result = supabase.table('coupons')\
                    .select('*')\
                    .eq('code', coupon_code.upper())\
                    .execute()
                
                if coupon_result.data and len(coupon_result.data) > 0:
                    coupon = coupon_result.data[0]
                    supabase.table('coupons')\
                        .update({'times_used': coupon['times_used'] + 1})\
                        .eq('id', coupon['id'])\
                        .execute()
            
            # Send license email
            email_success, email_message = send_license_email(
                user['email'],
                user['first_name'],
                product['name'],
                license_key,
                expires_at.strftime('%B %d, %Y')
            )
            
            response = {
                'success': True,
                'message': 'License created successfully',
                'license': {
                    'key': license_key,
                    'expires_at': expires_at.isoformat()
                },
                'email_sent': email_success
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error creating license: {str(e)}")
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()