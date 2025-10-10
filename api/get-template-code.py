from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from api.utils import validate_user_license
except ImportError:
    from utils import validate_user_license

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
            
            # Check if Pro license is required
            required_product = 'Pro' if tier == 'pro' else None
            
            # Validate user has appropriate license
            is_valid, error_msg = validate_user_license(email, required_product)
            
            if not is_valid:
                response = {'success': False, 'error': error_msg}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Read the template file
            file_path = os.path.join(os.path.dirname(__file__), '..', 'plugins', tier, filename)
            
            if not os.path.exists(file_path) or not filename.endswith('.py'):
                response = {'success': False, 'error': 'File not found'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
            except Exception as e:
                print(f"Error reading file: {str(e)}")
                response = {'success': False, 'error': 'Failed to read file'}
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Limit code size to prevent excessively large transfers
            max_size = 1000000  # 1MB
            if len(code) > max_size:
                code = code[:max_size] + '\n\n... (code truncated)'
            
            response = {
                'success': True,
                'code': code,
                'filename': filename,
                'tier': tier
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error processing request: {str(e)}")
            response = {'success': False, 'error': 'Server error'}
            self.wfile.write(json.dumps(response).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()