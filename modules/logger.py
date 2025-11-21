"""
Structured Logging Module

Provides centralized logging configuration with:
- JSON formatting for production
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Optional Sentry integration for error tracking
- Performance tracking helpers
"""
import logging
import os
import sys
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Try to import optional dependencies
try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False


class CustomJsonFormatter(logging.Formatter):
    """Custom JSON formatter that works without pythonjsonlogger"""
    
    def format(self, record):
        import json
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, 'job_id'):
            log_data['job_id'] = record.job_id
        if hasattr(record, 'email_count'):
            log_data['email_count'] = record.email_count
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'domain'):
            log_data['domain'] = record.domain
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(app=None):
    """Configure structured logging for the application
    
    Args:
        app: Optional Flask app instance for Sentry integration
        
    Returns:
        Configured logger instance
    """
    # Get log level from environment
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Create root logger
    logger = logging.getLogger('emailval')
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Use JSON formatter if available and enabled
    use_json = os.getenv('LOG_FORMAT', 'json').lower() == 'json'
    
    if use_json:
        if HAS_JSON_LOGGER:
            formatter = jsonlogger.JsonFormatter(
                '%(timestamp)s %(name)s %(levelname)s %(message)s',
                timestamp=True
            )
        else:
            formatter = CustomJsonFormatter()
    else:
        # Standard text format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Initialize Sentry if configured
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn and HAS_SENTRY and app:
        environment = os.getenv('ENVIRONMENT', 'production')
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            environment=environment,
            # Send errors and above to Sentry
            before_send=lambda event, hint: event if event.get('level') in ['error', 'fatal'] else None
        )
        logger.info(f"Sentry initialized for environment: {environment}")
    
    return logger


def get_logger(name: str = 'emailval') -> logging.Logger:
    """Get a logger instance
    
    Args:
        name: Logger name (default: 'emailval')
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class PerformanceTimer:
    """Context manager for tracking operation performance"""
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None, **extra_fields):
        self.operation_name = operation_name
        self.logger = logger or get_logger()
        self.extra_fields = extra_fields
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = int((time.time() - self.start_time) * 1000)
        
        if exc_type is None:
            # Success
            self.logger.info(
                f"{self.operation_name} completed",
                extra={'duration_ms': self.duration_ms, **self.extra_fields}
            )
        else:
            # Error
            self.logger.error(
                f"{self.operation_name} failed",
                extra={'duration_ms': self.duration_ms, **self.extra_fields},
                exc_info=True
            )


# Initialize default logger
_default_logger = None

def init_logger(app=None):
    """Initialize the default logger (call once at startup)"""
    global _default_logger
    _default_logger = setup_logging(app)
    return _default_logger


# Convenience functions for logging
def debug(msg: str, **kwargs):
    """Log debug message"""
    logger = _default_logger or get_logger()
    logger.debug(msg, extra=kwargs)


def info(msg: str, **kwargs):
    """Log info message"""
    logger = _default_logger or get_logger()
    logger.info(msg, extra=kwargs)


def warning(msg: str, **kwargs):
    """Log warning message"""
    logger = _default_logger or get_logger()
    logger.warning(msg, extra=kwargs)


def error(msg: str, **kwargs):
    """Log error message"""
    logger = _default_logger or get_logger()
    logger.error(msg, extra=kwargs)


def critical(msg: str, **kwargs):
    """Log critical message"""
    logger = _default_logger or get_logger()
    logger.critical(msg, extra=kwargs)

