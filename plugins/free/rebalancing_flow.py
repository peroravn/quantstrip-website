from quantstrip import ClientBase
import logging
from Utils import calendar_utils as cu
from IBKR.ib_objects import ib_order, ib_contract
from IBKR.ib_connect import ib 

# --- Logging setup ---
logger = logging.getLogger(__name__)

ALLOCATION = 100000

class Client(ClientBase):
    """ A trading client executing the SPY/TLT rebalancing trade
    """
    def __init__(self, *args):
        super().__init__()
        self.display_name = "Rebalancing Flow"
        self.scheduler.every().day.at("03:45", "America/New_York").do(self.job)
        
    def job(self):
        TLT_contract = ib_contract("TLT")
        SPY_contract = ib_contract("SPY")
        # Check if today is 16th trading day of the month (open position)
        if cu.business_day_number_today(calendar = "NYSE") == 16:
            try:
                if ib.connect_client(client_id = 1):
                    
                    # Get historical prices for last 16 days
                    TLT = ib.get_historical_data(TLT_contract, "", "16 D", "1 day")
                    SPY = ib.get_historical_data(SPY_contract, "", "16 D", "1 day")

                    # Calculate performance
                    TLT_perf    = TLT.iloc[-1]["close"]/TLT.iloc[0]["close"]
                    TLT_qty     = ALLOCATION / TLT.iloc[0]["close"]
                    
                    SPY_perf    = SPY.iloc[-1]["close"]/SPY.iloc[0]["close"]
                    SPY_qty     = ALLOCATION / SPY.iloc[0]["close"]

                    # Open position
                    if TLT_perf > SPY_perf:
                        contract, quantity = (SPY_contract, int(SPY_qty)) 
                    else:
                        contract, quantity = (TLT_contract, int(TLT_qty))
                        
                    ib.placeOrder(ib.get_next_order_id(), 
                                    contract, 
                                    ib_order(quantity, 
                                    "Rebalancing", 
                                    "MKT"))
                    
            except Exception as e:
                logger.error(e)
            
            finally:
                ib.disconnect_client()
        
        # Check if today is 1st trading day of the month (close position)
        if cu.is_last_business_day_of_month(calendar = "NYSE"):
            try:
                if ib.connect_client(client_id = 1):
                    positions = {p['contract'].symbol : p['position'] for p in ib.get_positions()} 
                    logger.info(f"Positions {positions}")
                    
                    if "TLT" in positions:
                        ib.placeOrder(ib.get_next_order_id(), 
                                        TLT_contract, 
                                        ib_order(-int(positions["TLT"]),
                                        "Rebalancing",
                                        "MKT")
                                        )
                                        
                    if "SPY" in positions: 
                        ib.placeOrder(ib.get_next_order_id(), 
                                        SPY_contract, 
                                        ib_order(-int(positions["SPY"]),
                                        "Rebalancing", "MKT")
                                        )
            
            except Exception as e:
                logger.error(e)
            
            finally:
                ib.disconnect_client()
                
        self.stop_client()
                        
                
        
        