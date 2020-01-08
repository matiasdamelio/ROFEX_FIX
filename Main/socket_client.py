# -*- coding: utf-8 -*-
"""
Created on Thu Dec 19 14:45:00 2019

@author: mdamelio
"""

import requests as _requests
import json as _json
import quickfix as fix
import time

base_url = "http://localhost:1234"
       
def getMarketData(entries, symbol):
    
    final_url = "{0}/marketdata".format(base_url)
    params  = _json.dumps({"entries": entries, "symbol": symbol})
    
    response = _requests.request("GET", final_url, data = params, verify = False)
        
    if(response.status_code == 200):
        print(response.json())
        return 0
    else:
        return -1
    
def newOrderSingle(symbol, side, quantity, price, orderType):
    
    final_url = "{0}/newordersingle".format(base_url)
    params  = _json.dumps({"symbol": symbol, "side": side, "quantity": quantity, "price": price, "orderType": orderType})
    
    response = _requests.request("GET", final_url, data = params, verify = False)
        
    if(response.status_code == 200):
        print(response.json())
        return response.json()
    else:
        return -1
    
def orderCancel(orderID, side, quantity, symbol):
    
    final_url = "{0}/ordercancel".format(base_url)
    params  = _json.dumps({"orderID": orderID, "side": side, "quantity": quantity, "symbol": symbol})
    
    response = _requests.request("GET", final_url, data = params, verify = False)
        
    if(response.status_code == 200):
        print(response.json())
        return 0
    else:
        return -1
    
def massCancel(segment):
    
    final_url = "{0}/masscancel".format(base_url)
    params  = _json.dumps({"marketSegment": segment})
        
    response = _requests.request("GET", final_url, data = params, verify = False)
        
    if(response.status_code == 200):
        print(response.json())
        return 0
    else:
        return -1
    
def orderStatus(orderID, symbol, side):
    
    final_url = "{0}/orderstatus".format(base_url)
    params  = _json.dumps({"orderID": orderID, "symbol": symbol, "side": side})
    
    response = _requests.request("GET", final_url, data = params, verify = False)
        
    if(response.status_code == 200):
        print(response.json())
        return 0
    else:
        return -1
    
    
getMarketData(entries = [0,1,'B'], symbol = ['RFX20Dic19','WTIEne20'])
order1 = newOrderSingle(symbol = 'RFX20Dic19', side = fix.Side_BUY, quantity = 1, price = 57400, orderType = fix.OrdType_LIMIT) 
time.sleep(1)
orderCancel(orderID=order1['data']['orderID'], side = order1['data']['side'], quantity = order1['data']['quantity'], symbol = order1['data']['symbol'])

#massCancel(segment='DUAL')
orderStatus(orderID=order1['data']['orderID'], symbol = order1['data']['symbol'], side = order1['data']['side'] )

