import cs50
import os
import sqlalchemy
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *
from datetime import datetime
from datetime import timedelta

# latest sql capabilities - pasted
class SQL(object):
    def __init__(self, url):
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)
    def execute(self, text, *multiparams, **params):
        try:
            statement = sqlalchemy.text(text).bindparams(*multiparams, **params)
            result = self.engine.execute(str(statement.compile(compile_kwargs={"literal_binds": True})))
            # SELECT
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]
            # INSERT
            elif result.lastrowid is not None:
                return result.lastrowid
            # DELETE, UPDATE
            else:
                return result.rowcount
        except sqlalchemy.exc.IntegrityError:
            return None
        except Exception as e:
            raise RuntimeError(e)

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response


# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///task.db")

# Following is for Task Management

@app.route("/")
@login_required
def index():
    # List all data from database
    # statusNum: = 0 means completed tasks,  = 1 means open tasks
    openTask = db.execute("SELECT * FROM tasks WHERE userID=:userID and statusNum=:statusNum", \
        userID=session["user_id"], statusNum=1)
    closedTask = db.execute("SELECT * FROM tasks WHERE userID=:userID and statusNum=:statusNum", \
        userID=session["user_id"], statusNum=0)

    return render_template("index.html", openTask=openTask, closedTask=closedTask)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    """add a new task"""

    if request.method == "GET":
        return render_template("add.html")
    else:
        # fetch value from form
        taskName = request.form.get("taskName")
        taskCategory = request.form.get("taskCategory")
        priority = request.form.get("priority")

        if not taskName:
            flash('Must provide task name')
            return redirect(url_for("index"))
        if not taskCategory:
            flash('Must provide task category')
            return redirect(url_for("index"))
        if not priority:
            flash('Must provide task priority')
            return redirect(url_for("index"))

        db.execute("INSERT INTO tasks (userId, taskName, category, priority) \
                    VALUES(:userId, :taskName, :category, :priority)", userId=session["user_id"], taskName=taskName, \
                    category=taskCategory, priority=priority)

        return redirect(url_for("index"))

@app.route('/delete/<int:taskID>', methods=['GET'])
@login_required
def delete_task(taskID):
    """Deletes task from database"""

    db.execute("DELETE FROM tasks WHERE taskID=:taskID AND userID=:userID", taskID =taskID, userID=session["user_id"])
    return redirect(url_for("index"))

@app.route('/complete/<int:taskID>/<int:rate>', methods=['GET'])
@login_required
def complete_task(taskID, rate):
    """Complete task from database"""

    currentTime=datetime.now()

    # load current status
    currentStatus = db.execute("SELECT status FROM tasks WHERE userID=:userID AND taskID=:taskID",\
        userID=session["user_id"], taskID=taskID)[0]["status"]

    # check status scenarios
    if currentStatus == "Standby":
        flash('Task has not started yet')

    elif currentStatus == "In Progress":
        previousTime=db.execute("SELECT previousTime FROM tasks WHERE userID=:userID AND taskID=:taskID",\
            userID=session["user_id"], taskID=taskID)[0]["previousTime"]

        timeSpent=db.execute("SELECT timeSpent FROM tasks WHERE userID=:userID AND taskID=:taskID",\
            userID=session["user_id"], taskID=taskID)[0]["timeSpent"]

        timeChange = (currentTime-datetime.strptime(previousTime,'%Y-%m-%d %H:%M:%S')).seconds/60
        timeSpent += timeChange

        db.execute("UPDATE tasks SET previousTime=:previousTime, endTime=:endTime, timeSpent=:timeSpent, \
            status=:status, statusNum=:statusNum, rate=:rate WHERE taskID=:taskID AND userID=:userID", \
            taskID=taskID, userID=session["user_id"], previousTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), \
            endTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), \
            timeSpent=round(timeSpent,2), status="Completed", statusNum=0, rate=rate)

    else:
        db.execute("UPDATE tasks SET status=:status, endTime=:endTime, statusNum=:statusNum, rate=:rate \
            WHERE taskID=:taskID AND userID=:userID", \
            taskID=taskID, userID=session["user_id"], endTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), \
            status="Completed", statusNum=0, rate=rate)

    return redirect(url_for("index"))

