from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import check_password_hash, generate_password_hash

import helpers


# create the extension
db = SQLAlchemy()
# create the app
app = Flask(__name__)
# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///finance.db"
# initialize the app with the extension
db.init_app(app)
# migration for db changes
migrate = Migrate(app, db)

# Custom filter
app.jinja_env.filters["usd"] = helpers.usd

# Configure session to use filesystem (instead of signed cookies)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

#User table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    hash = db.Column(db.String(60),nullable=False)
    cash = db.Column(db.Float,nullable=False)
    portfolio = db.relationship('Portfolio', backref='user', lazy=True)
    transaction = db.relationship('Transaction', backref='user',lazy=True)
#table for portfolio data
class Portfolio(db.Model):
    asset_id=db.Column(db.Integer, primary_key=True)
    ticker=db.Column(db.String(10),nullable=False)
    shares=db.Column(db.Integer,nullable=False)
    user_id = db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(10),nullable=False)
    ticker=db.Column(db.String(10),nullable=False)
    shares=db.Column(db.Integer,nullable=False)
    user_id = db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@helpers.login_required
def index():
    """Show portfolio of stocks"""
    history = Portfolio.query.filter_by(user_id=session["user_id"])
    portfolio=[]
    for h in history:
        price = helpers.lookup(h.ticker)["price"]
        asset = {
            'ticker': h.ticker,
            'shares': h.shares,
            'price': price,
            'total': price * h.shares
        }
        portfolio.append(asset)
       
    user_info = User.query.filter_by(id=session["user_id"]).first()
    cash = user_info.cash
    return render_template("portfolio.html", portfolio=portfolio, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@helpers.login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # get number of shares plus symbol from form, then validate
        ticker = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        quote, error = helpers.ticker_error(ticker,shares)
        if error is not None:
            return render_template('buy.html', error = error)
        shares= int(shares)
        # check user has enough cash
        user_info=User.query.filter_by(id=session["user_id"]).first()
        cash = user_info.cash
        if shares * quote["price"] > cash:
            error="you don't have enough cash"
            return render_template('buy.html',error=error)

        # update db to reflect transaction
        transaction = Transaction(transaction_type='BUY',ticker=ticker,shares=shares,user_id=user_info.id)
        db.session.add(transaction)
        asset=Portfolio.query.filter_by(user_id=user_info.id,ticker=ticker).first()
        if not asset:
            new_asset=Portfolio(ticker=ticker,shares=shares,user_id=user_info.id)
            db.session.add(new_asset)
        else:
            asset.shares=asset.shares+shares
        user_info.cash=user_info.cash - shares * quote["price"]
        db.session.commit()


        return redirect('/')
    else:
        return render_template('buy.html')


@app.route("/history")
@helpers.login_required
def history():
    """Show history of transactions"""
    # get history from db and send to site
    history = db.session.execute(db.select(Transaction).where(Transaction.user_id == session['user_id'])).scalars()
    history = history.all()
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    error=None
    if request.method == "POST":
        username=request.form.get("username").lower()
        password=request.form.get("password")
        # Ensure username and password have been submitted
        if not username or not password:
            error="must provide username and password"
            return render_template('login.html',error=error)


        # Query database for username
        user = User.query.filter_by(username=username).first()

        # Ensure username exists and password is correct
        if not user or not check_password_hash(user.hash, password):
            error = "invalid username and/or password"
            return render_template('login.html',error=error)


        # Remember which user has logged in
        session["user_id"] = user.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@helpers.login_required
def quote():
    """Get stock quote."""
    # use API to get quote for a stock and return result as a dictionary.
    if request.method == "POST":
        error = None
        ticker = request.form.get("symbol").upper()
        quote = helpers.lookup(ticker)
        if quote is None:
            error = "inalid ticker"
            quote = {"name": "", "price": 0, "symbol": ""}
            return render_template("quote.html", quote=quote,error=error)

        return render_template("quote.html", quote=quote)
    else:
        quote = {"name": "", "price": 0, "symbol": ""}
        return render_template("quote.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # register user
    session.clear()
    if request.method == "POST":
        # get details from form and validate
        username = request.form.get("username").lower()
        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        if (not username) or (not password) or (not confirm_password):
            error = "must provide username and password"
            return render_template('register.html',error=error)
        elif password != confirm_password:
            error = "passwords must match"
            return render_template('register.html',error=error)
        else:
            if helpers.valid_password(password) == False:
                error = "password doesn't meet requirements"
                return render_template('register.html',error=error)

        if User.query.filter_by(username=username).first() is not None:
            error = "username already in use"
            return render_template('register.html',error=error)
        # add username and hash password to db
        password_hash = generate_password_hash(password)
        new_user=User(username=username,hash=password_hash,cash=1000.00)
        db.session.add(new_user)
        db.session.commit()

        return render_template("registration_success.html")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@helpers.login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # get symbol and shares from form, then validate
        ticker = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        quote,error = helpers.ticker_error(ticker,shares)
        if error is not None:
            return render_template('sell.html', error = error)
        shares = int(shares)
        user_info = User.query.filter_by(id=session['user_id']).first()
        #ensure user has enough shares
        asset = Portfolio.query.filter_by(user_id=session['user_id'],ticker=ticker).first()
        if not asset or asset.shares < shares:
            error = "you can't sell that stock"
            return render_template('sell.html',error=error)

        # update db to reflect sale
        if asset.shares == shares:
            db.session.delete(asset)
        else:
            asset.shares=asset.shares-shares
        user_info.cash= user_info.cash + shares * quote['price']
        transaction = Transaction(transaction_type='SELL',ticker=ticker,shares=shares,user_id=session['user_id'])
        db.session.add(transaction)
        db.session.commit()
        return redirect("/")

    else:
        assets = db.session.execute(db.select(Portfolio.ticker).order_by(Portfolio.ticker)).scalars()
        assets = assets.all()

        return render_template("sell.html", assets=assets)
