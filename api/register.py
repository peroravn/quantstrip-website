from http.server import BaseHTTPRequestHandler
import json
import os
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = os.environ.get("https://ozamqnegrjquvwfzxocf.supabase.co")
supabase_key = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o")
supabase: Client = create_client(supabase_url, supabase_key)

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
            
            name = data.get('name')
            email = data.get('email')
            
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
            
            response = {
                'success': True,
                'message': 'User registered successfully',
                'data': result.data
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