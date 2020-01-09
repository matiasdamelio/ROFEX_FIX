# -*- coding: utf-8 -*-
"""
Created on Mon Nov 25 12:27:13 2019

@author: mdamelio
"""

import sys, os
import quickfix as fix
import quickfix50sp2 as fix50
import logging
import texttable
import random
import string
from WebSocket.BroadcasterWebsocketServer import BroadcasterWebsocketServer

sys.path.insert(0, os.path.join(os.path.dirname(sys.path[0]), 'model'))

from logger import setup_logger

__SOH__ = chr(1)

# Logger
setup_logger('FIX', './Logs/message.log')
logfix = logging.getLogger('FIX')

def randomString(stringLength=10):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

class Application(fix.Application):
    """FIX Application"""

    def __init__(self, target, sender, password, account):
        """
        ### Start Application
        
            - Start FIX Session    
            - Open WebSocket in localhost:8080    
        """
        
        super().__init__()
        
        self.senderCompID = sender
        self.targetCompID = target
        self.password = password
        self.account = account
    
        self.server_md = BroadcasterWebsocketServer('', 8080, True)
        self.server_md.start()
        
#        self.server_or = BroadcasterWebsocketServer('', 8081, True)
#        self.server_or.start()

    def onCreate(self, session):
        """
        onCreate is called when quickfix creates a new session.
        A session comes into and remains in existence for the life of the application.
        Sessions exist whether or not a counter party is connected to it.
        As soon as a session is created, you can begin sending messages to it.
        If no one is logged on, the messages will be sent at the time a connection is established with the counterparty.
        """
       
        targetCompID = session.getTargetCompID().getValue()
        try:
            self.sessions[targetCompID] = {}
        except AttributeError:
            self.lastOrderID            = self.account + '-00000000' 
            self.orderID                = 0
            self.sessions               = {}
            self.orders                 = {}
            self.sessions[targetCompID] = {}
            
            self.tradeReports           = {}

        self.sessions[targetCompID]['session']   = session
        self.sessions[targetCompID]['connected'] = False
        self.sessions[targetCompID]['exchID']    = 0
        self.sessions[targetCompID]['execID']    = 0
        
        logfix.info("onCreate, sessionID >> (%s)" %self.sessions[targetCompID]['session'])

    def onLogon(self, session):
        """
        onLogon notifies you when a valid logon has been established with a counter party.
        This is called when a connection has been established and the FIX logon process has completed with both parties exchanging valid logon messages.
        """

        targetCompID = session.getTargetCompID().getValue()
        self.sessions[targetCompID]['connected'] = True
        
        logfix.info("Client (%s) has logged in >>" % targetCompID)

        ## Test Message
        self.testRequest('TEST')
        
    def onLogout(self, session):
        """
        onLogout notifies you when an FIX session is no longer online.
        This could happen during a normal logout exchange or because of a forced termination or a loss of network connection.
        """
        
        targetCompID = session.getTargetCompID().getValue()
        self.sessions[targetCompID]['connected'] = False

        logfix.info("Client (%s) has logged out >>" % targetCompID)

    def toAdmin(self, message, session):
        """
        toAdmin provides you with a peek at the administrative messages that are being sent from your FIX engine
        to the counter party. This is normally not useful for an application however it is provided for any logging
        you may wish to do. Notice that the FIX::Message is not const.
        This allows you to add fields to an adminstrative message before it is sent out.
        """

        msg = message.toString().replace(__SOH__, "|")
        logfix.info("S toAdmin>> (%s)" % msg)

        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_Logon:
            message.getHeader().setField(553, self.senderCompID)
            message.getHeader().setField(554, self.password)
            msg = message.toString().replace(__SOH__, "|")
            logfix.info("S Logon>> (%s)" % msg)

    def fromAdmin(self, message, session):
        """
        fromAdmin notifies you when an administrative message is sent from a counterparty to your FIX engine. This can be usefull for doing extra validation on logon messages like validating passwords.
        Throwing a RejectLogon exception will disconnect the counterparty.
        """
        
        """
        SESSION MESSAGES
        """
        
        ## Message Type = 'h' - Heartbeat
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_Heartbeat:
            self.onMesssage_Heartbeat(message, session)
        ## Message Type = '5' - Logout
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_Logout:
            self.onMessage_Logout(message, session)        
        ## Message Type = '3' - Reject (Session Level)
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_Reject:
            self.onMessage_Reject(message, session)
        
        msg = message.toString().replace(__SOH__, "|")
        logfix.info("R adm>> (%s)" % msg)

    def toApp(self, message, session):
        """
        toApp is a callback for application messages that are being sent to a counterparty.
        If you throw a DoNotSend exception in this function, the application will not send the message.
        This is mostly useful if the application has been asked to resend a message such as an order that is no longer relevant for the current market.
        Messages that are being resent are marked with the PossDupFlag in the header set to true;
        If a DoNotSend exception is thrown and the flag is set to true, a sequence reset will be sent in place of the message.
        If it is set to false, the message will simply not be sent. Notice that the FIX::Message is not const.
        This allows you to add fields to an application message before it is sent out.
        """
        
        ## Message Type = 'j' - Business Message Reject
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_BusinessMessageReject:
            self.onMessage_BusinessMessageReject(message, session)
        
        msg = message.toString().replace(__SOH__, "|")
        logfix.info("S toApp>> (%s)" % msg)

    def fromApp(self, message, session):
        """
        fromApp receives application level request.
        If your application is a sell-side OMS, this is where you will get your new order requests.
        If you were a buy side, you would get your execution reports here.
        If a FieldNotFound exception is thrown,
        the counterparty will receive a reject indicating a conditionally required field is missing.
        The Message class will throw this exception when trying to retrieve a missing field, so you will rarely need the throw this explicitly.
        You can also throw an UnsupportedMessageType exception.
        This will result in the counterparty getting a reject informing them your application cannot process those types of messages.
        An IncorrectTagValue can also be thrown if a field contains a value you do not support.
        """
                
        """
        COMMON MESSSAGES
        """
        
        ## Message Type = 'B' - News
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_News:
            self.onMessage_News(message, session)  
                    
        """
        APPLICATION MESSSAGES
        """
        
        ## Message Type = 'h' - Trading Session Status
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_TradingSessionStatus:
            self.onMessage_TradingSessionStatus(message, session)
        ## Message Type = '9' - Order Cancel Reject
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_OrderCancelReject:
            self.onMessage_OrderCancelReject(message, session)
            self.onMessage(message, session)
        
        ######## EXECUTION REPORT ########
        
        ## Message Type = '8' - ExecutionReport: New
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_NEW:
            self.orderID = self.getValue(message, fix.OrderID())
            print(self.orderID)
            self.onMessage_ExecutionReport_New(message, session)
#            self.onMessage(message, session)
        ## Message Type = '8' - ExecutionReport: Order Canceled
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_CANCELED:
            self.onMessage_ExecutionReport_OrderCanceledResponse(message, session)
#            self.onMessage(message, session)
        ## Message Type = '8' - ExecutionReport: Order Replaced
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_REPLACE:
            self.orderID = self.getValue(message, fix.OrderID())
            self.onMessage_ExecutionReport_OrderReplacedResponse(message, session)
#            self.onMessage(message, session)        
        ## Message Type = '8' - ExecutionReport: Order Filled/Partially Filled
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_TRADE:
            self.onMessage_ExecutionReport_OrderFilledPartiallyFilledResponse(message, session)
#            self.onMessage(message, session)
        ## Message Type = '8' - ExecutionReport: Order Status 
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_ORDER_STATUS:
            self.onMessage_ExecutionReport_OrderStatusResponse(message, session)
#            self.onMessage(message, session)
        ## Message Type = '8' - ExecutionRepor: Reject Message
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_ExecutionReport and self.getValue(message, fix.ExecType()) == fix.ExecType_REJECTED:
            self.onMessage_ExecutionReport_RejectMessageResponse(message, session)
