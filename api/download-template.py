from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

def validate_user_license(email, required_product=None):
    """
    Validate that user has an active license.
    If required_product is specified (e.g., 'Pro'), check for that specific product.
    Returns: (is_valid, error_message)
    """
    try:
        # Get user
        user_result = supabase.table('users')\
            .select('id')\
            .eq('email', email)\
            .execute()
        
        if not user_result.data or len(user_result.data) == 0:
            return False, 'User not found'
        
        user_id = user_result.data[0]['id']
        
        # Get user's licenses with product information
        licenses_result = supabase.table('licenses')\
            .select('*, products(name)')\
            .eq('user_id', user_id)\
            .eq('status', 'active')\
            .execute()
        
        if not licenses_result.data or len(licenses_result.data) == 0:
            return False, 'No active licenses found'
        
        # Check if any license is still valid (not expired)
        has_valid_license = False
        has_required_product = False
        
        for license_data in licenses_result.data:
            expires_at = datetime.fromisoformat(license_data['expires_at'].replace('Z', '+00:00'))
            is_valid = datetime.now(expires_at.tzinfo) < expires_at
            
            if is_valid:
                has_valid_license = True
                
                # Check for specific product if required
                if required_product:
                    product_name = license_data['products']['name'] if license_data.get('products') else None
                    if product_name == required_product:
                        has_required_product = True
                        break
                else:
                    # No specific product required, any valid license is fine
                    return True, None
        
        if not has_valid_license:
            return False, 'All licenses have expired'
        
        if required_product and not has_required_product:
            return False, f'{required_product} license required'
        
        return True, None
        
    except Exception as e:
        print(f"Error validating license: {str(e)}")
        return False, f'Validation error: {str(e)}'

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
            tier = data.get('tier', '')  # 'free' or 'pro'
            filename = data.get('filename', '')
            
            if not email or not tier or not filename:
                response = {'success': False, 'error': 'Missing required parameters'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Validate tier
            if tier not in ['free', 'pro']:
                response = {'success': False, 'error': 'Invalid tier'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Validate filename (security check - no path traversal)
            if '..' in filename or '/' in filename or '\\' in filename:
                response = {'success': False, 'error': 'Invalid filename'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if file exists
            file_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', tier, filename)
            if not os.path.exists(file_path) or not filename.endswith('.py'):
                response = {'success': False, 'error': 'File not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Check if Pro license is required
            required_product = 'Pro' if tier == 'pro' else None
            
            # Validate user has appropriate license
            is_valid, error_msg = validate_user_license(email, required_product)
            
            if not is_valid:
                response = {'success': False, 'error': error_msg}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Generate download URL
            download_url = f'https://quantstrip.com/plugins/{tier}/{filename}'
            
            # Log the download
            try:
                user_result = supabase.table('users')\
                    .select('id')\
                    .eq('email', email)\
                    .execute()
                
                if user_result.data:
                    user_id = user_result.data[0]['id']
                    print(f"Download authorized for user {user_id}: {tier}/{filename}")
            except Exception as e:
                print(f"Logging error (non-critical): {str(e)}")
            
            response = {
                'success': True,
                'downloadUrl': download_url,
                'filename': filename,
                'message': 'Download authorized'
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error processing download: {str(e)}")
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()