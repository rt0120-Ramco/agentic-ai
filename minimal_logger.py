"""
Minimal Logger Utility
======================

Simple logging utility for development and debugging.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

class MinimalLogger:
    """Simple logger for debugging and development"""
    
    def __init__(self, name: str = "minimal_logger", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Add console handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_method_entry(self, method: str, params: Any, cls: str = ""):
        """Log method entry"""
        timestamp = datetime.now().isoformat()
        self.logger.debug(f"[{timestamp}] {cls}.{method} ENTRY: {params}")
    
    def log_method_exit(self, method: str, result: Any, cls: str = ""):
        """Log method exit"""
        timestamp = datetime.now().isoformat()
        self.logger.debug(f"[{timestamp}] {cls}.{method} EXIT: {result}")
    
    def log_execution_flow(self, step: str, details: str = "", cls: str = ""):
        """Log execution flow"""
        timestamp = datetime.now().isoformat()
        self.logger.info(f"[{timestamp}] {cls}: {step} - {details}")
    
    def log_decision(self, decision: str, reasoning: str, cls: str = ""):
        """Log decision points"""
        timestamp = datetime.now().isoformat()
        self.logger.info(f"[{timestamp}] {cls} DECISION: {decision} | {reasoning}")
    
    def log_error(self, error: Exception, context: str = "", cls: str = ""):
        """Log errors"""
        timestamp = datetime.now().isoformat()
        self.logger.error(f"[{timestamp}] {cls} ERROR: {context} - {str(error)}")
    
    def log_api_request(self, url: str, params: Dict[str, Any], headers: Dict[str, str]):
        """Log API requests"""
        timestamp = datetime.now().isoformat()
        self.logger.debug(f"[{timestamp}] API REQUEST: {url} | Params: {params} | Headers: {list(headers.keys())}")

# Create default instance
minimal_logger = MinimalLogger()

# Decorator for debug method tracing
def minimal_debug_method(func):
    """Decorator for automatic method entry/exit logging"""
    def wrapper(*args, **kwargs):
        cls_name = args[0].__class__.__name__ if args else ""
        minimal_logger.log_method_entry(func.__name__, {"args": len(args), "kwargs": list(kwargs.keys())}, cls_name)
        
        try:
            result = func(*args, **kwargs)
            minimal_logger.log_method_exit(func.__name__, "Success", cls_name)
            return result
        except Exception as e:
            minimal_logger.log_error(e, f"in {func.__name__}", cls_name)
            raise
    
    return wrapper