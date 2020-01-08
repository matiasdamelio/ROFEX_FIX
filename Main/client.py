# -*- coding: utf-8 -*-
"""
Created on Mon Nov 25 12:23:56 2019

@author: mdamelio
"""

import argparse
import quickfix as fix
from application import Application
from threading import Thread
from getpass import getpass
import time
import signal
import sys

import json
import bottle

def signal_handler(sig, frame):
    fixMain.application.logout()    
    fixMain.initiator.stop()
    sys.exit(0)
                
class main(Thread):
    def __init__(self, config_file, market, user, passwd, account):
        Thread.__init__(self)
        self.config_file = config_file
        self.market = market
        self.user = user
        self.passwd = passwd
        self.account = account
        
        self.settings = fix.SessionSettings(self.config_file)
        self.application = Application(self.market, self.user, self.passwd, self.account)
        self.storefactory = fix.FileStoreFactory(self.settings)
        self.logfactory = fix.FileLogFactory(self.settings)
        self.initiator = fix.SocketInitiator(self.application, self.storefactory, self.settings, self.logfactory)
            
    def run(self):
        self.initiator.start()
        
class bottle_framework(Thread):
    def __init__(self, host, port):
        Thread.__init__(self)
        self.host = host
        self.port = port
        
    def run(self):
        bottle.run(app, host=self.host, port=self.port)

"""
Framework for API Rest
"""

app = bottle.Bottle()

@app.get('/marketdata')
def marketData():
  req_obj = json.loads(bottle.request.body.read())
  fixMain.application.marketDataRequest(entries=req_obj['entries'], symbols=req_obj['symbol'])
  return {'type':'md', 'data':{'symbols': req_obj['symbol'], 'entries':req_obj['entries']}}

@app.get('/newordersingle')
def newOrderSingle():
    req_obj = json.loads(bottle.request.body.read())
    fixMain.application.newOrderSingle(symbol=req_obj['symbol'], side=req_obj['side'], quantity=req_obj['quantity'], 
                                       price=req_obj['price'], orderType=req_obj['orderType'])
    time.sleep(0.3)
    return {'type':'new', 'data':{'symbol':req_obj['symbol'], 'side':req_obj['side'], 'quantity':req_obj['quantity'], 
                                  'price':req_obj['price'], 'orderType':req_obj['orderType'], 'orderID': str(fixMain.application.orderID)}}
    
@app.get('/ordercancel')
def orderCancel():
    req_obj = json.loads(bottle.request.body.read())
    fixMain.application.orderCancelRequest(orderId=req_obj['orderID'], side=req_obj['side'], quantity=req_obj['quantity'], symbol=req_obj['symbol'])
    return {'type':'cancel', 'data':{'symbol':req_obj['symbol'], 'orderID':req_obj['orderID']}}

@app.get('/masscancel')
def massCancel():
    req_obj = json.loads(bottle.request.body.read())
    fixMain.application.orderMassCancelRequest(marketSegment=req_obj['marketSegment'])
    return {'type':'massCancel', 'marketSegment' : req_obj['marketSegment']}

@app.get('/orderstatus')
def orderStatus():
    req_obj = json.loads(bottle.request.body.read())
    fixMain.application.orderStatusRequest(orderId=req_obj['orderID'], symbol=req_obj['symbol'], side=req_obj['side'])
    return {'type':'orderStatus'}

"""
Main
"""

if __name__=='__main__':
    
    parser = argparse.ArgumentParser(description='FIX Client')
    parser.add_argument('file_name', type=str, help='Name of configuration file')
    args = parser.parse_args()
    market = input('Market (i.e. ROFX, BYMA): ')
    user = input('Username (SenderCompID): ')
    passwd = getpass(prompt="Password: ")
    account = input('Cuenta: ')
    fixMain = main(args.file_name, market, user, passwd, account)
    
#    fixMain = main(args.file_name, 'ROFX','juanvillarrueldujovne2989','myopwD3*','REM2989')
    fixMain.daemon = True
    fixMain.start()
    
    # Handler of Ctrl+C Event
    signal.signal(signal.SIGINT, signal_handler)
    
    # Framework for API Rest    
#    bottle.run(app, host='localhost', port=1234)
    bottleFW = bottle_framework(host = 'localhost', port = 1234)
    bottleFW.daemon = True
    bottleFW.start()
    
    time.sleep(3)
    

    
#    fixMain.application.orderStatusRequest(orderId=str(fixMain.application.orderID), symbol='RFX20Dic19', side=fix.Side_BUY)
    
#    fixMain.application.orderCancelReplaceRequest(orderId=str(fixMain.application.orderID), origClOrdId=str(fixMain.application.lastOrderID) ,side=fix.Side_BUY, symbol='RFX20Dic19', orderType=fix.OrdType_LIMIT, quantity= 2, price=48500)
    
#    fixMain.application.orderMassStatusRequest(fix.SecurityStatus_ACTIVE)
    
    
#    fixMain.application.orderMassStatusRequest()
    

    
#    fixMain.application.securityListRequest()
    
#    fixMain.application.securityStatusRequest(subscription=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES)
    
#    fixMain.application.tradeCaptureReportRequest()
    
#    fixMain.application.allocationInstruction(symbol = 'RFX20Mar20', quantity=5, side = fix.Side_BUY)
    
#    time.sleep(3)
    
#    print(fixMain.application.tradeReports)
    
    while 1:
        time.sleep(1)
    
    
    fixMain.application.logout()
    
    fixMain.initiator.stop()
        
    
