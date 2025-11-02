"""
    A minimal test client sending an MOC order to IB and inserting it in the QS database.
    By default the order is sent through the Trader Workstation (TWS) over the test-system
    port.
    To make the database insert work correctly, a strategy needs to be created in the strategy table.
    
"""

from quantstrip import ClientBase, db_handler
from IBKR.ib_connect import IB
from IBKR.ib_objects import ib_contract, ib_order
import traceback
import logging

# --- Set up logger ---
logger = logging.getLogger(__name__)

# --- Create contract and order objects
contract = ib_contract("SPY")
order = ib_order(quantity = 100, orderType = "MKT")

class Client(ClientBase):
    """ A minimal client sending an order to IB
    """
    def __init__(self, *args):
        super().__init__()
        db_handler.get_connection()
        self.display_name = "IB Send Order Test"
        self.scheduler.every(1).seconds.do(self.job)


    def job(self):
        ib = IB()
        order_id = db_handler.next_order_id()
        logger.info(f"Sending MOC order to IB with order ID {order_id}")
        
        try:
            if ib.connect_client(client_id = 5):
                
                # Step 1: Place the order with IB
                ib.placeOrder(order_id, contract, order)
                
                # Step 2: Insert order in DB.
                db_handler.insert_order( order_id = order_id,
                                        strategy_id     = 1, # Test Strategy
                                        broker_id       = 1, 
                                        symbol          = "SPY",
                                        action          = "BUY",
                                        order_type      = "MOC",
                                        total_quantity  = 100)
                
                # Step 3: Insert position in the internal position table in DB
                db_handler.insert_position( strategy_id = 1, 
                                        broker_id   = 1, 
                                        symbol      = "SPY",
                                        position    = 100, 
                                        action      = "OPEN", 
                                        quantity    = 100, 
                                        group_label = "", 
                                        order_id    = order_id
                                        )
                
        except Exception as e:
            logger.info(f"Error: {e}")
            logger.info(traceback.format_exc())
        
        finally:
            ib.disconnect_client()
            
        self.stop_client()