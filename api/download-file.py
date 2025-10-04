from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = "https://ozamqnegrjquvwfzxocf.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im96YW1xbmVncmpxdXZ3Znp4b2NmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzk0NzQ5OCwiZXhwIjoyMDczNTIzNDk4fQ.pxyJuiPZ9NZdspKVOlgSlLk1_Dgm5QNTuypSMy4gI_o"
supabase: Client = create_client(supabase_url, supabase_key)

# Vercel Blob Storage URLs for installers
# After uploading to Vercel Blob, replace these with your actual blob URLs
INSTALLER_BLOB_URLS = {
    'windows': os.environ.get('BLOB_URL_WINDOWS', 'https://ykti6gajg8cwr1pz.public.blob.vercel-storage.com/Quantstrip_Installer.exe'),
    'macos': os.environ.get('BLOB_URL_MACOS', 'https://your-blob-url.public.blob.vercel-storage.com/quantstrip-macos-v1.0.dmg'),
    'linux': os.environ.get('BLOB_URL_LINUX', 'https://your-blob-url.public.blob.vercel-storage.com/quantstrip-linux-v1.0.tar.gz')
}

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
            file_type = data.get('fileType', '')  # 'platform'
            platform = data.get('platform', '')    # 'windows', 'macos', 'linux'
            
            if not email or not file_type or not platform:
                response = {'success': False, 'error': 'Missing required parameters'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Only handle platform installers here (plugins moved to templates page)
            if file_type != 'platform':
                response = {'success': False, 'error': 'Invalid file type'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            if platform not in INSTALLER_BLOB_URLS:
                response = {'success': False, 'error': 'Invalid platform'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Validate user has active license (any license is fine for platform download)
            is_valid, error_msg = validate_user_license(email)
            
            if not is_valid:
                response = {'success': False, 'error': error_msg}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Get Vercel Blob URL for the installer
            download_url = INSTALLER_BLOB_URLS[platform]
            
            # Log the download
            try:
                user_result = supabase.table('users')\
                    .select('id, first_name, last_name')\
                    .eq('email', email)\
                    .execute()
                
                if user_result.data:
                    user_id = user_result.data[0]['id']
                    print(f"Download authorized for user {user_id}: {platform} installer")
            except Exception as e:
                print(f"Logging error (non-critical): {str(e)}")
            
            response = {
                'success': True,
                'downloadUrl': download_url,
                'filename': f'quantstrip-{platform}',
                'message': 'Download authorized',
                'fileInfo': {
                    'type': file_type,
                    'platform': platform
                }
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