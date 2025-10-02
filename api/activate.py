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
        try:
            # Parse the URL and get the token parameter
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Get the token from query parameters
            token = query_params.get('token', [None])[0]
            
            if not token:
                self.send_html_response(400, 
                    "Invalid Request", 
                    "No activation token provided.")
                return
            
            # Look up the user with this activation token
            result = supabase.table('users')\
                .select('*')\
                .eq('activation_token', token)\
                .execute()
            
            # Check if user was found
            if not result.data or len(result.data) == 0:
                self.send_html_response(404,
                    "Invalid Token",
                    "This activation token is invalid or has already been used.")
                return
            
            user = result.data[0]
            full_name = f"{user['first_name']} {user['last_name']}"
            
            # Check if already activated
            if user['status'] == 'active':
                self.send_html_response(200,
                    "Already Activated",
                    f"Welcome back, {full_name}! Your account is already active.")
                return
            
            # Update user status to active and clear the token
            update_result = supabase.table('users')\
                .update({
                    'status': 'active',
                    'activation_token': None
                })\
                .eq('activation_token', token)\
                .execute()
            
            # Send success response
            self.send_html_response(200,
                "Account Activated!",
                f"Congratulations, {full_name}! Your Quantstrip account has been successfully activated. You can now sign in.",
                success=True)
            
        except Exception as e:
            print(f"Error during activation: {str(e)}")
            self.send_html_response(500,
                "Server Error",
                f"An error occurred during activation: {str(e)}")
    
    def send_html_response(self, status_code, title, message, success=False):
        """Send a styled HTML response"""
        self.send_response(status_code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        color = "#4CAF50" if success else "#f44336"
        icon = "✓" if success else "✗"
        button_text = "Sign In" if success else "Go to Home"
        button_link = "https://quantstrip.com/login.html" if success else "https://quantstrip.com"
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} - Quantstrip</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    max-width: 500px;
                    text-align: center;
                }}
                .icon {{
                    font-size: 64px;
                    color: {color};
                    margin-bottom: 20px;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 30px;
                    background-color: {color};
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    transition: opacity 0.3s;
                }}
                .btn:hover {{
                    opacity: 0.8;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">{icon}</div>
                <h1>{title}</h1>
                <p>{message}</p>
                <a href="{button_link}" class="btn">{button_text}</a>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()