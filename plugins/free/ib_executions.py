from clients._client_base import ClientBase
from IBKR.ib_connect import IB
import logging

# --- Logging setup ---
logger = logging.getLogger(__name__)

class Client(ClientBase):
    """ A minimal client
    """
    def __init__(self, *args):
        super().__init__()
        self.display_name = "IB Execution Handler"
        self.scheduler.every(10).seconds.do(self.job)

    def job(self):
        ib = IB()
        logger.info("Checking for new executions")
        try:
            if ib.connect_client(client_id = 0):
                executions = ib.get_executions()
                logger.info(f"EXEVUTION RETURNED: {executions}")
        except Exception as e:
            print(e)
        
        finally:
            ib.disconnect_client()