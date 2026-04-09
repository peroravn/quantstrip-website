"""
    Connects to the IB Flex Web Service, runs a flex query and captuures the result (XML)
    
    Requires a Flex Web Service TOKEN. This is generated from the IBKR client posrtal.
    
    Used for batch reconciliation of positions, commissions, exections etc.
"""

from quantstrip import ClientBase
from settings import Settings
import requests
import time
import logging
import xml.etree.ElementTree as ET

# --- Logging setup ---
logger = logging.getLogger(__name__)

s = Settings()
TOKEN = s.get_by_path("Settings/IBKR Flex Web Service/TOKEN")
QUERY_ID = 689218

BASE_URL = "https://ndcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest"
STATUS_URL = "https://ndcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement"


class Client(ClientBase):
    """ A minimal client
    """
    def __init__(self, *args):
        super().__init__()
        self.display_name = "Test Client"
        self.scheduler.every(1).seconds.do(self.job)
        
    def request_report(self, token, query_id):
        params = {
            "t": token,
            "q": query_id,
            "v": "3"
        }
        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
            return response.text
        except:
            logger.error("Request failed")
            self.stop_client()
            return None
            
    def get_statement(self, token, reference_code):
        params = {
            "t": token,
            "q": reference_code,
            "v": "3"
        }
        response = requests.get(STATUS_URL, params=params)
        response.raise_for_status()
        return response.text
    
    def parse_xml_for_reference(self, xml_text):
        root = ET.fromstring(xml_text)
        status = root.find("Status").text
    
        if status != "Success":
            error_msg = root.find("ErrorMessage").text
            raise Exception(f"Request failed: {error_msg}")
    
        return root.find("ReferenceCode").text
    
    def is_ready(self, xml_text):
        root = ET.fromstring(xml_text)
        status = root.find("Status").text
        return status == "Success"
    
    def main(self):
        logger.info("Requesting Flex report...")
    
        # Step 1: Request report
        initial_response = self.request_report(TOKEN, QUERY_ID)
        reference_code = self.parse_xml_for_reference(initial_response)
    
        logger.info(f"Reference Code: {reference_code}")
        logger.info("Waiting for report to be ready...")
    
        result = self.get_statement(TOKEN, reference_code)
    
        logger.info(result)
        return

    def job(self):
        try:
            self.main()
        except:
            self.stop_client()
        finally:
            self.stop_client()
            
        