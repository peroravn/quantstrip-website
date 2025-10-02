from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Enable CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        try:
            # Parse URL and get email parameter
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            email = query_params.get('email', [None])[0]
            
            if not email:
                response = {'success': False, 'error': 'Email is required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Get user ID from email
            user_result = supabase.table('users')\
                .select('id')\
                .eq('email', email)\
                .execute()
            
            if not user_result.data or len(user_result.data) == 0:
                response = {'success': False, 'error': 'User not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            user_id = user_result.data[0]['id']
            
            # Fetch all licenses for this user with product information
            # Using a join-like query to get product details
            licenses_result = supabase.table('licenses')\
                .select('*, products(name, description)')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            licenses = []
            for license_data in licenses_result.data:
                # Extract product name from the joined data
                product_name = license_data['products']['name'] if license_data.get('products') else 'Unknown Product'
                
                licenses.append({
                    'id': license_data['id'],
                    'license_key': license_data['license_key'],
                    'product_id': license_data['product_id'],
                    'product_name': product_name,
                    'status': license_data['status'],
                    'expires_at': license_data['expires_at'],
                    'created_at': license_data['created_at'],
                    'coupon_used': license_data['coupon_used']
                })
            
            response = {
                'success': True,
                'licenses': licenses
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error fetching licenses: {str(e)}")
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()