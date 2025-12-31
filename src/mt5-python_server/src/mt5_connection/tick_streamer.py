"""
Class for the tick streaming operation from MT5
"""
import json
import os
import threading
import time

from database import Database
from utils.time_utils import print_with_datetime


class MT5TickStreamer:
    """
    MT5 terminal connection for tick streaming
    """

    def __init__(self, socket, asset, stop_char='\n',
                 verbose=False, console_lock=None, db=None):
        self.__socket = socket
        self.__asset = asset
        self.__stop_char = stop_char
        self.__verbose = verbose
        self.__console_lock = console_lock
        # Use provided database instance or create new one (for backward compatibility)
        self.__db = db if db is not None else Database()
        
        # Tick buffering configuration
        self.__batch_size = int(os.getenv('TICK_BATCH_SIZE', '50'))
        self.__batch_interval = float(os.getenv('TICK_BATCH_INTERVAL', '2.0'))
        self.__buffer_max_size = int(os.getenv('TICK_BUFFER_MAX_SIZE', '200'))
        
        # Thread-safe tick buffer
        self.__tick_buffer = []
        self.__buffer_lock = threading.Lock()
        self.__flush_timer = None
        self.__shutdown_flag = threading.Event()
        
        # Start periodic flush timer
        self.__start_flush_timer()

    def __start_flush_timer(self):
        """Start the periodic flush timer"""
        if self.__flush_timer:
            self.__flush_timer.cancel()
        
        if not self.__shutdown_flag.is_set():
            self.__flush_timer = threading.Timer(self.__batch_interval, self.__flush_buffer)
            self.__flush_timer.daemon = True
            self.__flush_timer.start()
    
    def __add_tick_to_buffer(self, symbol, date_time, ask, bid):
        """
        Add a tick to the buffer and flush if needed
        
        :param symbol: Currency pair symbol
        :param date_time: Tick datetime
        :param ask: Ask price
        :param bid: Bid price
        """
        with self.__buffer_lock:
            self.__tick_buffer.append((symbol, date_time, ask, bid))
            
            # Flush if buffer reaches max size
            if len(self.__tick_buffer) >= self.__buffer_max_size:
                self.__flush_buffer_internal()
            # Flush if batch size reached
            elif len(self.__tick_buffer) >= self.__batch_size:
                self.__flush_buffer_internal()
    
    def __flush_buffer_internal(self):
        """Internal flush method (must be called with buffer_lock held)"""
        if not self.__tick_buffer:
            return
        
        ticks_to_flush = self.__tick_buffer.copy()
        self.__tick_buffer.clear()
        
        # Release lock before database operation
        threading.Thread(
            target=self.__flush_ticks_to_db,
            args=(ticks_to_flush,),
            daemon=True
        ).start()
    
    def __flush_buffer(self):
        """Flush buffer based on timer (called periodically)"""
        with self.__buffer_lock:
            self.__flush_buffer_internal()
        
        # Restart timer for next flush
        self.__start_flush_timer()
    
    def __flush_ticks_to_db(self, ticks):
        """
        Flush ticks to database in batch
        
        :param ticks: List of (symbol, date_time, ask, bid) tuples
        """
        if not ticks:
            return
        
        try:
            result = self.__db.insert_forex_ticks_batch(ticks)
            if self.__verbose and result > 0:
                with self.__console_lock:
                    print_with_datetime(f"Flushed {result} ticks to database")
        except Exception as e:
            print_with_datetime(f"Error flushing ticks to database: {e}")
            # On error, try inserting individually as fallback
            for symbol, date_time, ask, bid in ticks:
                try:
                    self.__db.insert_forex_tick(symbol, date_time, ask, bid)
                except Exception as e2:
                    print_with_datetime(f"Error inserting individual tick: {e2}")
    
    def receive_tick(self):
        """
        Receive tick from mt5 client
        and store them in the database buffer
        """
        cum_data = ''
        try:
            while not self.__shutdown_flag.is_set():
                data = self.__socket.recv(1024).decode("utf-8")

                cum_data += data

                if self.__stop_char in cum_data:
                    final_data = cum_data[:cum_data.index(self.__stop_char)]

                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime(final_data)

                    tick_info = json.loads(final_data)
                    if len(tick_info) == 4:
                        symbol = tick_info['symbol']
                        date_time = tick_info['date_time']
                        ask = tick_info['ask']
                        bid = tick_info['bid']

                        self.__asset.update(bid, ask)
                        # Add to buffer instead of direct insert
                        self.__add_tick_to_buffer(symbol, date_time, ask, bid)
                    else:
                        print_with_datetime(f"Error wrong format of tick. Tick received: {tick_info}")
                    cum_data = ''
        finally:
            # Graceful shutdown: flush remaining ticks
            self.__shutdown_flag.set()
            if self.__flush_timer:
                self.__flush_timer.cancel()
            
            # Flush any remaining ticks
            with self.__buffer_lock:
                if self.__tick_buffer:
                    remaining_ticks = self.__tick_buffer.copy()
                    self.__tick_buffer.clear()
                    self.__flush_ticks_to_db(remaining_ticks)

    def __del__(self):
        """Cleanup on deletion"""
        self.__shutdown_flag.set()
        if self.__flush_timer:
            self.__flush_timer.cancel()
        
        # Flush any remaining ticks
        with self.__buffer_lock:
            if self.__tick_buffer:
                remaining_ticks = self.__tick_buffer.copy()
                self.__tick_buffer.clear()
                self.__flush_ticks_to_db(remaining_ticks)
        
        if self.__socket:
            self.__socket.close()
