import logging
import sys

def setup_logging():
    logger = logging.getLogger("sms_calendar_agent")
    
    # Ensure handlers aren't duplicated if this is imported multiple times
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler outputs to the terminal
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler writes to agent.log
        fh = logging.FileHandler('agent.log')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger

logger = setup_logging()
