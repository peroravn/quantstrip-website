from http.server import BaseHTTPRequestHandler
import json
import hashlib
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

def hash_password(password):
    """Hash password using SHA-256 with salt (must match registration)"""
    salt = "quantstrip_salt_2024"
    salted_password = password + salt
    return hashlib.sha256(salted_password.encode()).hexdigest()

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
            password = data.get('password', '')
            
            # Validation
            if not email or not password:
                response = {'success': False, 'error': 'Email and password are required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Look up user by email
            result = supabase.table('users')\
                .select('*')\
                .eq('email', email)\
                .execute()
            
            # Check if user exists
            if not result.data or len(result.data) == 0:
                response = {'success': False, 'error': 'Invalid email or password'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            user = result.data[0]
            
            # Check if account is activated
            if user['status'] != 'active':
                response = {
                    'success': False, 
                    'error': 'Account not activated. Please check your email for the activation link.'
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Verify password
            password_hash = hash_password(password)
            if user['password_hash'] != password_hash:
                response = {'success': False, 'error': 'Invalid email or password'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Successful login
            response = {
                'success': True,
                'message': 'Login successful',
                'user': {
                    'email': user['email'],
                    'firstName': user['first_name'],
                    'lastName': user['last_name']
                }
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Login error: {str(e)}")
            response = {'success': False, 'error': 'An error occurred during login'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()