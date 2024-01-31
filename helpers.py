import re
import urllib
import yfinance

from flask import redirect, session
from functools import wraps
#function decorator to ensure users log in
def login_required(f):
   
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Prepare API request
    symbol = symbol.upper()
    try:
        stock=yfinance.Ticker(urllib.parse.quote_plus(symbol)) 
        price=stock.info['currentPrice']   
        return {"name": symbol, "price": price, "symbol": symbol}
    except:
        return None
    
#validates an entered ticker and shares, gets quote
def ticker_error(ticker,shares):
    try:
        shares = int(shares)
    except:
        error = "number of shares must be an integer"
        return None, error
        
    if shares <= 0:
        
        error = "number of shares must be postive"
        return None, error

    quote = lookup(ticker)
    if quote is None:
        error = "stock not found"
        return None, error
    return quote, None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"

#ensure password is valid
def valid_password(password):
    password_length = len(password)
    if password_length > 20 or password_length < 8:
        return False
    regex = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*\W).+$"
    password_match = re.match(regex, password)
    return password_match is not None