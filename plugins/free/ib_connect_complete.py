"""
ib_connect.py

Synchronous wrapper around the Interactive Brokers Python API (ibapi).

Provides a collection of blocking `get_...` methods that wrap IB's asynchronous
`req...` calls using threading.Event synchronization and thread-safe request IDs.

Return conventions:
- List responses -> list[dict] (mirrors get_executions pattern).
- Single-value responses -> float or None.
- Structured responses -> pandas.DataFrame.

Timeouts and errors:
- Matches existing wrapper behavior: prints/logs an INFO message and returns
  an empty collection or None on timeout/error unless otherwise documented.

NOTE: This code uses the public ibapi interfaces. Callback signatures can vary
slightly by ibapi version; the code aims to be robust for recent ibapi versions.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

# Configure module-level logger (user can reconfigure in their application)
logger = logging.getLogger(__name__)

# Type aliases
DictAny = Dict[str, Any]


class IB(EWrapper, EClient):
    """
    Thread-safe synchronous wrapper over ibapi's asynchronous API.

    Use as a context manager:

        with IB() as ib:
            df = ib.get_historical_data(contract, ...)
    """

    # ------------- Initialization & internals -----------------
    def __init__(self) -> None:
        EClient.__init__(self, self)

        # Connection state
        self.connected: bool = False
        self.api_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Request-id counter
        self._reqid_lock = threading.Lock()
        self._next_req_id_val: int = 1000  # start point for generated request IDs

        # Storage + Events for different synchronous operations
        self._historical_data: List[List[Any]] = []
        self._historical_data_event = threading.Event()
        self._historical_error: Optional[str] = None

        self._executions: List[DictAny] = []
        self._executions_event = threading.Event()
        self._executions_error: Optional[str] = None

        # Market data snapshot containers: reqId -> record and event
        self._mktdata: Dict[int, DictAny] = {}
        self._mktdata_events: Dict[int, threading.Event] = {}

        # Realtime bars
        self._realtime_bars: Dict[int, List[List[Any]]] = {}
        self._realtime_bars_events: Dict[int, threading.Event] = {}

        # Positions
        self._positions: List[DictAny] = []
        self._positions_event = threading.Event()
        self._positions_error: Optional[str] = None

        # Open orders
        self._open_orders: List[DictAny] = []
        self._open_orders_event = threading.Event()
        self._open_orders_error: Optional[str] = None

        # Account summary
        self._account_summary: List[List[Any]] = []
        self._account_summary_event = threading.Event()
        self._account_summary_error: Optional[str] = None

        # Portfolio (account updates snapshot)
        self._portfolio: List[DictAny] = []
        self._portfolio_event = threading.Event()
        self._portfolio_error: Optional[str] = None
        self._account_download_end_event = threading.Event()

        # Contract details
        self._contract_details: List[DictAny] = []
        self._contract_details_event = threading.Event()
        self._contract_details_error: Optional[str] = None

        # Historical ticks
        self._historical_ticks: List[DictAny] = []
        self._historical_ticks_event = threading.Event()
        self._historical_ticks_error: Optional[str] = None

        # Fundamental data (reqId -> data string)
        self._fundamental_data: Dict[int, str] = {}
        self._fundamental_data_event = threading.Event()
        self._fundamental_data_error: Optional[str] = None

        # News bulletins
        self._news_bulletins: List[DictAny] = []
        self._news_bulletins_event = threading.Event()

        # Order status map
        self._order_status_map: Dict[int, DictAny] = {}
        self._order_status_event = threading.Event()

    # ----------------- Utility methods -----------------------
    def _get_req_id(self) -> int:
        """Return a unique request id in a thread-safe manner."""
        with self._reqid_lock:
            self._next_req_id_val += 1
            return self._next_req_id_val

    # ---------------- Context manager ------------------------
    def __enter__(self) -> "IB":
        """Enter context manager and connect to IB (default host/port/clientId)."""
        if not self.connect_client():
            raise ConnectionError("Failed to connect to IB")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Disconnect when exiting the context manager."""
        self.disconnect_client()
        return False  # don't suppress exceptions

    # ---------------- Connection management ------------------
    def nextValidId(self, orderId: int) -> None:
        """EWrapper callback - signals successful connection."""
        self.connected = True
        logger.info("Received nextValidId; connection established (orderId=%s)", orderId)

    def connectAck(self) -> None:
        """EWrapper callback - connection acknowledged (API >= v10.0)."""
        logger.info("Connection acknowledged by IB")

    def connectionClosed(self) -> None:
        """EWrapper callback - connection closed."""
        self.connected = False
        logger.info("IB connection closed")

    def connect_client(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> bool:
        """
        Connect to the IB Gateway / TWS and start the API thread.

        Returns True if connected within timeout (5s), else False.
        """
        logger.info("Connecting to IB at %s:%d (clientId=%s)...", host, port, client_id)
        try:
            self.connect(host, port, client_id)
        except Exception as e:
            logger.info("Connect error: %s", e)
            return False

        # Start socket thread
        self.api_thread = threading.Thread(target=self._run_socket, daemon=True)
        self.api_thread.start()

        # Wait a short while for nextValidId
        timeout = 5.0
        start = time.time()
        while not self.connected and (time.time() - start) < timeout:
            time.sleep(0.05)

        if not self.connected:
            logger.info("Failed to connect within timeout")
            return False

        logger.info("Connected successfully")
        return True

    def _run_socket(self) -> None:
        """Internal target for the background socket thread."""
        try:
            self.run()
        except Exception as exc:
            logger.info("Socket thread error: %s", exc)

    def disconnect_client(self) -> None:
        """Disconnect the client and join socket thread where appropriate."""
        if self.connected:
            logger.info("Disconnecting from IB...")
            try:
                super().disconnect()
            except Exception as e:
                logger.info("Disconnect exception: %s", e)

            # allow a small grace period
            timeout = 3.0
            start = time.time()
            while self.connected and (time.time() - start) < timeout:
                time.sleep(0.05)

        # join thread if needed
        if self.api_thread and self.api_thread.is_alive():
            if threading.current_thread() is not self.api_thread:
                self.api_thread.join(timeout=2.0)

        if not self.connected:
            logger.info("Disconnected")

    def is_connected(self) -> bool:
        """Return connection state."""
        return self.connected

    # ----------------- Synchronous get functions -----------------

    # 1) get_historical_data (already in your wrapper, preserved with types)
    def get_historical_data(
        self,
        contract: Contract,
        endDateTime: str = "",
        durationStr: str = "1 D",
        barSizeSetting: str = "1 min",
        whatToShow: str = "TRADES",
        useRTH: int = 1,
        formatDate: int = 1,
        keepUpToDate: bool = False,
        chartOptions: Optional[List[Any]] = None,
        timeout: float = 10.0,
    ) -> pd.DataFrame:
        """
        Request historical bars and return a pandas.DataFrame.

        Returns DataFrame indexed by datetime with columns: open, high, low, close, volume.
        On timeout or error returns an empty DataFrame.
        """
        self._historical_data = []
        self._historical_error = None
        self._historical_data_event.clear()

        reqId = self._get_req_id()
        try:
            self.reqHistoricalData(
                reqId,
                contract,
                endDateTime,
                durationStr,
                barSizeSetting,
                whatToShow,
                useRTH,
                formatDate,
                keepUpToDate,
                chartOptions or [],
            )
        except Exception as e:
            logger.info("reqHistoricalData error: %s", e)
            return pd.DataFrame()

        if not self._historical_data_event.wait(timeout=timeout):
            logger.info("'GET HISTORICAL DATA' - TIMEOUT")
            return pd.DataFrame()

        if self._historical_error:
            logger.info("'GET HISTORICAL DATA' - ERROR: %s", self._historical_error)
            return pd.DataFrame()

        df = pd.DataFrame(self._historical_data, columns=["date", "open", "high", "low", "close", "volume"])
        if not df.empty:
            df.set_index("date", inplace=True)
            df.index = pd.to_datetime(df.index)
        return df

    # 2) get_executions
    def get_executions(self, executionFilter: Optional[Any] = None, timeout: float = 10.0) -> List[DictAny]:
        """
        Request executions synchronously; returns list of execution dicts.
        """
        self._executions = []
        self._executions_error = None
        self._executions_event.clear()

        reqId = self._get_req_id()

        if executionFilter is None:
            # import inside to avoid module-level dependency in some test contexts
            from ibapi.execution import ExecutionFilter

            executionFilter = ExecutionFilter()

        try:
            self.reqExecutions(reqId, executionFilter)
        except Exception as e:
            logger.info("reqExecutions error: %s", e)
            return []

        if not self._executions_event.wait(timeout=timeout):
            logger.info("'GET EXECUTIONS' - TIMEOUT")
            return []

        if self._executions_error:
            logger.info("'GET EXECUTIONS' - ERROR: %s", self._executions_error)
            return []

        return self._executions

    # 3) get_last_price
    def get_last_price(self, contract: Contract, timeout: float = 5.0) -> Optional[float]:
        """
        Request a one-shot market data snapshot (reqMktData snapshot=True) and return
        the most recent trade price (float). If unavailable, returns None.
        """
        reqId = self._get_req_id()
        ev = threading.Event()
        self._mktdata_events[reqId] = ev
        # initialize with None values
        self._mktdata[reqId] = {"last": None, "bid": None, "ask": None, "last_size": None, "last_tick": None}

        try:
            # snapshot=True for one-shot (non-streaming)
            self.reqMktData(reqId, contract, "", True, False, [])
        except Exception as e:
            logger.info("reqMktData error: %s", e)
            ev.set()  # ensure we don't block
            # cleanup
            self._mktdata_events.pop(reqId, None)
            self._mktdata.pop(reqId, None)
            return None

        if not ev.wait(timeout=timeout):
            logger.info("'GET LAST PRICE' - TIMEOUT for reqId=%s", reqId)
            try:
                self.cancelMktData(reqId)
            except Exception:
                pass
            self._mktdata_events.pop(reqId, None)
            self._mktdata.pop(reqId, None)
            return None

        data = self._mktdata.pop(reqId, None)
        self._mktdata_events.pop(reqId, None)

        if data is None:
            return None

        last = data.get("last")
        bid = data.get("bid")
        ask = data.get("ask")

        try:
            # prefer last > 0
            if last is not None and float(last) > 0:
                return float(last)
            if bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0:
                return float((float(bid) + float(ask)) / 2.0)
            if bid is not None and float(bid) > 0:
                return float(bid)
            if ask is not None and float(ask) > 0:
                return float(ask)
        except Exception:
            # fallback to None
            return None

        return None

    # 4) get_market_snapshot (returns dict)
    def get_market_snapshot(self, contract: Contract, timeout: float = 5.0) -> DictAny:
        """
        Request a snapshot market data payload and return a dict with keys:
        'last', 'bid', 'ask', 'last_size', 'last_tick'. On timeout returns {}.
        """
        reqId = self._get_req_id()
        ev = threading.Event()
        self._mktdata_events[reqId] = ev
        self._mktdata[reqId] = {"last": None, "bid": None, "ask": None, "last_size": None, "last_tick": None}

        try:
            self.reqMktData(reqId, contract, "", True, False, [])
        except Exception as e:
            logger.info("reqMktData error: %s", e)
            ev.set()
            self._mktdata_events.pop(reqId, None)
            self._mktdata.pop(reqId, None)
            return {}

        if not ev.wait(timeout=timeout):
            logger.info("'GET MARKET SNAPSHOT' - TIMEOUT for reqId=%s", reqId)
            try:
                self.cancelMktData(reqId)
            except Exception:
                pass
            self._mktdata_events.pop(reqId, None)
            self._mktdata.pop(reqId, None)
            return {}

        data = self._mktdata.pop(reqId, {})
        self._mktdata_events.pop(reqId, None)
        return data

    # 5) get_realtime_bars
    def get_realtime_bars(self, contract: Contract, whatToShow: str = "TRADES", useRTH: int = 0, timeout: float = 5.0) -> pd.DataFrame:
        """
        Request realtime bars via reqRealTimeBars, return a DataFrame containing the
        first bar received. On timeout returns empty DataFrame.
        """
        reqId = self._get_req_id()
        ev = threading.Event()
        self._realtime_bars_events[reqId] = ev
        self._realtime_bars[reqId] = []

        try:
            # Many ibapi versions expect barSize (int) e.g. 5
            self.reqRealTimeBars(reqId, contract, 5, whatToShow, useRTH, [])
        except Exception as e:
            logger.info("reqRealTimeBars error: %s", e)
            ev.set()
            self._realtime_bars_events.pop(reqId, None)
            self._realtime_bars.pop(reqId, None)
            return pd.DataFrame()

        if not ev.wait(timeout=timeout):
            logger.info("'GET REALTIME BARS' - TIMEOUT for reqId=%s", reqId)
            try:
                self.cancelRealTimeBars(reqId)
            except Exception:
                pass
            self._realtime_bars_events.pop(reqId, None)
            self._realtime_bars.pop(reqId, None)
            return pd.DataFrame()

        bars = self._realtime_bars.pop(reqId, [])
        self._realtime_bars_events.pop(reqId, None)

        if not bars:
            return pd.DataFrame()

        cols = ["time", "open", "high", "low", "close", "volume", "wap", "count"]
        df = pd.DataFrame(bars, columns=cols)
        # convert epoch seconds to datetime if numeric
        try:
            df["time"] = pd.to_datetime(df["time"], unit="s", errors="coerce")
        except Exception:
            df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df.set_index("time", inplace=True)
        return df

    # 6) get_positions
    def get_positions(self, timeout: float = 10.0) -> List[DictAny]:
        """
        Request positions (reqPositions), returns list of dicts:
        {account, contract, position, avgCost}
        """
        self._positions = []
        self._positions_error = None
        self._positions_event.clear()

        try:
            self.reqPositions()
        except Exception as e:
            logger.info("reqPositions error: %s", e)
            return []

        if not self._positions_event.wait(timeout=timeout):
            logger.info("'GET POSITIONS' - TIMEOUT")
            return []

        if self._positions_error:
            logger.info("'GET POSITIONS' - ERROR: %s", self._positions_error)
            return []

        return self._positions

    # 7) get_open_orders
    def get_open_orders(self, timeout: float = 10.0) -> List[DictAny]:
        """
        Request open orders (reqOpenOrders) and return a list of dicts with keys:
        orderId, contract, order, orderState.
        """
        self._open_orders = []
        self._open_orders_error = None
        self._open_orders_event.clear()

        try:
            # Use reqOpenOrders for this client
            self.reqOpenOrders()
        except Exception as e:
            logger.info("reqOpenOrders error: %s", e)
            return []

        if not self._open_orders_event.wait(timeout=timeout):
            logger.info("'GET OPEN ORDERS' - TIMEOUT")
            return []

        if self._open_orders_error:
            logger.info("'GET OPEN ORDERS' - ERROR: %s", self._open_orders_error)
            return []

        return self._open_orders

    # 8) get_account_summary
    def get_account_summary(self, group: str = "All", tags: Optional[str] = None, timeout: float = 10.0) -> pd.DataFrame:
        """
        Request account summary (reqAccountSummary). Returns a DataFrame with columns:
        reqId, account, tag, value, currency. On timeout/error returns empty DataFrame.
        """
        if tags is None:
            tags = "NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower"

        self._account_summary = []
        self._account_summary_error = None
        self._account_summary_event.clear()

        reqId = self._get_req_id()
        try:
            self.reqAccountSummary(reqId, group, tags)
        except Exception as e:
            logger.info("reqAccountSummary error: %s", e)
            return pd.DataFrame()

        if not self._account_summary_event.wait(timeout=timeout):
            logger.info("'GET ACCOUNT SUMMARY' - TIMEOUT")
            try:
                self.cancelAccountSummary(reqId)
            except Exception:
                pass
            return pd.DataFrame()

        if self._account_summary_error:
            logger.info("'GET ACCOUNT SUMMARY' - ERROR: %s", self._account_summary_error)
            try:
                self.cancelAccountSummary(reqId)
            except Exception:
                pass
            return pd.DataFrame()

        if not self._account_summary:
            return pd.DataFrame()

        df = pd.DataFrame(self._account_summary, columns=["reqId", "account", "tag", "value", "currency"])
        return df

    # 9) get_portfolio (reqAccountUpdates snapshot)
    def get_portfolio(self, account: str = "", timeout: float = 10.0) -> List[DictAny]:
        """
        Subscribe briefly to account updates (reqAccountUpdates) to obtain a portfolio snapshot.
        Returns list of updatePortfolio dicts.
        """
        self._portfolio = []
        self._portfolio_error = None
        self._portfolio_event.clear()
        self._account_download_end_event.clear()

        try:
            # Subscribe
            self.reqAccountUpdates(True, account)
        except Exception as e:
            logger.info("reqAccountUpdates error: %s", e)
            return []

        # Wait until accountDownloadEnd/accountDownloadEnd callback occurs
        if not self._account_download_end_event.wait(timeout=timeout):
            logger.info("'GET PORTFOLIO' - TIMEOUT")
            try:
                self.reqAccountUpdates(False, account)
            except Exception:
                pass
            return []

        # Unsubscribe
        try:
            self.reqAccountUpdates(False, account)
        except Exception:
            pass

        return self._portfolio

    # 10) get_order_status
    def get_order_status(self, order_id: int, timeout: float = 5.0) -> Optional[DictAny]:
        """
        Retrieve latest known order status for a given orderId.
        Returns dict (or None if unknown).
        """
        # Clear event and then request open orders to refresh statuses
        self._order_status_event.clear()

        try:
            self.reqOpenOrders()
        except Exception as e:
            logger.info("reqOpenOrders error while fetching order status: %s", e)
            return None

        # Wait briefly for orderStatus callbacks to arrive
        self._order_status_event.wait(timeout=timeout)
        return self._order_status_map.get(int(order_id))

    # 11) get_contract_details
    def get_contract_details(self, contract: Contract, timeout: float = 10.0) -> List[DictAny]:
        """
        Request contract details (reqContractDetails) and return list of dicts containing raw contractDetails.
        """
        self._contract_details = []
        self._contract_details_error = None
        self._contract_details_event.clear()

        reqId = self._get_req_id()
        try:
            self.reqContractDetails(reqId, contract)
        except Exception as e:
            logger.info("reqContractDetails error: %s", e)
            return []

        if not self._contract_details_event.wait(timeout=timeout):
            logger.info("'GET CONTRACT DETAILS' - TIMEOUT")
            return []

        if self._contract_details_error:
            logger.info("'GET CONTRACT DETAILS' - ERROR: %s", self._contract_details_error)
            return []

        return self._contract_details

    # 12) get_historical_ticks
    def get_historical_ticks(
        self,
        contract: Contract,
        startDateTime: Optional[str] = None,
        endDateTime: Optional[str] = None,
        numberOfTicks: int = 1000,
        whatToShow: str = "TRADES",
        useRth: int = 1,
        timeout: float = 10.0,
    ) -> List[DictAny]:
        """
        Request historical ticks (reqHistoricalTicks) and return list of tick dicts.
        On timeout/error returns [].
        """
        self._historical_ticks = []
        self._historical_ticks_error = None
        self._historical_ticks_event.clear()

        reqId = self._get_req_id()
        try:
            # Some versions accept ignoreSize or additional options; pass an empty list for options to be safe
            self.reqHistoricalTicks(reqId, contract, startDateTime or "", endDateTime or "", numberOfTicks, whatToShow, useRth, [])
        except Exception as e:
            logger.info("reqHistoricalTicks error: %s", e)
            return []

        if not self._historical_ticks_event.wait(timeout=timeout):
            logger.info("'GET HISTORICAL TICKS' - TIMEOUT")
            return []

        if self._historical_ticks_error:
            logger.info("'GET HISTORICAL TICKS' - ERROR: %s", self._historical_ticks_error)
            return []

        return self._historical_ticks

    # Additional: get_news_bulletins
    def get_news_bulletins(self, timeout: float = 5.0) -> List[DictAny]:
        """
        Subscribe to news bulletins briefly and return any received bulletins.
        This is best-effort and may return an empty list.
        """
        self._news_bulletins = []
        self._news_bulletins_event.clear()

        try:
            self.reqNewsBulletins(True)
        except Exception as e:
            logger.info("reqNewsBulletins error: %s", e)
            return []

        # wait up to timeout for any bulletins
        self._news_bulletins_event.wait(timeout=timeout)

        try:
            self.cancelNewsBulletins()
        except Exception:
            pass

        return self._news_bulletins

    # Additional: get_fundamental_data
    def get_fundamental_data(self, contract: Contract, reportType: str = "ReportSnapshot", timeout: float = 10.0) -> Optional[str]:
        """
        Request fundamental data (reqFundamentalData) and return the returned string (XML/text).
        On timeout or error returns None.
        """
        self._fundamental_data = {}
        self._fundamental_data_error = None
        self._fundamental_data_event.clear()

        reqId = self._get_req_id()
        try:
            self.reqFundamentalData(reqId, contract, reportType, [])
        except Exception as e:
            logger.info("reqFundamentalData error: %s", e)
            return None

        if not self._fundamental_data_event.wait(timeout=timeout):
            logger.info("'GET FUNDAMENTAL DATA' - TIMEOUT")
            return None

        if self._fundamental_data_error:
            logger.info("'GET FUNDAMENTAL DATA' - ERROR: %s", self._fundamental_data_error)
            return None

        return self._fundamental_data.get(reqId)

    # -------------------- Callback handlers --------------------

    # Historical data
    def historicalData(self, reqId: int, bar: Any) -> None:
        """EWrapper callback: called per historical bar (bar has date/open/high/low/close/volume)."""
        self._historical_data.append([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """EWrapper callback: end of historical data stream."""
        self._historical_data_event.set()

    # Executions
    def execDetails(self, reqId: int, contract: Contract, execution: Any) -> None:
        exec_dict = {
            "reqId": reqId,
            "contract": contract,
            "execution": execution,
            "orderId": getattr(execution, "orderId", None),
            "clientId": getattr(execution, "clientId", None),
            "execId": getattr(execution, "execId", None),
            "time": getattr(execution, "time", None),
            "acctNumber": getattr(execution, "acctNumber", None),
            "exchange": getattr(execution, "exchange", None),
            "side": getattr(execution, "side", None),
            "shares": getattr(execution, "shares", None),
            "price": getattr(execution, "price", None),
            "permId": getattr(execution, "permId", None),
            "liquidation": getattr(execution, "liquidation", None),
            "cumQty": getattr(execution, "cumQty", None),
            "avgPrice": getattr(execution, "avgPrice", None),
            "orderRef": getattr(execution, "orderRef", None),
            "evRule": getattr(execution, "evRule", None),
            "evMultiplier": getattr(execution, "evMultiplier", None),
            "modelCode": getattr(execution, "modelCode", None),
            "lastLiquidity": getattr(execution, "lastLiquidity", None),
        }
        self._executions.append(exec_dict)

    def execDetailsEnd(self, reqId: int) -> None:
        """EWrapper callback: all execution details received."""
        self._executions_event.set()

    # Market data callbacks
    def tickPrice(self, reqId: int, tickType: int, price: float, attrib: Any) -> None:
        """
        EWrapper callback: tickPrice. We capture last/bid/ask heuristically.
        tickType mapping can vary by API version; common:
        1 = bid, 2 = ask, 4 = last
        """
        if reqId not in self._mktdata:
            return

        rec = self._mktdata.get(reqId, {})
        try:
            p = float(price)
        except Exception:
            p = None

        if p is not None and p != 0.0:
            # if last not set, set it by default
            if rec.get("last") is None:
                rec["last"] = p
                rec["last_tick"] = tickType
            if tickType == 1:
                rec["bid"] = p
            elif tickType == 2:
                rec["ask"] = p
            elif tickType == 4:
                rec["last"] = p

        self._mktdata[reqId] = rec

    def tickSize(self, reqId: int, tickType: int, size: int) -> None:
        """EWrapper callback: tickSize - capture last trade size if available."""
        if reqId not in self._mktdata:
            return
        rec = self._mktdata.get(reqId, {})
        try:
            s = int(size)
        except Exception:
            s = None
        if s:
            rec["last_size"] = s
        self._mktdata[reqId] = rec

    def tickString(self, reqId: int, tickType: int, value: str) -> None:
        """Some tick fields come as strings; not used by snapshot logic presently."""
        return

    def tickGeneric(self, reqId: int, tickType: int, value: float) -> None:
        """Generic tick - ignored for snapshot logic."""
        return

    def tickSnapshotEnd(self, reqId: int) -> None:
        """EWrapper callback: snapshot request completed."""
        ev = self._mktdata_events.get(reqId)
        if ev:
            ev.set()

    # Realtime bars
    def realtimeBar(self, reqId: int, time_: int, open_: float, high: float, low: float, close: float, volume: int, wap: float, count: int) -> None:
        """
        EWrapper callback: realtimeBar. Append the bar and signal the waiting caller (first bar).
        """
        if reqId not in self._realtime_bars:
            return
        self._realtime_bars[reqId].append([time_, open_, high, low, close, volume, wap, count])
        ev = self._realtime_bars_events.get(reqId)
        if ev:
            ev.set()
            # cancel to stop streaming further bars
            try:
                self.cancelRealTimeBars(reqId)
            except Exception:
                pass

    # Positions
    def position(self, account: str, contract: Contract, position: float, avgCost: float) -> None:
        rec = {"account": account, "contract": contract, "position": position, "avgCost": avgCost}
        self._positions.append(rec)

    def positionEnd(self) -> None:
        self._positions_event.set()

    # Open orders
    def openOrder(self, orderId: int, contract: Contract, order: Any, orderState: Any) -> None:
        od = {"orderId": orderId, "contract": contract, "order": order, "orderState": orderState}
        self._open_orders.append(od)

    def openOrderEnd(self) -> None:
        self._open_orders_event.set()

    # Account summary
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:
        self._account_summary.append([reqId, account, tag, value, currency])

    def accountSummaryEnd(self, reqId: int) -> None:
        self._account_summary_event.set()

    # Portfolio updates
    def updatePortfolio(self, contract: Contract, position: float, marketPrice: float, marketValue: float, averageCost: float, unrealizedPNL: float, realizedPNL: float, accountName: str) -> None:
        rec = {
            "contract": contract,
            "position": position,
            "marketPrice": marketPrice,
            "marketValue": marketValue,
            "averageCost": averageCost,
            "unrealizedPNL": unrealizedPNL,
            "realizedPNL": realizedPNL,
            "accountName": accountName,
        }
        self._portfolio.append(rec)

    def accountDownloadEnd(self, accountName: str) -> None:
        self._account_download_end_event.set()

    def updateAccountValue(self, key: str, val: str, currency: str, accountName: str) -> None:
        # could store account value updates if desired
        return

    # Contract details
    def contractDetails(self, reqId: int, contractDetails: Any) -> None:
        self._contract_details.append({"reqId": reqId, "contractDetails": contractDetails})

    def contractDetailsEnd(self, reqId: int) -> None:
        self._contract_details_event.set()

    # Historical ticks
    def historicalTicks(self, reqId: int, ticks: List[Any], done: bool) -> None:
        try:
            for t in ticks:
                if hasattr(t, "__dict__"):
                    self._historical_ticks.append(t.__dict__)
                else:
                    self._historical_ticks.append({"tick": repr(t)})
        except Exception as e:
            self._historical_ticks_error = str(e)
        if done:
            self._historical_ticks_event.set()

    def historicalTicksBidAsk(self, reqId: int, ticks: List[Any], done: bool) -> None:
        self.historicalTicks(reqId, ticks, done)

    def historicalTicksLast(self, reqId: int, ticks: List[Any], done: bool) -> None:
        self.historicalTicks(reqId, ticks, done)

    # Fundamental data
    def fundamentalData(self, reqId: int, data: str) -> None:
        self._fundamental_data[reqId] = data
        self._fundamental_data_event.set()

    def fundamentalDataEnd(self, reqId: int) -> None:
        self._fundamental_data_event.set()

    # News bulletins
    def updateNewsBulletin(self, msgId: int, msgType: int, message: str, origExchange: str) -> None:
        rec = {"msgId": msgId, "msgType": msgType, "message": message, "exchange": origExchange}
        self._news_bulletins.append(rec)
        self._news_bulletins_event.set()

    # Order status
    def orderStatus(self, orderId: int, status: str, filled: float, remaining: float, avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float, clientId: int, whyHeld: str, mktCapPrice: float) -> None:
        rec = {
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "permId": permId,
            "parentId": parentId,
            "lastFillPrice": lastFillPrice,
            "clientId": clientId,
            "whyHeld": whyHeld,
            "mktCapPrice": mktCapPrice,
        }
        self._order_status_map[int(orderId)] = rec
        self._order_status_event.set()

    # -------------------- Error handler --------------------
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        """
        Centralized error handler. Follows existing pattern: log error and map to
        any waiting events for synchronous wrappers.
        """
        logger.info("Error %s (reqId=%s): %s", errorCode, reqId, errorString)
        if errorCode in (502, 504):
            # connection issues
            self.connected = False

        msg = f"{errorCode}: {errorString}"
        # populate possible waiting error slots
        try:
            if not self._executions_event.is_set():
                self._executions_error = msg
                self._executions_event.set()
        except Exception:
            pass
        try:
            if not self._historical_data_event.is_set():
                self._historical_error = msg
                self._historical_data_event.set()
        except Exception:
            pass
        try:
            if not self._contract_details_event.is_set():
                self._contract_details_error = msg
                self._contract_details_event.set()
        except Exception:
            pass
        try:
            if not self._historical_ticks_event.is_set():
                self._historical_ticks_error = msg
                self._historical_ticks_event.set()
        except Exception:
            pass
        try:
            if not self._fundamental_data_event.is_set():
                self._fundamental_data_error = msg
                self._fundamental_data_event.set()
        except Exception:
            pass
        try:
            if not self._open_orders_event.is_set():
                self._open_orders_error = msg
                self._open_orders_event.set()
        except Exception:
            pass
        try:
            if not self._positions_event.is_set():
                self._positions_error = msg
                self._positions_event.set()
        except Exception:
            pass
        try:
            if not self._account_summary_event.is_set():
                self._account_summary_error = msg
                self._account_summary_event.set()
        except Exception:
            pass

# ----------------- End of IB class -------------------------


# ----------------- Example tests (live) ---------------------
def _make_demo_equity_contract(symbol: str = "AAPL") -> Contract:
    """Helper to create a simple stock contract on SMART/NYSE with USD currency."""
    c = Contract()
    c.symbol = symbol
    c.secType = "STK"
    c.exchange = "SMART"
    c.currency = "USD"
    return c


if __name__ == "__main__":
    """
    Live test harness that connects to local TWS/Gateway (127.0.0.1:7497) and runs
    all 12 get_... functions in sequence.

    IMPORTANT:
    - This will make real API calls to your IB instance.
    - Ensure TWS/Gateway is running and API access is enabled (paper trading recommended).
    """
    import sys

    # Configure root logger at INFO
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.setLevel(logging.INFO)

    contract = _make_demo_equity_contract("AAPL")

    with IB() as ib:
        # Ensure connection parameters (host/port/clientId) are correct before running
        # For safety we already used the default connect_client during __enter__

        logger.info("Starting live tests for IB synchronous wrapper...")

        # 1) historical data
        try:
            logger.info("Testing get_historical_data...")
            df_hist = ib.get_historical_data(contract, durationStr="1 D", barSizeSetting="5 mins", timeout=10)
            logger.info("Historical bars rows: %s", len(df_hist))
        except Exception as e:
            logger.info("get_historical_data exception: %s", e)

        # 2) executions
        try:
            logger.info("Testing get_executions...")
            execs = ib.get_executions(timeout=5)
            logger.info("Executions returned: %s", len(execs))
        except Exception as e:
            logger.info("get_executions exception: %s", e)

        # 3) last price
        try:
            logger.info("Testing get_last_price...")
            price = ib.get_last_price(contract, timeout=5)
            logger.info("Last price: %s", price)
        except Exception as e:
            logger.info("get_last_price exception: %s", e)

        # 4) market snapshot
        try:
            logger.info("Testing get_market_snapshot...")
            snap = ib.get_market_snapshot(contract, timeout=5)
            logger.info("Market snapshot: %s", snap)
        except Exception as e:
            logger.info("get_market_snapshot exception: %s", e)

        # 5) realtime bars
        try:
            logger.info("Testing get_realtime_bars...")
            rt = ib.get_realtime_bars(contract, timeout=7)
            logger.info("Realtime bars rows: %s", len(rt))
        except Exception as e:
            logger.info("get_realtime_bars exception: %s", e)

        # 6) positions
        try:
            logger.info("Testing get_positions...")
            positions = ib.get_positions(timeout=5)
            logger.info("Positions returned: %s", len(positions))
        except Exception as e:
            logger.info("get_positions exception: %s", e)

        # 7) open orders
        try:
            logger.info("Testing get_open_orders...")
            opens = ib.get_open_orders(timeout=5)
            logger.info("Open orders returned: %s", len(opens))
        except Exception as e:
            logger.info("get_open_orders exception: %s", e)

        # 8) account summary
        try:
            logger.info("Testing get_account_summary...")
            df_acc = ib.get_account_summary(timeout=5)
            logger.info("Account summary rows: %s", len(df_acc))
        except Exception as e:
            logger.info("get_account_summary exception: %s", e)

        # 9) portfolio snapshot
        try:
            logger.info("Testing get_portfolio...")
            portfolio = ib.get_portfolio(timeout=7)
            logger.info("Portfolio items: %s", len(portfolio))
        except Exception as e:
            logger.info("get_portfolio exception: %s", e)

        # 10) order status (example uses orderId=1)
        try:
            logger.info("Testing get_order_status for orderId=1...")
            order_status = ib.get_order_status(1, timeout=5)
            logger.info("Order status (orderId=1): %s", order_status)
        except Exception as e:
            logger.info("get_order_status exception: %s", e)

        # 11) contract details
        try:
            logger.info("Testing get_contract_details...")
            cd = ib.get_contract_details(contract, timeout=5)
            logger.info("Contract details entries: %s", len(cd))
        except Exception as e:
            logger.info("get_contract_details exception: %s", e)

        # 12) historical ticks
        try:
            logger.info("Testing get_historical_ticks (may return empty) ...")
            ticks = ib.get_historical_ticks(contract, numberOfTicks=10, timeout=7)
            logger.info("Historical ticks returned: %s", len(ticks))
        except Exception as e:
            logger.info("get_historical_ticks exception: %s", e)

        # News bulletins
        try:
            logger.info("Testing get_news_bulletins...")
            news = ib.get_news_bulletins(timeout=3)
            logger.info("News bulletins returned: %s", len(news))
        except Exception as e:
            logger.info("get_news_bulletins exception: %s", e)

        # Fundamental data
        try:
            logger.info("Testing get_fundamental_data...")
            fdata = ib.get_fundamental_data(contract, reportType="ReportSnapshot", timeout=7)
            if fdata:
                logger.info("Fundamental data length: %s", len(fdata))
            else:
                logger.info("No fundamental data returned")
        except Exception as e:
            logger.info("get_fundamental_data exception: %s", e)

        logger.info("Live tests completed.")

    # end of context manager -> automatically disconnected