@app.route('/track/<int:taskID>', methods=['GET'])
@login_required
def track(taskID):
    """ A pause and resume function to switch status and calculate time spent """

    # load current time as text string
    # currentTime = time.strftime('%Y-%m-%d %H:%M:%S')
    currentTime=datetime.now()

    # load current status
    currentStatus = db.execute("SELECT status FROM tasks WHERE userID=:userID AND taskID=:taskID",\
        userID=session["user_id"], taskID=taskID)[0]["status"]

    # Check Status
    if currentStatus == "Standby":
        timeSpent=0
        db.execute("UPDATE tasks SET previousTime=:previousTime, timeSpent=:timeSpent, status=:status \
            WHERE taskID=:taskID AND userID=:userID", \
            taskID=taskID, userID=session["user_id"], previousTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), \
            timeSpent=timeSpent, status="In Progress")

    elif currentStatus == "In Progress":
        previousTime=db.execute("SELECT previousTime FROM tasks WHERE userID=:userID AND taskID=:taskID",\
            userID=session["user_id"], taskID=taskID)[0]["previousTime"]

        timeSpent=db.execute("SELECT timeSpent FROM tasks WHERE userID=:userID AND taskID=:taskID",\
            userID=session["user_id"], taskID=taskID)[0]["timeSpent"]

        timeChange = (currentTime-datetime.strptime(previousTime,'%Y-%m-%d %H:%M:%S')).seconds/60
        timeSpent += timeChange

        db.execute("UPDATE tasks SET previousTime=:previousTime, timeSpent=:timeSpent, status=:status \
            WHERE taskID=:taskID AND userID=:userID", \
            taskID=taskID, userID=session["user_id"], previousTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), \
            timeSpent=round(timeSpent,2), status="Pause")
    else:
        db.execute("UPDATE tasks SET previousTime=:previousTime, status=:status WHERE taskID=:taskID AND userID=:userID", \
            taskID=taskID, userID=session["user_id"], previousTime=currentTime.strftime("%Y-%m-%d %H:%M:%S"), status="In Progress")

    return redirect(url_for("index"))

# only GET method
@app.route('/review', methods=['GET'])
@login_required
def review():
    '''
    Provides a summary of Time Spent and Rating filtered by category
    Listed in 7-day (week) increments
    '''

    # Past week's calculation
    daysInterval = 7
    currentTime=datetime.now()
    beginWeek=currentTime-timedelta(days=daysInterval)

    # Attention on boundary, strftime() will drop hours, minutes and seconds
    date1=beginWeek.strftime("%Y-%m-%d")
    date2=currentTime.strftime("%Y-%m-%d %H:%M:%S")

    # Filter uses Group By category. Use SUM() and AVG to calculate accumulated values in SQL
    # Filter endDate within date1 and date2
    # closed-boundary
    # reviewTask is a kind of array table
    reviewTask = db.execute("SELECT category, SUM(timeSpent) AS totalSpent, ROUND(AVG(rate),2) AS avgRate \
        FROM tasks WHERE userID=:userID AND statusNum=:statusNum AND endTime >= :date1 AND endTime <= :date2 GROUP BY category", \
        userID=session["user_id"], statusNum=0, date1=date1, date2=date2)

    # totalTime and averageRate are variables, not an array table. Use [0]["COLUMN NAME"] to extract the values only
    totalTime = db.execute("SELECT SUM(timeSpent) AS totalTime FROM tasks WHERE userID=:userID AND statusNum=:statusNum \
        AND endTime >= :date1 AND endTime <= :date2 ", \
        userID = session["user_id"], statusNum=0, date1=date1, date2=date2)[0]["totalTime"]
    averageRate = db.execute("SELECT AVG(rate) AS averageRate FROM tasks WHERE userID=:userID AND statusNum=:statusNum \
        AND endTime >= :date1 AND endTime <= :date2 ", \
        userID = session["user_id"], statusNum=0, date1=date1, date2=date2)[0]["averageRate"]

    # output format
    return render_template("review.html", reviewTask=reviewTask, today=currentTime.strftime("%m/%d/%Y"), weekAgo = beginWeek.strftime("%m/%d/%Y"), \
        totalTime=round(totalTime,2), averageRate=round(averageRate,2))
        # Note: If no tasks for a week, make sure review route and round method still work


# Following is for User Management

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash('Must provide username')
            return render_template("login.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash('Must provide password')
            return render_template("login.html")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username=:username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            flash('Invalid username and/or password')
            return render_template("login.html")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    '''
        Require that a user input a username.
        Flash an apology if the user’s input is blank or the username already exists.

        Require that a user input a password and then that same password again.
        Flash an apology if either input is blank or the passwords do not match.

        INSERT the new user into users,
        storing a hash of the user’s password, not the password itself.
        Odds are you’ll find pwd_context.hash of interest.
    '''

    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            flash('Must provide username')
            return render_template("register.html")

        # ensure password was submitted
        elif not request.form.get("password"):
            flash('Must provide password')
            return render_template("register.html")

        # ensure two passwords match
        elif request.form.get("password") != request.form.get("password_again"):
            flash('Password not match')
            return render_template("register.html")

        # create username in database
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", \
            username = request.form.get("username"), hash = pwd_context.hash(request.form.get("password")))

        if not result:
            flash('Username already exists')
            return render_template("register.html")

        # remember which user has logged in
        session["user_id"] = result

        # redirect user to homepage
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

# Required Addon - pasted
if __name__ == '__main__':
 app.debug = True
 port = int(os.environ.get("PORT", 5000))
 app.run(host='0.0.0.0', port=port)
