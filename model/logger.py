# -*- coding: utf-8 -*-
"""
Created on Mon Nov 25 12:18:35 2019

@author: mdamelio
"""

import logging

def setup_logger(logger_name, log_file, level=logging.DEBUG): #.INFO
    lz = logging.getLogger(logger_name)
    formatter = logging.Formatter(u'%(asctime)s : %(message)s')
    fileHandler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fileHandler.setFormatter(formatter)
    lz.setLevel(level)
    lz.addHandler(fileHandler)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)
    lz.addHandler(streamHandler) 