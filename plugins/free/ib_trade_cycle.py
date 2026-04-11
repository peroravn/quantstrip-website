"""
Example client handling trade life-cycle events for Interactive Brokers.

Events:
    - order_status      (create)
    - execution         (create)
    - position_event    (create, triggered by execution)
    - strategy_event    (update, triggered by position_event)
    - commission        (create)
    
Run mode:
    - synchronous (scheduled requests)

"""

from quantstrip import ClientBase, db_handler
from IBKR.ib_connect import IB
import logging
import time
import traceback

# --- Logging setup ---
logger = logging.getLogger(__name__)

class Client(ClientBase):
    def __init__(self, *args):
        super().__init__()
        self.display_name = "IB Trade Flow Handler"
        self.db = db_handler
        self.scheduler.every(1).seconds.do(self.job)
        
    #------------------------------------------------------------------------------------
    #   Helper functions: Mapping IB fields to Quanstrip canonical datamodel
    #------------------------------------------------------------------------------------
        
    def insert_order_status(self, status):
        # Map IB status states to QS DB
        STATUS_MAP = {"Submitted": "SUBMITTED",
                      "Cancelled": "CANCELLED",
                      "Filled"   : "FILLED",
                     }

        order_status = STATUS_MAP.get(status["status"], "NEW")
        
        self.db.insert_order_status(
                                    order_id            = status['orderId'],
                                    external_order_id   = status['permId'],
                                    status              = order_status,
                                    filled_quantity     = status['filled'],
                                    remaining_quantity  = status['remaining'],
                                    avg_fill_price      = status['avgFillPrice'],
                                    last_fill_price     = status['lastFillPrice']
                                    )
                                    
        
    def insert_execution(self, execution, order):
        ex = execution['execution']
        c  = execution['contract']
        
        self.db.insert_execution(
                            exec_id         = ex['execId'],
                            order_id        = ex['orderId'],
                            strategy_id     = order["strategy_id"],
                            broker_id       = order["broker_id"],
                            symbol          = c['symbol'],
                            instrument_type = c["secType"],
                            contract_id     = c["conId"],
                            side            = "BUY" if ex['side'] == "BOT" else "SELL",
                            quantity        = ex['shares'],
                            price           = ex['price'],
                            exec_time       = ex['time'],
                            exchange        = ex['exchange'],
                            liquidity_flag  = None,
                            order_type      = order["order_type"],
                            cum_qty         = ex['cumQty'],
                            avg_price       = ex['avgPrice'],
                            is_liquidation  = None,
                            external_order_id = ex['permId'],
                            external_exec_id = None,
                            metadata        = {"order_ref" : ex['orderRef']}   # dict or None
                        )
    
    def insert_commission(self, commission):
        # Handle IB rpl quirk
        rpl = 0 if commission['realizedPNL'] > 1.0e+100 else commission['realizedPNL']  
        
        self.db.insert_commission(
                    exec_id         = commission['execId'], 
                    amount          = commission['commission'],
                    currency        = commission['currency'], 
                    fee_type        = "COMMISSION",
                    realized_pnl    = rpl,
                    metadata        = None   # dict or None
                    )
        
    def insert_position_event(self, execution, order):
        # Separate the actual execution object from the contract 
        ex = execution['execution']
        c  = execution['contract']
        
        exec_id = ex["execId"]
        side    = "BUY" if ex['side'] == "BOT" else "SELL"
    
        # Signed trade quantity: +BUY, -SELL
        qty = ex["shares"] if side == "BUY" else -ex["shares"]
        trade_price = ex["price"]
    
        # Handle position state (in relation to previous state)
        
        # 1. Load *previous* position snapshot
        strategy_id = order["strategy_id"] if order else -1
        symbol = c["symbol"]
        
        prev = self.db.get_last_position_event(strategy_id, symbol)
        old_pos = prev["position"] if prev else 0.0
        old_avg = prev["avg_price"] if prev else None
    
        # 2. Compute new position + avg_price and classify event type
        if old_pos == 0:
            # Fresh open
            new_pos = qty
            new_avg = trade_price
            event_type = "OPEN_LONG" if qty > 0 else "OPEN_SHORT"
    
        elif (old_pos > 0 and qty > 0):
            # Adding to long
            new_pos = old_pos + qty
            new_avg = (old_avg * old_pos + trade_price * qty) / new_pos
            event_type = "OPEN_LONG"
    
        elif (old_pos < 0 and qty < 0):
            # Adding to short
            new_pos = old_pos + qty
            new_avg = (old_avg * abs(old_pos) + trade_price * abs(qty)) / abs(new_pos)
            event_type = "OPEN_SHORT"
    
        elif old_pos > 0 and qty < 0 and old_pos + qty > 0:
            # Partial close of long
            new_pos = old_pos + qty
            new_avg = old_avg
            event_type = "PARTIAL_CLOSE"
    
        elif old_pos < 0 and qty > 0 and old_pos + qty < 0:
            # Partial cover of short
            new_pos = old_pos + qty
            new_avg = old_avg
            event_type = "PARTIAL_COVER"
    
        elif old_pos + qty == 0:
            # Full close or cover
            new_pos = 0
            new_avg = None
            event_type = "CLOSE" if old_pos > 0 else "COVER"
    
        else:
            # Flip 
            new_pos = old_pos + qty
            new_avg = trade_price
            event_type = "FLIP"
        
        # 4. Insert into position_event
        self.db.insert_position_event(
            event_time     = ex["time"],
            strategy_id    = order["strategy_id"],
            broker_id      = order["broker_id"],
            exec_id        = ex["execId"],
            order_id       = ex["orderId"],
            symbol         = c["symbol"],
            position       = new_pos,
            avg_price      = new_avg,
            trade_quantity = qty,
            trade_price    = ex["price"],
            event_type     = event_type,
            group_label    = None, #ex["orderRef"],
            metadata       = None
        )
    
        return new_pos, new_avg
        
        
    def job(self):
        
        ib = IB()
        logger.info("Running trade IB life-cycle process")
        try:
            with IB(client_id = 0) as ib: # client_id = 0 "sees" all executions from all other clients
            
                # 1. Fetch order_status for all open orders and insert records in DB if status changed
                all_order_status = ib.get_order_status()
                
                for order_id, status in all_order_status.items():
                    order = self.db.get_order(order_id)
                    if not order.empty:
                        self.insert_order_status(status)
                    
                # 2. Fetch new executions - insert new execution, insert position_event, 
                #    and confirm strategy position
                all_executions  = ib.get_executions()
                
                for execution in all_executions:
                    order_id = execution["execution"]["orderId"] 
                    order = self.db.get_order(order_id)
                    
                    if not order.empty: # Check that originating order exist in DB
                        order = order.iloc[0].to_dict()
                        
                        # 2a. Insert execution record 
                        self.insert_execution(execution, order)
                        
                        # 2b. Insert resulting position event
                        new_position, _ = self.insert_position_event(execution, order)
                        
                        # 2c. Update (confirm) strategy state
                        strategy_event = self.db.get_last_strategy_event_by_order(order_id)
                        target_position = strategy_event["position"]
                        
                        if new_position == target_position:
                            self.db.update_strategy_event_status(order_id, status="CONFIRMED")
                    
                # 4. Fetch and insert commissions
                all_commissions = ib.get_commissions()
                
                # select all exec_ids from DB
                stored_executions = self.db.get_executions()
                all_exec_ids = stored_executions['exec_id'].to_list()
                
                for commission in all_commissions:
                    if commission['execId'] in all_exec_ids:
                        self.insert_commission(commission)
                
        except Exception as e:
            logger.info(f"Failed to run IB trade life-cycle process: {e}\n{traceback.format_exc()}")
        
        self.stop_client()
                
        