#            self.onMessage(message, session)
            
        ######## MARKET DATA ########            
            
        ## Message Type = 'W' - Market Data Snapshot / Full Refresh
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_MarketDataSnapshotFullRefresh:
            self.onMessage_MarketDataSnapshotFullRefresh(message, session)
        ## Message Type = 'Y' - Market Data Request Reject
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_MarketDataRequestReject:
            self.onMessage_MarketDataRequestReject(message, session)
            
        ######## SECURITY DEFINTION ########       
        ## Message Type = 'y' - Security List
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_SecurityList:     
            self.onMessage_SecurityList(message, session)
        ## Message Type = 'f' - Security Status
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_SecurityStatus:
            self.onMessage_SecurityStatus(message, session)
        
        ######## POST TRADE ########       
        ## Message Type = 'AE' - Trade Capture Report
        if self.getHeaderValue(message, fix.MsgType()) == fix.MsgType_TradeCaptureReport:        
            self.onMessage_TradeCaptureReport(message, session)
    
    """
    Response (onMessage)
    """    
        
    def onMessage(self, message, session):
        """
        onMessage
        
        Print of FIX Message
        """
        msg = message.toString().replace(__SOH__, "|")

        logfix.info("onMessage, R app>> (%s)" % msg)
        
    def onMesssage_Heartbeat(self, message, session):
        """
        onMessage - Heartbeat
        """
        try:
            text = self.getValue(message, fix.TestReqID())
            print('TEST REQUEST:', text)
        except:
            print('HEARTBEAT')
            
    def onMessage_Reject(self, message, session):
        """
        onMessage - Reject - Session Level
        
        Message Type = '3'.
        The FIX Reject message should be issued when a message is received but cannot be properly processed 
        due to a session-level rule violation.
        This message will be sent by the Exchange when a session level error has occurred.
        
        Fields:
            - (35) - MsgType = 3
            - (45) - RefSeqNum = (int)
            - (58) - Text = (string)
            - (371) - RefTagID = (int)
            - (372) - RefMsgType = (string)
            - (373) - SessionRejectReason = (int)        
        """
        
        details = {'refSeqNum'             : self.getValue(message, fix.RefSeqNum()),
                   'refTagId'              : self.getValue(message, fix.RefTagID()),
                   'refMsgType'            : self.getValue(message, fix.RefMsgType()),
                   'sessionRejectReason'   : self.getSessionRejectReason(self.getValue(message, fix.SessionRejectReason())),        
                   'text'                  : self.getValue(message, fix.Text())
                  }
        
        print(details)
            
    def onMessage_Logout(self, message, session):
        """
        onMessage - Logout
        
        Message Type = '5'
        The FIX Logout message initiates or confirms the termination of a FIX Session. Disconnection without the
        exchange Logout messages should be interpreted as an abnormal condition.
    
        """
        print('TRYING TO LOGOUT')
        
    def onMessage_News(self, message, session):
        """
        onMessage - News
        
        Message Type = 'B'.
        The news message is a general free format message between the broker and institution. The message is
        used by the exchange to notify to connected participants (brokers) of market news; contains flags to
        identify the news item's urgency.
                
        Fields:
            - (35) - MsgType = B
            - (42) - OrigTime = UTC Timestamp
            - (148) - Headline = (str)
            - (1300) - MarketSegmentID = (string)
            
        """

        details = {'origTime'         : self.getString(message, fix.OrigTime()),
                   'headline'         : self.getValue(message, fix.Headline()).encode(sys.getfilesystemencoding(), 'surrogateescape').decode('latin1','replace'),
                   'marketSegmentID'  : self.getValue(message, fix.MarketSegmentID())
                  }
        
        print(details)
        
    def onMessage_BusinessMessageReject(self, message, session):
        """
        onMessage - Business Message Reject
        
        Message Type = 'j'.
        Message sent by the exchange when it receives a supported message that is syntactically correct in an 
        unsupported situation, and there is no specific rejection message.
        
        Fields:
            - (35) - MsgType = j
            - (58) - Text = (string)
            - (372) - RefMsgType = (string)
            - (380) - BusinessRejectReason = (int)
        """
        
        details = {'refMsgType'            : self.getValue(message, fix.RefMsgType()),
                   'businessRejectReason'  : self.getBusinessRejectReason(self.getValue(message, fix.BusinessRejectReason())),        
                   'text'                  : self.getValue(message, fix.Text())
                  }
        
        print(details)
    
    def onMessage_TradingSessionStatus(self, message, session):
        """
        onMessage - Trading Session Status
        
        Message Type = 'h'.
        The Trading Session Status message provides information on the status of a market, and particularly,
        of the segments for the phase in which they are.
        
        Fields:
            - (58) - Text = (string)
            - (336) - TradingSessionID = (string)
            - (625) - TradingSessionSubID = (string)
            - (340) - TradSesStatus = (int)
            - (1301) - MarketID = (string)
            - (1300) - MarketSegmentID = (string)        
        """
        
        details = {'tradingSessionId' : self.getValue(message, fix.TradingSessionID()),
                   'tradSesStatus'    : self.getTradSesStatus(self.getValue(message, fix.TradSesStatus())),
                   'marketID'         : self.getValue(message, fix.MarketID()),
                   'marketSegmentID'  : self.getValue(message, fix.MarketSegmentID())
                   }
        
        try:
            details['text'] = self.getValue(message, fix.Text())
        except:
            pass
        
        try:
            details['tradingSessionSubId'] = self.getTradingSessionSubId(self.getValue(message, fix.TradingSessionSubID()))
        except:
            pass
        
        print(details)
        
    def onMessage_OrderCancelReject(self, message, session):
        """
        onMessage - Order Cancel Reject
        
        Message Type = '9'.
        The 'Order Cancel Reject' message is issued by the exchange, upon receipt of a 'Cancel Request', 'Mass
        Cancel Request' or 'Order Cancel Replace Request' message sent by client, which cannot be honored.
        Filled orders cannot be cancelled or modified.
        
        When rejecting an 'Order Cancel Request', the 'Order Cancel Reject' message will provide the ClOrdID
        and OrigClOrdID values which were specified on the original message 'Cancel/Mass Cancel/Replace request'
        for identification.
        
        Fields:
            - (11) - ClOrdId = (string)
            - (41) - OrigClOrdId = (string)
            - (37) - OrderID = (string)
            - (39) - OrderStatus = 0 (New) / 1 (Partially Filled) / (2) Filled / 4 (Canceled) / 8 (Rejected)
            - (434) - CxlRejResponseTo = 1 (Order Cancel Request)
            - (102) - CxlRejReason = 0 (Too late to Cancel) / 1 (Unknown Order) / 99 (Other)
        """        
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,  
                         'OrigClOrdId'      : self.getValue(message, fix.OrigClOrdID()),
                         'orderId'          : self.getValue(message, fix.OrderID()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                         'cxlRejResponseTo' : self.getValue(message, fix.CxlRejResponseTo()),
                         'cxlRejReason'     : self.getCxlRejReason(self.getValue(message, fix.CxlRejReason()))
                         }
        
        print(details)
    
    def onMessage_ExecutionReport_New(self, message, session):
        """
        onMessage - Execution Report - New
        
        Message Type = '8', ExecType '0' = New.
        Confirm the receipt of an order.
        
        Fields:
            - (35) - MsgType = 8
            - (6)  - AvgPx = (float)
            - (11) - ClOrdId = (string)
            - (14) - CumQty = (int)
            - (17) - ExecID = (string)
            - (31) - LastPx = (float)
            - (32) - LastQty = (int)
            - (37) - OrderID = (string)
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 0 (New)
            - (40) - OrdType = 2 (Limit)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (150) - ExecType = 0 (New)
            - (151) - LeavesQty = (int)
        """
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,                         
                         'execId'           : self.getValue(message, fix.ExecID()), 
                         'symbol'           : self.getValue(message, fix.Symbol()),
                         'side'             : self.getSide(self.getValue(message, fix.Side())),
                         'securityExchange' : self.getValue(message, fix.SecurityExchange()),
                         'transactTime'     : self.getString(message, fix.TransactTime()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                         'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                         'price'            : self.getValue(message, fix.Price()),
                         'avgPx'            : self.getValue(message, fix.AvgPx()),
                         'lastPx'           : self.getValue(message, fix.LastPx()),
                         'orderQty'         : self.getValue(message, fix.OrderQty()),
                         'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                         'cumQty'           : self.getValue(message, fix.CumQty()),
                         'lastQty'          : self.getValue(message, fix.LastQty()),
                         'text'             : self.getValue(message, fix.Text())
                         }
        
        orderID = self.getValue(message, fix.OrderID())
        
        data = {}
        data['type']  = 'or'
        data['senderCompID'] = senderCompID
        data['orderReport'] = {'accountId'    : {'id' : self.account},
                               'clOrdId'      : details['clOrdId'],
                               'cumQty'       : details['cumQty'],
                               'execId'       : details['execId'],
                               'instrumentId' : {'marketId' : details['securityExchange'], 'symbol' : details['symbol']},
                               'leavesQty'    : details['leavesQty'],
                               'ordType'      : details['ordType'],
                               'orderId'      : orderID,
                               'orderQty'     : details['orderQty'],
                               'price'        : details['price'],
                               'side'         : details['side'],
                               'status'       : details['ordStatus'],
                               'transactTime' : details['transactTime'],
                               'text'         : details['text']                            
                               }
        
        
        
        self.orders[orderID] = details
        self.sessions[targetCompID][clientOrderID] = orderID
        
        print(self.orders)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_ExecutionReport_OrderCanceledResponse(self, message, session):
        """
        onMessage - Execution Report - Order Canceled Response
        
        Message Type = '8', ExecType '4' = Canceled.
        Confirm order cancel requests of an existing order.
        
        Fields:
            - (35) - MsgType = 8
            - (6)  - AvgPx = (float)
            - (11) - ClOrdId = (string)
            - (14) - CumQty = (int)
            - (17) - ExecID = (string)
            - (31) - LastPx = (float)
            - (32) - LastQty = (int)
            - (37) - OrderID = (string)
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 4 (Canceled)
            - (40) - OrdType = 2 (Limit)
            - (41) - OrigClOrdID = (string)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (150) - ExecType = 4 (Canceled)
            - (151) - LeavesQty = (int)
        """
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,                         
                         'execId'           : self.getValue(message, fix.ExecID()), 
                         'origClOrdId'      : self.getValue(message, fix.OrigClOrdID()),
                         'symbol'           : self.getValue(message, fix.Symbol()),
                         'side'             : self.getSide(self.getValue(message, fix.Side())),
                         'securityExchange' : self.getValue(message, fix.SecurityExchange()),
                         'transactTime'     : self.getString(message, fix.TransactTime()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                         'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                         'price'            : self.getValue(message, fix.Price()),
                         'avgPx'            : self.getValue(message, fix.AvgPx()),
                         'lastPx'           : self.getValue(message, fix.LastPx()),
                         'orderQty'         : self.getValue(message, fix.OrderQty()),
                         'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                         'cumQty'           : self.getValue(message, fix.CumQty()),
                         'lastQty'          : self.getValue(message, fix.LastQty()),
                         'text'             : self.getValue(message, fix.Text())
                         }
        
        orderID = self.getValue(message, fix.OrderID())
        
        data = {}
        data['type']  = 'or'
        data['senderCompID'] = senderCompID
        data['orderReport'] = {'accountId'    : {'id' : self.account},
                               'avgPx'        : details['avgPx'],
                               'clOrdId'      : details['clOrdId'],
                               'origClOrdId'  : details['origClOrdId'],
                               'cumQty'       : details['cumQty'],
                               'execId'       : details['execId'],
                               'lastPx'       : details['lastPx'],
                               'lastQty'      : details['lastQty'],
                               'instrumentId' : {'marketId' : details['securityExchange'], 'symbol' : details['symbol']},
                               'leavesQty'    : details['leavesQty'],
                               'ordType'      : details['ordType'],
                               'orderId'      : orderID,
                               'orderQty'     : details['orderQty'],
                               'price'        : details['price'],
                               'side'         : details['side'],
                               'status'       : details['ordStatus'],
                               'transactTime' : details['transactTime'],
                               'text'         : details['text']
                               }
        
        
        
        self.orders[orderID] = details
        self.sessions[targetCompID][clientOrderID] = orderID
        
        print(self.orders)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_ExecutionReport_OrderReplacedResponse(self, message, session):
        """
        onMessage - Execution Report - Order Replaced Response
        
        Message Type = '8', ExecType '5' = Replaced.
        Confirm changes to an existing order
        
        Fields:
            - (35) - MsgType = 8
            - (6)  - AvgPx = (float)
            - (11) - ClOrdId = (string)
            - (14) - CumQty = (int)
            - (17) - ExecID = (string)
            - (31) - LastPx = (float)
            - (32) - LastQty = (int)
            - (37) - OrderID = (string)
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 1 (Partially Filled) / 2 (Filled)
            - (40) - OrdType = 1 (Market) / 2 (Limit) / K (Market with Left Over as Limit)
            - (41) - OrigClOrdID = (string)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (150) - ExecType = F (Trade <Partial Fill or Fill>)
            - (151) - LeavesQty = (int)
        """
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,
                         'execId'           : self.getValue(message, fix.ExecID()), 
                         'origClOrdId'      : self.getValue(message, fix.OrigClOrdID()),
                         'symbol'           : self.getValue(message, fix.Symbol()),
                         'side'             : self.getSide(self.getValue(message, fix.Side())),
                         'securityExchange' : self.getValue(message, fix.SecurityExchange()),
                         'transactTime'     : self.getString(message, fix.TransactTime()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                         'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                         'price'            : self.getValue(message, fix.Price()),
                         'avgPx'            : self.getValue(message, fix.AvgPx()),
                         'lastPx'           : self.getValue(message, fix.LastPx()),
                         'orderQty'         : self.getValue(message, fix.OrderQty()),
                         'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                         'cumQty'           : self.getValue(message, fix.CumQty()),
                         'lastQty'          : self.getValue(message, fix.LastQty()),
                         'text'             : self.getValue(message, fix.Text())
                         }
        
        orderID = self.getValue(message, fix.OrderID())
        
        data = {}
        data['type']  = 'or'
        data['senderCompID'] = senderCompID
        data['orderReport'] = {'accountId'    : {'id' : self.account},
                               'avgPx'        : details['avgPx'],
                               'clOrdId'      : details['clOrdId'],
                               'origClOrdId'  : details['origClOrdId'],
                               'cumQty'       : details['cumQty'],
                               'execId'       : details['execId'],
                               'lastPx'       : details['lastPx'],
                               'lastQty'      : details['lastQty'],
                               'instrumentId' : {'marketId' : details['securityExchange'], 'symbol' : details['symbol']},
                               'leavesQty'    : details['leavesQty'],
                               'ordType'      : details['ordType'],
                               'orderId'      : orderID,
                               'orderQty'     : details['orderQty'],
                               'price'        : details['price'],
                               'side'         : details['side'],
                               'status'       : details['ordStatus'],
                               'transactTime' : details['transactTime'],
                               'text'         : details['text']
                               }
        
        
        
        self.orders[orderID] = details
        self.sessions[targetCompID][clientOrderID] = orderID
        
        print(self.orders)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_ExecutionReport_OrderFilledPartiallyFilledResponse(self, message, session):
        """
        onMessage - Execution Report - Order Filled/Partially Filled Response
        
        Message Type = '8', ExecType 'F' = Trade (Partial Fill or Fill).
        Ths message will be sent to the customer as a result of an order matching leading to trade creation.
        
        Fields:
            - (35) - MsgType = 8
            - (6)  - AvgPx = (float)
            - (11) - ClOrdId = (string)
            - (14) - CumQty = (int)
            - (17) - ExecID = (string)
            - (31) - LastPx = (float)
            - (32) - LastQty = (int)
            - (37) - OrderID = (string)
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 1 (Partially Filled) / 2 (Filled)
            - (40) - OrdType = 1 (Market) / 2 (Limit) / K (Market with Left Over as Limit)
            - (41) - OrigClOrdID = (string)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (150) - ExecType = F (Trade <Partial Fill or Fill>)
            - (151) - LeavesQty = (int)
        """
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,
                         'execId'           : self.getValue(message, fix.ExecID()), 
                         'origClOrdId'      : self.getValue(message, fix.OrigClOrdID()),
                         'symbol'           : self.getValue(message, fix.Symbol()),
                         'side'             : self.getSide(self.getValue(message, fix.Side())),
                         'securityExchange' : self.getValue(message, fix.SecurityExchange()),
                         'transactTime'     : self.getString(message, fix.TransactTime()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                         'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                         'price'            : self.getValue(message, fix.Price()),
                         'avgPx'            : self.getValue(message, fix.AvgPx()),
                         'lastPx'           : self.getValue(message, fix.LastPx()),
                         'orderQty'         : self.getValue(message, fix.OrderQty()),
                         'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                         'cumQty'           : self.getValue(message, fix.CumQty()),
                         'lastQty'          : self.getValue(message, fix.LastQty()),
                         'text'             : self.getValue(message, fix.Text())
                         }
        
        orderID = self.getValue(message, fix.OrderID())
        
        data = {}
        data['type']  = 'or'
        data['senderCompID'] = senderCompID
        data['orderReport'] = {'accountId'    : {'id' : self.account},
                               'avgPx'        : details['avgPx'],
                               'clOrdId'      : details['clOrdId'],
                               'origClOrdId'  : details['origClOrdId'],
                               'cumQty'       : details['cumQty'],
                               'execId'       : details['execId'],
                               'lastPx'       : details['lastPx'],
                               'lastQty'      : details['lastQty'],
                               'instrumentId' : {'marketId' : details['securityExchange'], 'symbol' : details['symbol']},
                               'leavesQty'    : details['leavesQty'],
                               'ordType'      : details['ordType'],
                               'orderId'      : orderID,
                               'orderQty'     : details['orderQty'],
                               'price'        : details['price'],
                               'side'         : details['side'],
                               'status'       : details['ordStatus'],
                               'transactTime' : details['transactTime'],
                               'text'         : details['text']
                               }
        
        
        
        self.orders[orderID] = details
        self.sessions[targetCompID][clientOrderID] = orderID
        
        print(self.orders)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_ExecutionReport_OrderStatusResponse(self, message, session):
        """
        onMessage - Execution Report - Order Status Response
        
        Message Type = '8', ExecType 'I' = Order Status.
        This message will be sent to the customer as the reply of an order mass status request or an order status request.
        
        Fields:
            - (35) - MsgType = 8
            - (790)  - OrdStatusReqID = (string)
            - (911) - TotNumReports = (itn)
            - (584) - Mass StatusReqID = (int)
            - (912) - LastRptRequested = (boolean) - N (Not last message) / Y (Last message)
            - (6) - AvgPx = (float)
            - (11) - ClOrdID (string)
            - (14) - CumQty = (int)
            - (17) - ExecID = (string)
            - (31) - LastPx = (float)
            - (32) - LastQty = (int)
            - (37) - OrderID = (string)
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 0 (New) / 1 (Partially Filled) / 2 (Filled) / 4 (Canceled) / 8 (Rejected)
            - (40) - OrdType = 1 (Market) / 2 (Limit) / K (Market with Left Over as Limit)
            - (41) - OrigClOrdID = (string)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (103) - OrdRejReason = (int)
            - (150) - ExecType = I (Order Status)
            - (151) - LeavesQty = (int)
        """
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        
        try:
            totNumReports = self.getValue(message, fix.TotNumReports())
            details       = {'targetCompId'     : targetCompID,
                             'totNumReports'    : totNumReports,
                             'massStatusReqId'  : self.getValue(message, fix.MassStatusReqID()),
                             'lastRptRequested' : self.getValue(message, fix.LastRptRequested()),
                             'avgPx'            : self.getValue(message, fix.AvgPx()),
                             'cumQty'           : self.getValue(message, fix.CumQty()),
                             'execId'           : self.getValue(message, fix.ExecID()), 
                             'orderId'          : self.getValue(message, fix.OrderID()),
                             'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                             'symbol'           : self.getValue(message, fix.Symbol()),
                             'side'             : self.getSide(self.getValue(message, fix.Side())),
                             'transactTime'     : self.getString(message, fix.TransactTime()),
                             'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                             'text'             : self.getValue(message, fix.Text())
                             }
            
            data = {}
            data['type']  = 'os'
            data['senderCompID'] = senderCompID
            data['statusReport'] = details
            
            if totNumReports > 0:
                
                details_with_orders = {'account'        : self.getValue(message, fix.Account()),
                                       'clOrdId'        : self.getValue(message, fix.ClOrdID()),
                                       'lastPx'         : self.getValue(message, fix.LastPx()),
                                       'lastQty'        : self.getValue(message, fix.LastQty()),
                                       'orderQty'       : self.getValue(message, fix.OrderQty()),
                                       'ordType'        : self.getOrdType(self.getValue(message, fix.OrdType())),
                                       'price'          : self.getValue(message, fix.Price())                           
                                      }
            
                details.update(details_with_orders)
                data['statusReport'].update(details_with_orders)
        except:
            details       = {'targetCompId'     : targetCompID,
                             'account'          : self.getValue(message, fix.Account()),
                             'avgPx'            : self.getValue(message, fix.AvgPx()),
                             'clOrdId'          : self.getValue(message, fix.ClOrdID()),
                             'cumQty'           : self.getValue(message, fix.CumQty()),
                             'execId'           : self.getValue(message, fix.ExecID()), 
                             'lastPx'           : self.getValue(message, fix.LastPx()),
                             'lastQty'          : self.getValue(message, fix.LastQty()),
                             'orderId'          : self.getValue(message, fix.OrderID()),
                             'orderQty'         : self.getValue(message, fix.OrderQty()),
                             'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
                             'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                             'price'            : self.getValue(message, fix.Price()),
                             'symbol'           : self.getValue(message, fix.Symbol()),
                             'side'             : self.getSide(self.getValue(message, fix.Side())),
                             'transactTime'     : self.getString(message, fix.TransactTime()),
                             'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                             'text'             : self.getValue(message, fix.Text()),
                             'securityExchange' : self.getValue(message, fix.SecurityExchange())
                             }
            
            data = {}
            data['type']  = 'os'
            data['senderCompID'] = senderCompID
            data['statusReport'] = details
        
        print(data)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_ExecutionReport_RejectMessageResponse(self, message, session):
        """
        onMessage - Execution Report - Reject Message Response
        
        Message Type = '8', ExecType '8' = Rejected.
        
        Fields:
            - (35) - MsgType = 8
            - (6)  - AvgPx = 0
            - (11) - ClOrdId = (string)
            - (14) - CumQty = 0
            - (17) - ExecID = (string)
            - (37) - OrderID = 'NONE'
            - (38) - OrderQty = (int)
            - (39) - OrderStatus = 8 (Rejected)
            - (44) - Price = (float)
            - (54) - Side = 1 (Buy) / 2 (Sell)
            - (55) - Symbol = (string)
            - (58) - Text = (string)
            - (60) - TransactTime = UTC Timestamp
            - (150) - ExecType = 8 (Rejected)
            - (151) - LeavesQty = 0
        """
        
        clientOrderID = self.getValue(message, fix.ClOrdID())
        targetCompID  = session.getTargetCompID().getValue()
        senderCompID  = session.getSenderCompID().getValue()
        details       = {'targetCompId'     : targetCompID,
                         'clOrdId'          : clientOrderID,
                         'execId'           : self.getValue(message, fix.ExecID()), 
                         'symbol'           : self.getValue(message, fix.Symbol()),
                         'side'             : self.getSide(self.getValue(message, fix.Side())),
                         'transactTime'     : self.getString(message, fix.TransactTime()),
                         'ordStatus'        : self.getOrdStatus(self.getValue(message, fix.OrdStatus())),
#                         'ordType'          : self.getOrdType(self.getValue(message, fix.OrdType())),
                         'price'            : self.getValue(message, fix.Price()),
                         'avgPx'            : self.getValue(message, fix.AvgPx()),
                         'orderQty'         : self.getValue(message, fix.OrderQty()),
                         'leavesQty'        : self.getValue(message, fix.LeavesQty()),
                         'cumQty'           : self.getValue(message, fix.CumQty()),
                         'text'             : self.getValue(message, fix.Text())
                         }
        
        data = {}
        data['type']  = 'or'
        data['senderCompID'] = senderCompID
        data['orderReport'] = details
              
        print(data)
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_MarketDataSnapshotFullRefresh(self, message, session):
        """
        onMessage - Market Data - Snapshot / Full Refresh
        
        Message Type = 'W'.
        The Market Data Snapshot/Full Refresh messages are sent as the response to a Market Data Request
        message. The message refers to only one Market Data Request. It will contain the appropiate MDReqID
        tag value to correlate the request with the response.
        
        Fields:
            - (35) MsgType = W  
            - (262) MDReqID = (string)
            - Block Instrument:
                - (55) Symbol = (string - Ticker)
            - Block MDfullGrp:
                - (268) NoMDEntries = (Int - number of Entries)
                    - (269) MDEntryType = 0 (Bid) / 1 (Offer) / 2 (Trade) / 4 (Opening price) / 5 (Closing Price) / 6 (Settlement Price) /
                                            7 (Trading Session High Price) / 8 (Trading Session Low Price) / B (Trade Volume) / C (Open Interest) /
                                            x (Nominal Volume) / w (Cash Volume)
                    - (270) MDEntryPx = (float - Conditional field when MDEntryType is 0-1-2-4-5-6-7-8-w)
                    - (271) MDEntrySize = (int - Conditional field when MDEntryType is 0-1-2-B-C-x)
                    - (290) MDEntryPositionNo = (int)    
        """
        
        msg = message.toString().replace(__SOH__, "|")
        logfix.info("onMessage, R app (%s)" % msg)
        
        data = {}
         
        ## Number of entries following (Bid, Offer, etc)
        noMDEntries = self.getValue(message, fix.NoMDEntries())
        
        symbol = self.getValue(message, fix.Symbol())
        
        ## Market ID (ROFX, BYMA)     
        marketId = self.getValue(message, fix.SecurityExchange())
        
        instrumentId = {"symbol": symbol, "marketId": marketId}
        data["instrumentId"] = instrumentId
        data["marketData"] = {"BI": [], "OF": []}
           
        group = fix50.MarketDataSnapshotFullRefresh().NoMDEntries()
        
        MDEntryType = fix.MDEntryType() # Identifies the type of entry (Bid, Offer, etc)
        MDEntryPx = fix.MDEntryPx()
        MDEntrySize = fix.MDEntrySize()
        MDEntryPositionNo = fix.MDEntryPositionNo() # Display position of a bid or offer, numbered from most competitive to least competitive
        
        table = texttable.Texttable()
        table.set_deco(texttable.Texttable.BORDER|texttable.Texttable.HEADER)
        table.header(['Ticker','Tipo','Precio','Size','Posicion'])
        table.set_cols_width([12,20,8,8,8])      
        table.set_cols_align(['c','c','c','c','c'])
                
        for entry in range(1,int(noMDEntries)+1):
            try:
                
                md = {}
                price, size, position = None, None, None
                
                message.getGroup(entry, group)
                entry_type = group.getField(MDEntryType).getString()
                
                if entry_type in list('01245678w'):
                    price = group.getField(MDEntryPx).getString()
                    md['price'] = float(price)
                if entry_type in list('012BCx'):
                    size = group.getField(MDEntrySize).getString()
                    md['size'] = int(size)
                if entry_type in list('01'):
                    position = group.getField(MDEntryPositionNo).getString()
                    md['position'] = int(position)
                
                if entry_type == '0':
                    data["marketData"]["BI"].append(md)
                    tipo = 'BID'
                elif entry_type == '1':
                    data["marketData"]["OF"].append(md)
                    tipo = 'OFFER'
                elif entry_type == 'B':
                    data["marketData"]["TV"] = md
                    tipo = 'TRADE VOLUME'
                else:
                    tipo = entry_type
                                     
                table.add_row([symbol, tipo, price, size, position])
            except:
                pass
            
        print(table.draw())
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_MarketDataRequestReject(self, message, session):
        """
        onMessage - Market Data Request Reject
        
        Message Type = 'Y'.
        The Market Data Request Reject will be issued by the Exchange when it cannot honor the Market Data
        Request, due to business or technical reasons.
        
        Fields:
            - (35) MsgType = Y  
            - (262) MDReqID = (string)
            - (281) MDReqRejReason = (char)
        """
        
        details = {'MDReqId'           : self.getValue(message, fix.MDReqID()),
                   'MDReqRejReason'    : self.getMDReqRejReason(self.getValue(message, fix.MDReqRejReason()))
                   }
         
        print(details)
        
    def onMessage_SecurityList(self, message, session):
        """
        onMessage - Security List
        
        Message Type = 'y'.
        The Security List message is used to return a list of securities that matches the criteria specified
        in a Security List Request.
        
        Fields:
            - (35) - MsgType = y
            - (320) - SecurityReqID = (string)
            - (322) - SecurityResponseID = (string)
            - (560) - SecurityRequestResult = (int)
            - (559) - SecurityListRequestType = 4 (All Securities)
            - (393) - TotNoRelatedSym = (int)            
            - Block SecListGrp:
                - (146) - NoRelatedSym = (Int - number of repeating symbols specified)
                    - Block Instrument:
                        - (55) - Symbol = (string - Ticker)
                        - (107) - SecurityDesc = (string)
                        - (228) - Factor = (float)
                        - (461) - CFICode = (string)
                        - (231) - ContractMultiplier = (float)
                        - (200) - MaturityMonthYear = ('YYYYMM')
                        - (541) - MaturityDate = ('YYYYMMDD')
                        - (202) - StrikePrice = (float)
                        - (947) - StrikeCurrency = (string)
                        - (969) - MinPriceIncrement = (float)
                        - (5023) - TickSize = (int)
                        - (5514) - InstrumentPricePrecision = (int)
                        - (7117) - InstrumentSizePrecision = (int)
                    - (15) - Currency = (string)
                    - Block FinancingDetails:
                        - (917) - EndDate = (Date)
                    - Block UndInstrmtGrp:
                        - (711) - NoUnderlyings = (int)
                         - Block UnderlyingSymbol:
                             - (311) - UnderlyingSymbol = (string)
                    - Block SecurityTradingRules:
                        - Block BaseTradingRules:
                            - (1140) - MaxTradeVol = (float)
                            - (562) - MinTradeVol = (float)
                            - Block LotTypeRules:
                                - (1234) - NoLotTypeRules = (int)
                                    - (1093) - LotType = (char)
                                    - (1231) - MinLotSize = (int)
                                    - (5515) - MaxLotSize = (int)
                            - Block PriceLimits:
                                - (1148) - LowLimitPrice = (float)
                                - (1149) - HighLimitPrice = (float)
                        - Block TradingSessionRulesGrp:
                            - (1309) - NoTradingSessionRules = (int)
                                - (336) - TradingSessionID = (string)
                                - Block TradingSessionRules:
                                    - Block OrdTypeRules:
                                        - (1237) - NoOrdTypeRules = (int)
                                            - (40) - OrdType = (char)
                                    - Block TimeInForceRules:
                                        - (1239) - NoTimeInForceRules = (int)
                                            - (59) - TimeInForce = (char)
                                    - Block ExecInstRules:
                                        - (1232) - NoExecInstRules = (int)
                                            - (1308) - ExecInstValue = (char)
        """
        
        details = {'securityReqId'           : self.getValue(message, fix.SecurityReqID()),
                   'securityResponseId'      : self.getValue(message, fix.SecurityResponseID()),
                   'totNoRelatedSym'         : self.getValue(message, fix.TotNoRelatedSym()),
                   'securityListRequestType' : self.getValue(message, fix.SecurityListRequestType()),
                   'securityRequestResult'   : self.getValue(message, fix.SecurityRequestResult()),
                   'marketSegmentId'         : self.getValue(message, fix.MarketSegmentID()),
                   'noRelatedSym'            : self.getValue(message, fix.NoRelatedSym())
                  }
        
        data = {}
        data['details'] = details
        data['tickers'] = []
                
        group = fix50.SecurityList().NoRelatedSym()
        
        table = texttable.Texttable()
        table.set_deco(texttable.Texttable.BORDER|texttable.Texttable.HEADER)
        table.header(['Symbol','Min Price Increment','Tick Size','Price Precision','Size Precision','Currency',
                      'Underlying','Low Limit Price','High Limit Price'])
        table.set_cols_width([35,15,10,10,10,10,45,10,10])      
        table.set_cols_align(['c','c','c','c','c','c','c','c','c'])
                
        for relatedSym in range(1,details['noRelatedSym']+1):
            
            message.getGroup(relatedSym, group)
                       
            aux = {'symbol'                     : self.getValueGroup(group, fix.Symbol()),
                   'factor'                     : self.getValueGroup(group, fix.Factor()),
                   'securityDesc'               : self.getValueGroup(group, fix.SecurityDesc()),
                   'cfiCode'                    : self.getValueGroup(group, fix.CFICode()),
                   'contractMultiplier'         : self.getValueGroup(group, fix.ContractMultiplier()),      
                   'minPriceIncrement'          : self.getValueGroup(group, fix.MinPriceIncrement()),
                   'tickSize'                   : group.getField(5023),
                   'instrumentPricePrecision'   : group.getField(5514),
                   'instrumentSizePrecision'    : group.getField(7117),
                   'currency'                   : self.getValueGroup(group, fix.Currency()),
                   'maxTradeVol'                : self.getValueGroup(group, fix.MaxTradeVol()),
                   'minTradeVol'                : self.getValueGroup(group, fix.MinTradeVol()),
                   'lowLimitPrice'              : self.getValueGroup(group, fix.LowLimitPrice()),
                   'highLimitPrice'             : self.getValueGroup(group, fix.HighLimitPrice())
                   }          
            try: 
                aux['strikePrice'] = self.getValueGroup(group, fix.StrikePrice()) 
            except: 
                pass
            try: 
                aux['strikeCurrency'] = self.getValueGroup(group, fix.StrikeCurrency()) 
            except: 
                pass
            try: 
                aux['maturityMonthYear'] = self.getValueGroup(group, fix.MaturityMonthYear()) 
            except: 
                pass
            try: 
                aux['maturityDate'] = self.getValueGroup(group, fix.MaturityDate()) 
            except: 
                pass
               
            ## Block UndInstrmtGrp
            groupUnderlyings = fix50.SecurityList().NoRelatedSym().NoUnderlyings()
            try:
                noUnderlyings = group.getField(711)
                for underlying in range(1,int(noUnderlyings)+1):
                    group.getGroup(underlying, groupUnderlyings)
                    try:
                        aux['underlyingSymbol'] = self.getValueGroup(groupUnderlyings, fix.UnderlyingSymbol()).encode(sys.getfilesystemencoding(), 'surrogateescape').decode('latin1','replace')
                    except:
                        pass
            except:
                pass
            
            ## Block LotTypeRules
            groupLotTypeRules = fix50.SecurityList().NoRelatedSym().NoLotTypeRules()
            try:
                noLotTypeRules = group.getField(1234)
                for typeRule in range(1,int(noLotTypeRules)+1):
                    group.getGroup(typeRule, groupLotTypeRules)
                    try:
                        aux['lotType'] = self.getValueGroup(groupLotTypeRules, fix.LotType())
                        aux['minLotSize'] = self.getValueGroup(groupLotTypeRules, fix.MinLotSize())
                        aux['maxLotSize'] = groupLotTypeRules.getField(5515)
                    except:
                        pass
            except:
                pass
            
            ## Block TradingSessionRulesGrp
            groupTradingSessionRules = fix50.SecurityList().NoRelatedSym().NoTradingSessionRules()
            try:
                noTradingSessionRules = group.getField(1309)
                for sessionRule in range(1,int(noTradingSessionRules)+1):
                    group.getGroup(sessionRule, groupTradingSessionRules)
                    try:
                        aux['tradingSessionId'] = self.getValueGroup(groupTradingSessionRules, fix.TradingSessionID())
                        
                        ## Block TradingSessionRules
                            
                        ### Block OrdTypeRules
                        groupOrdTypeRules = fix50.SecurityList().NoRelatedSym().NoTradingSessionRules().NoOrdTypeRules()
                        try:
                            noOrdTypeRules = groupTradingSessionRules.getField(1237)
                            aux['ordType'] = []
                            for typeRule in range(1,int(noOrdTypeRules)+1):
                                groupTradingSessionRules.getGroup(typeRule, groupOrdTypeRules)
                                try:
                                    aux['ordType'].append(self.getOrdType(self.getValueGroup(groupOrdTypeRules, fix.OrdType())))
                                except:
                                    pass
                        except:
                            pass 
                        
                        ### Block TimeInForceRules
                        groupTimeInForceRules = fix50.SecurityList().NoRelatedSym().NoTradingSessionRules().NoTimeInForceRules()
                        try:
                            noTimeInForceRules = groupTradingSessionRules.getField(1239)
                            aux['timeInForce'] = []
                            for forceRule in range(1,int(noTimeInForceRules)+1):
                                groupTradingSessionRules.getGroup(forceRule, groupTimeInForceRules)
                                try:
                                    aux['timeInForce'].append(self.getTimeInForce(self.getValueGroup(groupTimeInForceRules, fix.TimeInForce())))
                                except:
                                    pass
                        except:
                            pass
                        
                        ### Block ExecInstRules
                        groupExecInstRules = fix50.SecurityList().NoRelatedSym().NoTradingSessionRules().NoExecInstRules()
                        try:
                            noExecInstRules = groupTradingSessionRules.getField(1232)
                            aux['execInstValue'] = []
                            for instRule in range(1,int(noExecInstRules)+1):
                                groupTradingSessionRules.getGroup(instRule, groupExecInstRules)
                                try:
                                    aux['execInstValue'].append(self.getExecInstValue(self.getValueGroup(groupExecInstRules, fix.ExecInstValue())))
                                except:
                                    pass
                        except:
                            pass                            
                            
                    except:
                        pass
            except:
                pass
            
            data['tickers'].append(aux)

            table.add_row([aux['symbol'],aux['minPriceIncrement'],aux['tickSize'],aux['instrumentPricePrecision'],aux['instrumentSizePrecision'],aux['currency'],
                           aux['underlyingSymbol'],aux['lowLimitPrice'],aux['highLimitPrice']])
            
        print(table.draw())
        
        ## Broadcast JSON to WebSocket
        self.server_md.broadcast(str(data))
        
    def onMessage_SecurityStatus(self, message, session):
        """
        onMessage - Security Status
        
        Message Type = 'f'.
        The Security Status message provides for the ability to report changes in status to a security. The Security 
        Status message contains fields to indicate trading status, corporate actions, financial status of the company. 
        The Security Status message is used by one tradiny entity to report changes in the state of a security.
        
        Fields:
            - (35) - MsgType = Y  
            - (324) - SecurityStatusReqID = (string)
            - (55) - Symbol = (string)
            - (326) - SecurityTradingStatus = (int)
        """
        
        details = {'symbol'                   : self.getValue(message, fix.Symbol()),
                   'securityTradingStatus'    : self.getSecurityTradingStatus(self.getValue(message, fix.SecurityTradingStatus()))
                   }
        
        table = texttable.Texttable()
        table.set_deco(texttable.Texttable.BORDER|texttable.Texttable.HEADER)
        table.header(['Symbol','Trading Status'])
        table.set_cols_width([35,20])      
        table.set_cols_align(['c','c'])
        
        table.add_row([details['symbol'], details['securityTradingStatus']])
        print(table.draw())       
        
