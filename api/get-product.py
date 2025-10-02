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
            # Parse URL and get product ID
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            product_id = query_params.get('id', [None])[0]
            
            if not product_id:
                response = {'success': False, 'error': 'Product ID is required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Fetch product from database
            result = supabase.table('products')\
                .select('*')\
                .eq('id', product_id)\
                .eq('is_active', True)\
                .execute()
            
            if not result.data or len(result.data) == 0:
                response = {'success': False, 'error': 'Product not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            product = result.data[0]
            
            # Return product details
            response = {
                'success': True,
                'product': {
                    'id': product['id'],
                    'name': product['name'],
                    'description': product['description'],
                    'price_usd': float(product['price_usd']),
                    'duration_days': product['duration_days']
                }
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error fetching product: {str(e)}")
            response = {'success': False, 'error': 'Server error'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()