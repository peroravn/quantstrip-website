# from http.server import BaseHTTPRequestHandler

# class handler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(200)
#         self.send_header('Content-type', 'text/plain')
#         self.end_headers()
#         self.wfile.write(b'Hello from Python!')
#         return

from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_data = {
            "message": "Hello from Python!",
            "status": "success",
            "runtime": "python3.12",
            "timestamp": "2025-09-15"
        }
        
        self.wfile.write(json.dumps(response_data).encode('utf-8'))
        return