#        print(details)
        
    def onMessage_TradeCaptureReport(self, message, session):
        """
        onMessage - Trade Capture Report
        
        Message Type = 'AE'.
        The Trade Capture Report message can be:
            - Used to report trades between counterparties.
            - Can be sent unsolicited between counterparties.
            - Sent as a reply to a Trade Capture Report Request.
            - Can be used to send a Block Trade to be confirmed by the involved parties.
            - Can be used to notify about the new Block Trade to be confirmed.
            - Can be used to notify the Block Trade acceptation, or declination.
            
        Fields:
            - (35) - MsgType = AE
            - (571) - TradeReportID = (string)
            - (568) - TradeRequestID = (string)
            - (828) - TrdType = (int) - 0 (Regular Trade)
            - (60) - TransactTime = UTC Timestamp
            - (570) - PreviouslyReported = (boolean) - N (Not reported to counterparty)
            - (748) - TotNumTradeReports = (int)
            - (912) - LastRptRequested = N (Not last message) / Y (Last message)
            - (32) - LastPx = (float)
            - (31) - LastQty = (int)
            - (55) - Symbol = (string)
            - (17) - ExecID = (int)
            - (207) - SecurityExchange = 'ROFX'
            - (461) - CFICode = (string)
            Block TrdCapRptSideGrp:
                - (552) - NoSides = 1 (One Side) / 2 (Both Sides)
                    - (54) - Side = 1 (Buy) / 2 (Sell)
                    - (1) - Account = (string)            
        """
        
        tradeRequestID          = self.getValue(message, fix.TradeRequestID())    
        totNumTradeReports      = self.getValue(message, fix.TotNumTradeReports())
        lastRptRequested        = self.getValue(message, fix.LastRptRequested())    
        tradeReportID           = self.getValue(message, fix.TradeReportID())   
        details                 = {'lastPx'                   : self.getValue(message, fix.LastPx()),
                                   'lastQty'                  : self.getValue(message, fix.LastQty()),
                                   'symbol'                   : self.getValue(message, fix.Symbol()),
                                   'transactTime'             : self.getString(message, fix.TransactTime()),                   
                                   'previouslyReported'       : self.getValue(message, fix.PreviouslyReported()),
                                   'sides'                    : []
                                   }
        
        try:
            details['execId'] = self.getValue(message, fix.ExecID())
        except:
            pass
        try:
            details['securityExchange'] = self.getValue(message, fix.SecurityExchange())
        except:
            pass
        try:
            details['cfiCode'] = self.getValue(message, fix.CFICode())
        except:
            pass
        try:
            details['trdType'] = self.getValue(message, fix.TrdType())
        except:
            pass
        
        noSides                 = self.getValue(message, fix.NoSides())
        group                   = fix50.TradeCaptureReport().NoSides()        
                
        for side in range(1,noSides+1):
            message.getGroup(side, group)
            
            aux = {'side'           : self.getSide(self.getValueGroup(group, fix.Side())),
                   'account'        : self.getValueGroup(group, fix.Account())
                   }
            
            try:
                aux['orderId'] = self.getValueGroup(group, fix.OrderID())
            except:
                pass
            
            ## Block Parties
            groupParties = fix50.TradeCaptureReport().NoSides().NoPartyIDs()
            try:
                noParties = group.getField(453)
                aux['parties'] = {}
                for party in range(1,int(noParties)+1):
                    group.getGroup(party, groupParties)
                    
                    partyId = self.getValueGroup(groupParties, fix.PartyID())
                    aux['parties'][partyId] = {'partyIdSource'      : self.getValueGroup(groupParties, fix.PartyIDSource()),
                                               'partyRole'          : self.getValueGroup(groupParties, fix.PartyRole())
                                              }
            except:
                pass
            
            try:
                aux['aggressorIndicator'] = self.getValueGroup(group, fix.AggressorIndicator())
            except:
                pass            
            
            details['sides'].append(aux)
            
        if tradeRequestID not in self.tradeReports:
            self.tradeReports[tradeRequestID] = {'totNumTradeReports' : totNumTradeReports,
                                                 'reports'            : {}                    
                                                 }
        
        self.tradeReports[tradeRequestID]['reports'][tradeReportID] = details
        
        if lastRptRequested:
            print(self.tradeReports)
                        
    def logout(self):
        fix.Session.lookupSession(self.sessions[self.targetCompID]['session']).logout()
        
    """
    Wrappers for get(Field)
    """
    
    def getValue(self, message, field):
        key = field
        message.getField(key)
        return key.getValue()
    
    def getString(self, message, field):
        key = field
        message.getField(key)
        return key.getString()
    
    def getHeaderValue(self, message, field):
        key = field
        message.getHeader().getField(key)
        return key.getValue()
    
    def getFooterValue(self, message, field):
        key = field
        message.getTrailer().getField(key)
        return key.getValue() 
    
    def getStringGroup(self, group, field):
        key = field
        group.getField(key)
        return key.getString()
    
    def getValueGroup(self, group, field):
        key = field
        group.getField(key)
        return key.getValue()
    
    """
    Wrappers for Next Field
    """
    
    def getNextOrderID(self):
        lastOrderID = int(self.lastOrderID.split('-')[1]) + 1
        self.lastOrderID = self.account + '-' + str(lastOrderID).zfill(8)
        return self.lastOrderID

    def getNextExecID(self, targetCompID):
        self.sessions[targetCompID]['execID'] += 1
        return "{}_{}".format(targetCompID, self.sessions[targetCompID]['execID'])

    def getNextExchangeID(self, targetCompID):
        self.sessions[targetCompID]['exchID'] += 1
        return "{}_{}".format(targetCompID, self.sessions[targetCompID]['exchID'])
                
    """
    Wrappers for messages
    """
    
    def getSide(self, side):
        if side == fix.Side_BUY: return "Buy"
        if side == fix.Side_SELL: return "Sell"
        if side == fix.Side_SELL_SHORT: return "SellShort"
        
    def getOrdType(self, ordType):
        if ordType == fix.OrdType_MARKET: return "Market"
        if ordType == fix.OrdType_LIMIT: return "Limit"
        if ordType == fix.OrdType_MARKET_WITH_LEFTOVER_AS_LIMIT: return "Market with left over as limit"
        if ordType == fix.OrdType_STOP: return "Stop Merval"
        if ordType == fix.OrdType_STOP_LIMIT: return "Stop Limit"
        if ordType == 'z': return "Stop"
        
    def getOrdStatus(self, status):
        if status == fix.OrdStatus_NEW: return "NEW"
        if status == fix.OrdStatus_PARTIALLY_FILLED: return "PARTIALLY FILLED"
        if status == fix.OrdStatus_FILLED: return "FILLED"
        if status == fix.OrdStatus_CANCELED: return "CANCELLED"
        if status == fix.OrdStatus_REJECTED: return "REJECTED"
        if status == fix.OrdStatus_SUSPENDED: return "SUSPENDED"
        
    def getExecType(self, execType):
        if execType == fix.ExecType_NEW: return "NEW"
        if execType == fix.ExecType_REPLACED: return "REPLACED"
        if execType == fix.ExecType_TRADE: return "TRADE (PARTIAL FILL OR FILL)"
        if execType == fix.ExecType_CANCELLED: return "CANCELLED"
        if execType == fix.ExecType_ORDER_STATUS: return "ORDER STATUS"
        if execType == fix.ExecType_REJECTED: return "REJECTED"
        
    def getBusinessRejectReason(self, reason):
        if reason == fix.BusinessRejectReason_OTHER: return fix.BusinessRejectReason_OTHER_TEXT
        if reason == fix.BusinessRejectReason_UNKNOWN_ID: return fix.BusinessRejectReason_UNKNOWN_ID_TEXT
        if reason == fix.BusinessRejectReason_UNKNOWN_SECURITY: return fix.BusinessRejectReason_UNKNOWN_SECURITY_TEXT
        if reason == fix.BusinessRejectReason_UNSUPPORTED_MESSAGE_TYPE: return fix.BusinessRejectReason_UNSUPPORTED_MESSAGE_TYPE_TEXT
        if reason == fix.BusinessRejectReason_APPLICATION_NOT_AVAILABLE: return fix.BusinessRejectReason_APPLICATION_NOT_AVAILABLE_TEXT
        if reason == fix.BusinessRejectReason_CONDITIONALLY_REQUIRED_FIELD_MISSING: return fix.BusinessRejectReason_CONDITIONALLY_REQUIRED_FIELD_MISSING_TEXT
        if reason == fix.BusinessRejectReason_NOT_AUTHORIZED: return fix.BusinessRejectReason_NOT_AUTHORIZED_TEXT
        if reason == fix.BusinessRejectReason_DELIVERTO_FIRM_NOT_AVAILABLE_AT_THIS_TIME: return fix.BusinessRejectReason_DELIVERTO_FIRM_NOT_AVAILABLE_AT_THIS_TIME_TEXT
        if reason == fix.BusinessRejectReason_INVALID_PRICE_INCREMENT: return "Invalid Price Increment"
        
    def getSessionRejectReason(self, reason):
        if reason == fix.SessionRejectReason_INVALID_TAG_NUMBER: return fix.SessionRejectReason_INVALID_TAG_NUMBER_TEXT
        if reason == fix.SessionRejectReason_REQUIRED_TAG_MISSING: return fix.SessionRejectReason_REQUIRED_TAG_MISSING_TEXT
        if reason == fix.SessionRejectReason_TAG_NOT_DEFINED_FOR_THIS_MESSAGE_TYPE: return fix.SessionRejectReason_TAG_NOT_DEFINED_FOR_THIS_MESSAGE_TYPE_TEXT
        if reason == fix.SessionRejectReason_UNDEFINED_TAG: return fix.SessionRejectReason_UNDEFINED_TAG_TEXT
        if reason == fix.SessionRejectReason_TAG_SPECIFIED_WITHOUT_A_VALUE: return fix.SessionRejectReason_TAG_SPECIFIED_WITHOUT_A_VALUE_TEXT
        if reason == fix.SessionRejectReason_VALUE_IS_INCORRECT: return fix.SessionRejectReason_VALUE_IS_INCORRECT_TEXT
        if reason == fix.SessionRejectReason_INCORRECT_DATA_FORMAT_FOR_VALUE: return fix.SessionRejectReason_INCORRECT_DATA_FORMAT_FOR_VALUE_TEXT
        if reason == fix.SessionRejectReason_DECRYPTION_PROBLEM: return fix.SessionRejectReason_DECRYPTION_PROBLEM_TEXT
        if reason == fix.SessionRejectReason_SIGNATURE_PROBLEM: return fix.SessionRejectReason_SIGNATURE_PROBLEM_TEXT
        if reason == fix.SessionRejectReason_COMPID_PROBLEM: return fix.SessionRejectReason_COMPID_PROBLEM_TEXT
        if reason == fix.SessionRejectReason_SENDINGTIME_ACCURACY_PROBLEM: return fix.SessionRejectReason_SENDINGTIME_ACCURACY_PROBLEM_TEXT
        if reason == fix.SessionRejectReason_INVALID_MSGTYPE: return fix.SessionRejectReason_INVALID_MSGTYPE_TEXT
        if reason == fix.SessionRejectReason_XML_VALIDATION_ERROR: return "XML Validation Error"
        if reason == fix.SessionRejectReason_TAG_APPEARS_MORE_THAN_ONCE: return fix.SessionRejectReason_TAG_APPEARS_MORE_THAN_ONCE_TEXT
        if reason == fix.SessionRejectReason_TAG_SPECIFIED_OUT_OF_REQUIRED_ORDER: return fix.SessionRejectReason_TAG_SPECIFIED_OUT_OF_REQUIRED_ORDER_TEXT
        if reason == fix.SessionRejectReason_REPEATING_GROUP_FIELDS_OUT_OF_ORDER: return "Repeating Group fields out of order"
        if reason == fix.SessionRejectReason_INCORRECT_NUMINGROUP_COUNT_FOR_REPEATING_GROUP: return fix.SessionRejectReason_INCORRECT_NUMINGROUP_COUNT_FOR_REPEATING_GROUP_TEXT
        if reason == fix.SessionRejectReason_NON_DATA_VALUE_INCLUDES_FIELD_DELIMITER: return "Non 'data' value includes field delimiter (SOH character)"
        if reason == fix.SessionRejectReason_OTHER: return "Other"    
        
    def getTradSesStatus(self, status):
        if status == fix.TradSesStatus_UNKNOWN: return "Unknown"
        if status == fix.TradSesStatus_HALTED: return "Halted"
        if status == fix.TradSesStatus_OPEN: return "Open"
        if status == fix.TradSesStatus_CLOSED: return "Closed"
        if status == fix.TradSesStatus_PRE_CLOSE: return "Pre-Close"
        if status == fix.TradSesStatus_PRE_OPEN: return "Pre-Open"
        if status == fix.TradSesStatus_REQUEST_REJECTED: return "Request Rejected"
     
    def getTradingSessionSubId(self, subId):
        if subId == '0': return "Pre-Trading"
        if subId == '1': return "Trading"
        if subId == '2': return "Post-Trading"
        if subId == '3': return "After Hour"
        if subId == '4': return "Closed"
        
    def getCxlRejReason(self, reason):
        if reason == fix.CxlRejReason_TOO_LATE_TO_CANCEL: return "Too late to Cancel"
        if reason == fix.CxlRejReason_UNKNOWN_ORDER: return "Unknown order"
        if reason == fix.CxlRejReason_OTHER: return "Other"
        
    def getMDReqRejReason(self, reason):
        if reason == fix.MDReqRejReason_UNKNOWN_SYMBOL: return "Unknown symbol"
        if reason == fix.MDReqRejReason_DUPLICATE_MDREQID: return "Duplicate MDReqID"
        if reason == fix.MDReqRejReason_INSUFFICIENT_BANDWIDTH: return "Insufficient Bandwidth"
        if reason == fix.MDReqRejReason_INSUFFICIENT_PERMISSIONS: return "Insufficient Permissions"
        if reason == fix.MDReqRejReason_UNSUPPORTED_SUBSCRIPTIONREQUESTTYPE: return "Unsupported Subscription Request Type"
        if reason == fix.MDReqRejReason_UNSUPPORTED_MARKETDEPTH: return "Unsupported MarketDepth"
        if reason == fix.MDReqRejReason_UNSUPPORTED_MDUPDATETYPE: return "Unsupported MDUpdateType"
        if reason == fix.MDReqRejReason_UNSUPPORTED_AGGREGATEDBOOK: return "Unsupported AggregatedBook"
        if reason == fix.MDReqRejReason_UNSUPPORTED_MDENTRYTYPE: return "Unsupported MDEntryType"
        
    def getTimeInForce(self, time):
        if time == fix.TimeInForce_DAY: return "Day"
        if time == fix.TimeInForce_GOOD_TILL_CANCEL: return "Good Till Cancel"
        if time == fix.TimeInForce_IMMEDIATE_OR_CANCEL: return "Immediate or Cancel"
        if time == fix.TimeInForce_FILL_OR_KILL: return "Fill or Kill"
        if time == fix.TimeInForce_GOOD_TILL_DATE: return "Good Till Date"
        if time == fix.TimeInForce_AT_CROSSING: return "At Crossing"
        if time == fix.TimeInForce_AT_THE_CLOSE: return "At the Close"
        if time == fix.TimeInForce_AT_THE_OPENING: return "At the Opening"
        if time == fix.TimeInForce_GOOD_THROUGH_CROSSING: return "Good Through Crossing"
        if time == fix.TimeInForce_GOOD_TILL_CROSSING: return "Good Till Crossing"        
        
    def getExecInstValue(self, value):
        if value == fix.ExecInst_ALL_OR_NONE: return "All or None"
        if value == fix.ExecInst_BEST_EXECUTION: return "Best Execution"
        if value == fix.ExecInst_CANCEL_IF_NOT_BEST: return "Cancel if Not Best"       
        
    def getSecurityTradingStatus(self, status):
        if status == fix.SecurityTradingStatus_TRADING_HALT: return "Trading Halt"
        if status == fix.SecurityTradingStatus_RESUME: return "Resume"
                
    """
    Messages
    """
    
    def testRequest(self, message):
        """
        Test Request
                
        Message Type = '1'.
        The test request message forces a heartbeat from the opposing application. The test request message
        checks sequence numbers or verifies communication line status. The opposite application responds to 
        the Test Request with a Heartbeat containing the TestReqID.
        """
        msg=self.buildMsgHeader("1")
        msg.setField(fix.TestReqID(str(message)))
        
        fix.Session.sendToTarget(msg)        

    def buildMsgHeader(self, msgType):
        """
        Message Header Builder
        """
        self.msg=msg = fix.Message()
        header = msg.getHeader()
        header.setField(fix.BeginString(fix.BeginString_FIXT11))
        header.setField(fix.MsgType(msgType))
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        return self.msg
    
    def newOrderSingle(self, symbol, side, quantity, price, orderType):
        """
        New Order - Single
        
        Message Type = 'D'.
        The New Order Single message is used by institutions to electronically submit orders to be executed by the
        exchange. Orders should have a unique identifier (tag ClOrdID <11>) assigned by the institution for a trading day.
        Orders with duplicate identifiers will be rejected by the exchange.
                
        Arguments:
            - symbol: string
            - side: char
            - quantity: int
            - price: float
            - orderType: char
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = D 
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (1)  Account = (string)
            - (11) ClOrdID = (string)
            - (38) OrderQty = (int)
            - (40) OrdType = 1 (Market) / 2 (Limit)            
            - (44) Price = (float)
            - (54) Side = 1 (Buy) / 2 (Sell)
            - (60) TransactTime = UTC Timestamp     
            - (55) Symbol = (string)            
            - (10) CheckSum = (string(3))       
        """
        
        clOrdId = self.getNextOrderID()
        details = {'clOrdId'  : clOrdId,
                   'symbol'   : symbol,
                   'side'     : side,
                   'quantity' : quantity,
                   'price'    : price,
                   'ordType'  : orderType                   
                   }
        
        # ---- Header
        
        msg = fix50.NewOrderSingle()        
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.Account(self.account))
        msg.setField(fix.ClOrdID(str(details['clOrdId'])))
        msg.setField(fix.OrderQty(details['quantity']))
        msg.setField(fix.OrdType(details['ordType']))
        msg.setField(fix.Price(details['price']))
        msg.setField(fix.Side(details['side']))
        msg.setField(fix.TransactTime())        
        msg.setField(fix.Symbol(details['symbol']))
        
        fix.Session.sendToTarget(msg)
        
    def orderCancelRequest(self, orderId, side, quantity, symbol):
        """
        Order Cancel Request
        
        Message Type = 'F'.
        The Order Cancel Request message requests the cancellation of all of the remaining quantity of an 
        existing order. The request will only be accepted if the order can successfully be pulled back from the
        exchange book without executing. A cancel request is assigned a ClOrdID and is treated as a separate
        entity. If rejected, the ClOrdID of the Cancel Request will be sent in the Cancel Reject message, as well
        as the ClOrdID of the actual order in the OrigClOrdID field. The ClOrdID assigned to the cancel request 
        must be unique amongst the ClOrdID assigned to regular orders and replacement orders. A successful 
        Order Cancel Request is replied to with an Execution Report message.       
        
        Arguments:
            - orderId: string
            - symbol: string
            - side: char
            - quantity: int
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = F  
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (11) ClOrdID = (string)
            - (37) OrderID = (string)
            - (54) Side = 1 (Buy) / 2 (Sell)
            - (60) TransactTime = UTC Timestamp
            - (1)  Account = (string)
            - (38) OrderQty = (int)
            - (55) Symbol = (string)            
            - (10) CheckSum = (string(3))       
        """
        
        clOrdId = self.getNextOrderID()
        details = {'clOrdId'  : clOrdId,
                   'symbol'   : symbol,
                   'side'     : side,
                   'quantity' : quantity ,
                   'orderId'  : orderId
                   }
       
        # ---- Header
        
        msg = fix50.OrderCancelRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.ClOrdID(str(details['clOrdId'])))
        msg.setField(fix.OrderID(str(details['orderId'])))
        msg.setField(fix.Side(details['side']))
        msg.setField(fix.TransactTime())
        msg.setField(fix.Account(self.account))
        msg.setField(fix.OrderQty(details['quantity']))
        msg.setField(fix.Symbol(details['symbol']))
        msg.setField(fix.SecurityExchange(self.targetCompID))
        
        fix.Session.sendToTarget(msg)
                
    def orderCancelReplaceRequest(self, orderId, origClOrdId, side, symbol, orderType, quantity=None, price=None):
        """
        Order Cancel/Replace Request
        
        Message Type = 'G'.
        
        The Order Cancel Replace Request message is used to change the parameters of a previously entered
        order. It may be used to change attributes of an order (i.e. reduce/increase quantity, change price).
        The Cancel/Replace request will only be accepted if the order can successfully be pulled back from the 
        exchange book without executing.
        
        Only the fields that are being changed need to be sent in the replacement message. Fields that are not
        sent are considered without changes. (FUNCIONA SOLAMENTE MANDANDO PRECIO Y CANTIDAD)
        If an order is successfully replaced, then it will generate a new OrderID for it, while the replaced order
        will be canceled.
                
        Arguments:
            - orderId: string
            - origClOrdId: string
            - symbol: string
            - side: char
            - orderType: char
            - quantity: int
            - price: float
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = F  
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (1)  Account = (string)
            - (11) ClOrdID = (string)
            - (37) OrderID = (string)
            - (40) OrdType = 1 (Market) / 2 (Limit)            
            - (41) OrigClOrdID = (string)
            - (44) Price = (float) CONDITIONAL
            - (54) Side = 1 (Buy) / 2 (Sell)
            - (60) TransactTime = UTC Timestamp
            - (55) Symbol = (string)          
            - (38) OrderQty = (int) CONDITIONAL             
            - (10) CheckSum = (string(3))       
        """
        
        clOrdId = self.getNextOrderID()
        details = {'clOrdId'        : clOrdId,
                   'origClOrdId'    : origClOrdId,
                   'symbol'         : symbol,
                   'side'           : side,
                   'quantity'       : quantity,
                   'price'          : price,
                   'orderId'        : orderId,
                   'ordType'        : orderType
                   }
        
        # ---- Header
        
        msg = fix50.OrderCancelReplaceRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.Account(self.account))
        msg.setField(fix.ClOrdID(str(details['clOrdId'])))
        msg.setField(fix.OrderID(str(details['orderId'])))
        msg.setField(fix.OrdType(details['ordType']))
        msg.setField(fix.OrigClOrdID(str(details['origClOrdId'])))
        if details['price'] is not None:
            msg.setField(fix.Price(float(details['price'])))
        msg.setField(fix.Side(details['side']))
        msg.setField(fix.TransactTime())        
        msg.setField(fix.Symbol(details['symbol']))        
        if details['quantity'] is not None:
            msg.setField(fix.OrderQty(int(details['quantity'])))        
            
        fix.Session.sendToTarget(msg)
                
    def orderStatusRequest(self, orderId, symbol, side):
        """
        Order Status Request
        
        Message Type = 'H'.
        The order status request message is used by the institution to generate an order status message back from
        the Exchange.
        
        Arguments:
            - orderId: string
            - symbol: string
            - side: char
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = H  
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (37) OrderID = (string)
            - (55) Symbol = (string)
            - (54) Side = 1 (Buy) / 2 (Sell)
            - (10) CheckSum = (string(3))       
        """
        
        details = {'symbol'         : symbol,
                   'side'           : side,
                   'orderId'        : orderId
                   }
        
        # ---- Header
        
        msg = fix50.OrderStatusRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.OrderID(str(details['orderId'])))
        msg.setField(fix.Symbol(details['symbol']))
        msg.setField(fix.Side(details['side']))
        
        fix.Session.sendToTarget(msg)    
    
    def orderMassStatusRequest(self, securityStatus):        
        """
        Order Mass Status Request
        
        Message Type = 'AF'.
        Message sent by the client to request status of orders meeting certain selection criteria.      
        
        Arguments:
            - securityStatus: string
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = AF   
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (584) MassStatusReqID = (string)
            - (585) MassStatusReqType = 7 (Status for all orders)
            - (965) SecurityStatus = 0 (All) / 1 (Actives) / 2 (Inactive)
            - (10) CheckSum = (string(3))       
        """
        
        # ---- Header
        
        msg = fix50.OrderMassStatusRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))

        # ---- Body

        msg.setField(fix.MassStatusReqID(randomString(5)))        
        msg.setField(fix.MassStatusReqType(fix.MassStatusReqType_STATUS_FOR_ALL_ORDERS))
        msg.setField(fix.SecurityStatus(securityStatus))
        
        fix.Session.sendToTarget(msg)
    
    def orderMassCancelRequest(self, marketSegment):
        """
        Order Mass Cancel Request
        
        Message Type = 'q'.
        Message sent by the client to request the cancellation of orders that meet certain selection creiteria.
        
        Arguments:
            - marketSegment: string
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = q 
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (530) MassCancelRequestType = 1 (Cancel orders for a security) / 4 (Cancel orders for a CFICode) / 7 (Cancel all orders)
            - (11) ClOrdID = (string)
            - (60) TransactTime = UTC Timestamp
            - (1300) MarketSegmentID = (string) / (DDF-DDA-DUAL-MERV)
            - (10) CheckSum = (string(3))       
        """
        
        msg = fix50.OrderMassCancelRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        msg.setField(fix.MassCancelRequestType(fix.MassCancelRequestType_CANCEL_ALL_ORDERS))
        msg.setField(fix.ClOrdID(str(self.getNextOrderID())))
        msg.setField(fix.TransactTime())        
        msg.setField(fix.MarketSegmentID(marketSegment))
    
        fix.Session.sendToTarget(msg)
        
    def marketDataRequest(self, entries, symbols, subscription=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES, depth=5):
        """
        Market Data Request
        
        Message Type = 'V'.
        A Market Data Request is a general request for market data on a specific security. A successful Market
        Data Request return one Market Data Full Snapshot message containing one or more Market Data Entries.
        
        Arguments:
            - entries: list of int/character
            - symbols: list of strings 
            - subscription: int (default: fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES)
            - depth: int (default: 5)
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = V   
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (262) MDReqID = (string)
            - (263) SubscriptionRequestType = 0 (Snapshot) / 1 (Snapshot+Updates) / 2 (Disable Previous Snapshot+Update)
            - (264) MarketDepth = 0 (Full book) / 1 (Top of Book) / N>1 (Best N price tiers of data)
            - (265) MDUpdateType = 0 (Full Refresh - Conditional field when 263=1)
            - (266) AggregatedBook = True (one book entry per side per price) / False (Multiple entries per side per price)
            - Block MDReqGrp:
                - (267) NoMDEntryTypes = (Int - contador de tipos de Entries)
                    - (269) MDEntryType = 0 (Bid) / 1 (Offer) / 2 (Trade) / 4 (Opening price) / 5 (Closing Price) / 6 (Settlement Price) /
                                            7 (Trading Session High Price) / 8 (Trading Session Low Price) / B (Trade Volume) / C (Open Interest)
            - Block InstrumentMDReqGrp:
                - (146) NoRelatedSym = (Int - contador de Tickers)
                    - (55) Symbol = (string - Ticker)
            - (10) CheckSum = (string(3))       
        """
        
        if len(entries) == 0 or len(symbols) == 0:
            return
        
        posibles_entries = [0,1,2,4,5,6,7,8,'B','C']
        
        if not all(elem in posibles_entries for elem in entries):
            return
        
        # ---- Header
        
        msg = fix50.MarketDataRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.MDReqID(randomString(5))) # Unique ID 
        msg.setField(fix.SubscriptionRequestType(subscription))
        msg.setField(fix.MarketDepth(depth))
        msg.setField(fix.MDUpdateType(0))
        msg.setField(fix.AggregatedBook(True))

        # ---- MDEntries 

        group=fix50.MarketDataRequest().NoMDEntryTypes()
        
        for entry in entries:        
            group.setField(fix.MDEntryType(str(entry)))
            msg.addGroup(group)

        # ---- Symbols
        
        norelatedsym = fix50.MarketDataRequest().NoRelatedSym()
        
        for symbol in symbols:       
            print(symbol)
            norelatedsym.setField(fix.Symbol(str(symbol)))
            msg.addGroup(norelatedsym)
                
        # -----------------------------------------

        fix.Session.sendToTarget(msg)
        
    def securityListRequest(self, criteria=fix.SecurityListRequestType_ALL_SECURITIES, symbol=None, cficode=None, subscription=fix.SubscriptionRequestType_SNAPSHOT):
        """
        Security List Request
        
        Message Type = 'x'.
        Used by the client to request the instrument definitions.
        
        Arguments:
            - criteria: int (default: fix.SecurityListRequestType_ALL_SECURITIES)
            - symbol: strings (default: None)
            - cficode: string (default: None)
            - subscription: int (default: fix.SubscriptionRequestType_SNAPSHOT)
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = V   
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (320) - SecurityReqID = (string)
            - (559) - SecurityListRequestType = 0 (Symbol) / 1 (Security/Type or CFICode) / 2 (Product) / 4 (All Securities)
            - (55) - Symbol = string
            - (461) - CFICode = (string)
            - (263) SubscriptionRequestType = 0 (Snapshot) / 1 (Snapshot+Updates) / 2 (Disable Previous Snapshot+Update)
            - (10) CheckSum = (string(3))       
        """
        
        if criteria == fix.SecurityListRequestType_SYMBOL and symbol is None:
            return
        if criteria == fix.SecurityListRequestType_SECURITYTYPE_AND_OR_CFICODE and cficode is None:
            return
        
        details = {'criteria'         : criteria,
                   'symbol'           : symbol,
                   'cficode'          : cficode,
                   'subscription'     : str(subscription)
                   }
        
        print(details)
        
        # ---- Header
        
        msg = fix50.SecurityListRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.SecurityReqID(randomString(5))) # Unique ID 
        msg.setField(fix.SecurityListRequestType(details['criteria']))
        
        if details['criteria'] == fix.SecurityListRequestType_SYMBOL:
            if details['symbol'] is not None:
                msg.setField(fix.Symbol(details['symbol']))
            else:
                return
        
        if details['criteria'] == fix.SecurityListRequestType_SECURITYTYPE_AND_OR_CFICODE:
            if details['cficode'] is not None:
                msg.setField(fix.Symbol(details['cficode']))
            else:
                return    
        
        msg.setField(fix.SubscriptionRequestType(details['subscription']))
        
        fix.Session.sendToTarget(msg) 
        
    def securityStatusRequest(self, subscription=fix.SubscriptionRequestType_SNAPSHOT, symbol='[N/A]'):
        """
        Security Status Request
        
        Message Type = 'e'.
        The Security Status Request message provides for the ability to request the status of a security. One or
        more Security Status message are returned as a result of a Security Status Request message.
        
        Arguments:
            - subscription: int (default: fix.SubscriptionRequestType_SNAPSHOT)
            - symbol: list of strings (default: '[N/A]')            
        
        Fields:
            - Header Group:
                - (8) BeginString = 'FIXT.1.1
                - (9) BodyLength = (Int)
                - (35) MsgType = e   
                - (1128) AppVerID = 9 (FIX50SP2)
                - (49) SenderCompID = usuario
                - (56) TargetCompID = 'ROFX'/'BYMA'
            - (324) - SecurityStatusReqID = (string)            
            - (55) - Symbol = string
            - (263) SubscriptionRequestType = 0 (Snapshot) / 1 (Snapshot+Updates) / 2 (Disable Previous Snapshot+Update)
            - (10) CheckSum = (string(3))       
        """
        
        details = {'symbol'           : symbol,                   
                   'subscription'     : str(subscription)
                   }
        
        # ---- Header
        
        msg = fix50.SecurityStatusRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.SecurityStatusReqID(randomString(5))) # Unique ID                 
        msg.setField(fix.Symbol(details['symbol']))        
        msg.setField(fix.SubscriptionRequestType(details['subscription']))
        
        fix.Session.sendToTarget(msg) 
        
    def tradeCaptureReportRequest(self, symbol=None):
        """
        Trade Capture Report Request for Regular Trades by Account
        
        Message Type = 'AD'.
        Request one or more trade capture reports based upon selection criteria provided on the trade capture
        report request.
        
        """
        
        # ---- Header
        
        msg = fix50.TradeCaptureReportRequest()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.TradeRequestID(randomString(5))) # Unique ID                 
        msg.setField(fix.TradeRequestType(fix.TradeRequestType_MATCHED_TRADES_MATCHING_CRITERIA_PROVIDED_ON_REQUEST))
        
        
        if symbol is None:        
            noPartyIds = fix50.TradeCaptureReportRequest().NoPartyIDs()     
            
            noPartyIds.setField(fix.PartyID(self.account))
            noPartyIds.setField(fix.PartyIDSource(fix.PartyIDSource_PROPRIETARY))
            noPartyIds.setField(fix.PartyRole(fix.PartyRole_CUSTOMER_ACCOUNT))
            
            msg.addGroup(noPartyIds)
        else:
            msg.setField(fix.Symbol(symbol))
        
        fix.Session.sendToTarget(msg) 
        
    def allocationInstruction(self, symbol, quantity, side):
        """
        Allocation Instruction
        
        Message Type = 'J'.
        The Allocation Instruction message provides the ability to specify how an order or set of orders should be
        subdivided amongst one or more accounts. Currenty used to request the allocation of the order to other of
        the broker accounts in case of an 'allocation'; or another account from a different broker in case of a 
        'giveup'.
        """
        
        # ---- Header
        
        msg = fix50.AllocationInstruction()
        header = msg.getHeader()
        header.setField(fix.SenderCompID(self.senderCompID))
        header.setField(fix.TargetCompID(self.targetCompID))
        
        # ---- Body
        
        msg.setField(fix.AllocID(randomString(5))) # Unique ID
        msg.setField(fix.AllocTransType(fix.AllocTransType_NEW))
        msg.setField(fix.AllocType(fix.AllocType_CALCULATED))
        
        msg.setField(fix.Symbol(symbol))
        msg.setField(fix.Quantity(quantity))
        msg.setField(fix.Side(side))
        msg.setField(fix.TradeDate('20200103'))
        
        fix.Session.sendToTarget(msg)
        
        
