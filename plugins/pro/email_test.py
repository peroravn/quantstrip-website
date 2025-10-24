"""
Test client that sending email from the built-in email manager.

"""

from quantstrip import ClientBase
from quantstrip import send_email
from quantstrip import email_manager
import logging

RECIPIENT = "email@server.com"

# --- Logging setup ---
logger = logging.getLogger(__name__)

class Client(ClientBase):
    """ A minimal client
    """
    def __init__(self, *args):
        super().__init__()
        self.display_name = "Email Test"
        self.scheduler.every(1).seconds.do(self.job)

    def job(self):
        
        # Test 1: Send regular email
        logger.info("SENDING TEST EMAIL")
        send_email(subject  = "THIS IS A TEST EMAIL", 
                    body    = "Test email", 
                    to      = RECIPIENT)
                    
        # Test 2: Send HTML email
        html_body = """<html>
                        <body>
                            <h2>Trade Summary</h2>
                            <p>Today's P&L: <span style="color:green">$1,234.56</span></p>
                            <ul>
                                <li>AAPL: +$500</li>
                                <li>MSFT: +$734.56</li>
                            </ul>
                        </body>
                        </html>
                    """
                    
        success, msg = email_manager.send(
                                            subject ="Daily P&L Report",
                                            body    =html_body,
                                            to      =RECIPIENT,
                                            html    =True
                                        )
        
        self.stop_client()