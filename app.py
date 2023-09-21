from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # User Stock n Shares and balance
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM portfolio WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE user_id = :user_id", user_id=session["user_id"])[0]["cash"]
    cash = round(cash,2)
    print(f"total cash: {cash}")

    # Initialize total_value with the cash balance
    total_value = cash

    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        stock["value"] = quote["price"] * stock["total_shares"]
        total_value += stock["value"]  # Add the value of each stock to the total
        total_value = round(total_value,2)



    return render_template("index.html", stocks=stocks, cash=usd(cash), total_value=usd(total_value))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            return apology("Must Provide Symbol")
        elif not shares or not shares.isdigit() or int(shares) <= 0:
            return apology("Must provide a minimum of 1 shares")

        quote = lookup(symbol)
        if quote is None:
            return apology("Symbol not found")

        price = quote["price"]
        total_cost = int(shares) * price
        cash = db.execute("SELECT cash FROM users WHERE user_id = ?",session["user_id"])[0]["cash"]

        if cash < total_cost:
            return apology("You have insufficient amount to buy")

        # Update user balance
        db.execute("UPDATE users SET cash = cash - :total_cost WHERE user_id = :user_id", total_cost=total_cost, user_id=session["user_id"])

        # Add purchase to history and portfolio
        action = "BUY"
        db.execute("INSERT INTO history (user_id, symbol, shares, action, price) VALUES (:user_id, :symbol, :shares, :action, :price)",user_id=session["user_id"], symbol=symbol, shares=shares, action=action, price=price)
        db.execute("INSERT INTO portfolio (user_id, symbol, shares) VALUES (:user_id, :symbol, :shares)",user_id=session["user_id"], symbol=symbol, shares=shares)

        flash(f"You bought {shares} shares of {symbol} for {usd(total_cost)}!")
        return redirect("/")

    else:
        return render_template("buy.html")




@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM history WHERE user_id = :userid", userid=session["user_id"])

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["user_id"]

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
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if not quote:
            return apology("Invalid Symbol",400)
        return render_template("quote.html",quote=quote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Registering User"""
    # Clear User Session First
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Must Provide Username!",400)
        elif not request.form.get("password"):
            return apology("Must Provide Password!",400)
        elif not request.form.get("confirmation"):
            return apology("Must Confirm Password",400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password do not match",400)

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

    # Check if user already exists in DB
        if len(rows) != 0:
            return apology("Username already exists",400)

    # Add user into DB
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

    # Query database for the user that just created
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

    # Log user in
        session["user_id"] = rows[0]["user_id"]
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "GET":
        symbols = db.execute("SELECT symbol FROM portfolio WHERE user_id = :user_id", user_id=session["user_id"])
        return render_template("sell.html", symbols=symbols)
    else:
        user_id = session["user_id"]
        action = "SELL"
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not shares:
            return apology("Must provide shares")
        shares = int(shares)

        if not symbol:
            return apology("Must Provide Stock",403)

        sym_price = lookup(symbol)["price"]
        sym_name = lookup(symbol)["name"]
        price = shares * sym_price

        shares_owned = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?",user_id, symbol)[0]['shares']
        print(shares_owned)

        if shares > shares_owned:
            return apology("You dont have enough shares")

        # Update user cash in DB
        usrCash = db.execute("SELECT cash FROM users WHERE user_id = ?",user_id)[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE user_id = ?",usrCash + price, user_id)

        # Update User Portfolio and Add into History
        if shares == shares_owned:
            db.execute("DELETE FROM portfolio WHERE symbol = ?", symbol)
        db.execute("UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?", shares_owned - shares, user_id, symbol)
        db.execute("INSERT INTO history (user_id, symbol, shares, action, price)VALUES(?, ?, ?, ?, ?)",user_id, sym_name, -shares, action, sym_price)
        flash(f"You sold {shares} shares of {symbol} for {usd(price)}!")
        return redirect("/")






