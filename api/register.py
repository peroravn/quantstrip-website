from http.server import BaseHTTPRequestHandler
import json
import uuid
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.utils import (
    create_user, 
    send_activation_email, 
    hash_password, 
    check_email_exists
)

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
            
            first_name = data.get('firstName', '').strip()
            last_name = data.get('lastName', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            # Validation
            if not first_name or not last_name or not email or not password:
                response = {'success': False, 'error': 'All fields are required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            if len(password) < 8:
                response = {'success': False, 'error': 'Password must be at least 8 characters'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if email already exists
            if check_email_exists(email):
                response = {'success': False, 'error': 'Email already registered'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Generate activation token
            activation_token = str(uuid.uuid4())
            
            # Hash password
            password_hash = hash_password(password)
            
            # Create user
            user = create_user(first_name, last_name, email, password_hash, activation_token)
            
            # Send activation email
            email_success, email_message = send_activation_email(
                email, first_name, last_name, activation_token
            )
            
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
            print(f"Registration error: {str(e)}")
            response = {'success': False, 'error': 'An error occurred during registration'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()