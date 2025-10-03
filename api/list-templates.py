from http.server import BaseHTTPRequestHandler
import json
import os
import re

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
            templates = []
            
            # Define the plugins directory structure
            base_path = os.path.join(os.path.dirname(__file__), '..', 'plugins')
            
            # Process free templates
            free_path = os.path.join(base_path, 'free')
            if os.path.exists(free_path):
                templates.extend(self.scan_directory(free_path, 'free'))
            
            # Process pro templates
            pro_path = os.path.join(base_path, 'pro')
            if os.path.exists(pro_path):
                templates.extend(self.scan_directory(pro_path, 'pro'))
            
            # Sort templates by name
            templates.sort(key=lambda x: x['filename'])
            
            response = {
                'success': True,
                'templates': templates
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error listing templates: {str(e)}")
            response = {'success': False, 'error': f'Server error: {str(e)}'}
            self.wfile.write(json.dumps(response).encode())
    
    def scan_directory(self, directory_path, tier):
        """Scan directory for Python files and extract docstrings"""
        templates = []
        
        try:
            if not os.path.exists(directory_path):
                return templates
            
            for filename in os.listdir(directory_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    file_path = os.path.join(directory_path, filename)
                    description = self.extract_docstring(file_path)
                    
                    templates.append({
                        'filename': filename,
                        'tier': tier,
                        'description': description,
                        'path': f'/plugins/{tier}/{filename}'
                    })
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {str(e)}")
        
        return templates
    
    def extract_docstring(self, file_path):
        """Extract the module-level docstring from a Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Match triple-quoted docstring at the start of the file
            # Handles both """ and ''' style docstrings
            pattern = r'^\s*["\']{{3}}(.*?)["\']{{3}}'
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            
            if match:
                docstring = match.group(1).strip()
                # Clean up the docstring - take first line or first sentence
                lines = docstring.split('\n')
                first_line = lines[0].strip()
                return first_line if first_line else 'No description available'
            
            return 'No description available'
        except Exception as e:
            print(f"Error extracting docstring from {file_path}: {str(e)}")
            return 'No description available'
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()