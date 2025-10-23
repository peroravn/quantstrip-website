"""
    Module implements basic functions to create IB data objects,
    like Orders, Contracts, etc...
"""

from ibapi.order import Order
from ibapi.contract import Contract

def ib_contract(symbol):
    """ Creates an IB contract object for US ETF contract """
    contract = Contract()
    contract.currency = "USD"
    contract.exchange = "SMART"
    contract.secType = "STK"
    contract.symbol = symbol
    return contract
    
def ib_order(quantity, order_ref = '', orderType = "MOC"):
    """ Creates an IB order object  """
    direction = "BUY" if quantity > 0 else "SELL"
    order = Order()
    order.action = direction
    order.orderType = orderType
    order.totalQuantity = abs(quantity)
    order.exchange = "SMART"
    order.orderRef = order_ref
    order.eTradeOnly = False
    order.firmQuoteOnly = False
    return order