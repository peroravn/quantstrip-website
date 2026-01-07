from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
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
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            coupon_code = data.get('couponCode', '').strip().upper()
            product_id = data.get('productId')
            
            if not coupon_code:
                response = {'success': False, 'error': 'Coupon code is required'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Look up coupon in database
            result = supabase.table('coupons')\
                .select('*')\
                .eq('code', coupon_code)\
                .eq('is_active', True)\
                .execute()
            
            if not result.data or len(result.data) == 0:
                response = {'success': False, 'error': 'Invalid coupon code'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            coupon = result.data[0]
            
            # Check if coupon has expired
            expires_at = datetime.fromisoformat(coupon['expires_at'].replace('Z', '+00:00'))
            if datetime.now(expires_at.tzinfo) > expires_at:
                response = {'success': False, 'error': 'This coupon has expired'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if coupon has reached max uses
            if coupon['times_used'] >= coupon['max_uses']:
                response = {'success': False, 'error': 'This coupon has reached its usage limit'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if coupon is valid for this product
            if coupon['product_id'] is not None and coupon['product_id'] != product_id:
                response = {'success': False, 'error': 'This coupon is not valid for this product'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Coupon is valid!
            response = {
                'success': True,
                'message': 'Coupon is valid',
                'coupon': {
                    'code': coupon['code'],
                    'discount_percent': coupon['discount_percent'],
                    'id': coupon['id']
                }
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error validating coupon: {str(e)}")
            response = {'success': False, 'error': 'Server error validating coupon'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()