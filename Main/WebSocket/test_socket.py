# -*- coding: utf-8 -*-
"""
Created on Mon Dec  2 16:34:06 2019

@author: mdamelio
"""

import websocket as _websocket
import json as _json

global rawdata

def on_message(ws, message):
    """ 
    ### Procesamiento del Mensaje de WebSocket de Market Data
    """
    global rawdata
    
    rawdata = _json.loads(message)   
    print(rawdata)
    
def on_error(ws, error):
    print(error)

def on_close(ws, error=None):
    print(error)
    print("### closed ### ")

def connectToSocket():
    print('connectToSocket - Data')
    # websocket.enableTrace(True)
    global ws_data
    ws_data = _websocket.WebSocketApp("ws://localhost:8080",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    ws_data.run_forever()
    
connectToSocket()