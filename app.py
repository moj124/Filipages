import os
import datetime
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey, Text, DateTime
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, send_from_directory
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from helpers import login_required, apology, allowed_file

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# base file path of the main folder
basedir = os.path.abspath(os.path.dirname(__file__))

# Configure session to use filesystem (instead of signed cookies)
app.config['UPLOAD_FOLDER'] = os.path.join(basedir,'uploads')
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure sqlalchemy Library to use SQLite database
engine = create_engine('sqlite:///finals.db', echo=True)
meta = MetaData()

# Generate the initial databases 

# Users Table storing all relevant information for the user
users = Table(
    'users', meta,
    Column('id', Integer, primary_key=True),
    Column('username', String, nullable=False),
    Column('hash', String, nullable=False),
    Column('type', String, nullable=False))


# Posts table storing all relevant information for each posts published
# on the website
posts = Table(
    'posts', meta,
    Column('id', Integer, primary_key=True),
    Column('user', String, ForeignKey("users.username"), nullable=False),
    Column('title', String, nullable=False),
    Column('description', String, nullable=False),
    Column('location', String, nullable=False),
    Column('image',String),
    Column('text', Text, nullable=False),
    Column('date', DateTime, onupdate=datetime.datetime.now, nullable=False))


# execute the creation of the database
meta.create_all(engine)


# the main page of the website
# contains all added posts and the search function
@app.route("/")
def index():
    # connect to the database and query all posts generated
    with engine.connect() as connection:
        s = posts.select()
        rows = connection.execute(s)

        # render the main webpage given the all the posts stored
        return render_template("index.html", posts=rows)


# Add a new user's post to the database
@app.route('/add', methods=['GET', 'POST'])
@login_required
def upload_file():

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':
        # retrieve image file object form request form
        file = request.files['image']

        # query file for correct formating
        if file and allowed_file(file.filename):
            # retrieve the filename of the file securely
            #avoiding cross-scripting
            filename = secure_filename(file.filename)

            # save file to local upload folder
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # connect to the database
            # insert user's post details from the request form to the database
            with engine.connect() as connection:
                s = posts.insert().values(user = session["username"],
                    title = request.form.get("title"), description=request.form.get("description"), 
                    location=request.form.get("location") ,image = filename,
                    text = request.form.get("body"), date = datetime.datetime.now())
                connection.execute(s)

            # render management page of user's posts
            return redirect("/manage")
    else:
        # render the add page for creating user's posts
        return render_template('add.html')


# Search all posts for given location query for posts
# Return webpage of search
@app.route("/search", methods=["GET","POST"])
def search_posts():
    # query database for all matching posts given request form of post location
    with engine.connect() as connection:
        s = posts.select().where(posts.c.location == request.form.get("location"))
        rows = connection.execute(s)

        # render search webpage given location search and matched posts
        return render_template("search.html", rows = rows, location = request.form.get("location"))


# view current user's posts for editing or deletion
@app.route("/manage", methods=['GET','POST'])
@login_required
def manage_posts():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':  
        pass
    else: 
        # query database for the user's posts
        with engine.connect() as connection:
            s = posts.select().where(posts.c.user == session["username"])
            rows = connection.execute(s)

            # render the manage posts page with user's posts
            return render_template('manage.html', rows = rows)   


# View user's account details and allow user to edit details from database
@app.route("/account", methods=['GET', 'POST'])
@login_required
def manage_account():
    # get the user's details
    user = get_user()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == 'POST':

        # verify password validation for submitting changing detail's form request
        if user and check_password_hash(user.hash, request.form.get("current_password")):
            # update details for the current user
            with engine.connect() as connection:
                s = users.update().values(username=request.form.get("username"), 
                    hash=generate_password_hash(request.form.get("new_password"))).where(users.c.username == session["username"])
                connection.execute(s)
            
            #update the session to new user's username
            if session["username"] != request.form.get("username"):
                session["username"] =  request.form.get("username")

        # return error 
        else:
            return apology("current password is invalid")

        # present successful feedback to webpage
        flash("account detail's updated")

    # render the account webpage with user's details
    return render_template('account.html', user=user)


# verify user request form matches the database entry to login
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username
        with engine.connect() as connection:
            s = users.select().where(users.c.username == request.form.get("username"))
            row = connection.execute(s).fetchone()

            # Ensure username exists and password is correct
            if not row or not check_password_hash(row.hash, request.form.get("password")):
                flash("invalid username and/or password")
                return render_template("login.html")
            else:
                # Remember which user has logged in
                session["username"] = row.username

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

# Register the user given post request or get viewpage for registration
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # check request form is correctly filled
        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # check confirmation password matches password entry
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

         # Query database for username
        with engine.connect()  as connection:
            s = users.select().where(users.c.id == request.form.get("username"))
            rows = connection.execute(s)

            # if user exists return error
            if rows.scalar():
                return apology("username already taken", 403)

        # Query to insert user into database
        with engine.connect() as connection:
            s = users.insert().values(username=request.form.get("username"),
                    hash=generate_password_hash(request.form.get("password")), type="member")
            connection.execute(s)

        # return feedback to webpage
        flash("You have been registered")

        # redirect to the main page
        return redirect("/")
    else:
        # render the register page
        return render_template("register.html")


# clear the session and redirect to login page
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# view the post given the parameter post id
@app.route('/view/<int:post_id>')
@login_required
def post(post_id):
    # get post details from post_id parameter
    post = get_post(post_id)

    # return the post's page
    return render_template('post.html', post=post, image_path= basedir+"/uploads"+post["image"])


# Retrieve existing post details and render for editting given the post's id
# any changes will be uploaded to the database
@app.route("/edit/<int:post_id>", methods=["GET","POST"])
@login_required
def edit_post(post_id):

    # get post details from post_id parameter
    post = get_post(post_id)

    # query if request is posting to this route
    if request.method == "POST":
        # retrieve the image file object from the request form
        file = request.files['image']

        # query file for correct formating
        if file and allowed_file(file.filename):
            # retrieve the filename of the file securely
            #avoiding cross-scripting
            filename = secure_filename(file.filename)

            # save file to local upload folder
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # connect to the database
            with engine.connect() as connection:
                # update query to insert new post to database
                s = posts.update().values(title=request.form.get("title"), location=request.form.get("location"), description=request.form.get("description"),
                image=filename, text= request.form.get("body"), date = datetime.datetime.now()).where(posts.c.id == post_id)
                connection.execute(s)
        else:
            # connect to the database
            with engine.connect() as connection:
                # update query to insert new post to database
                # given file form wasn't filled out by user
                s = posts.update().values(title=request.form.get("title"), location=request.form.get("location"),
                description=request.form.get("description"), text= request.form.get("body"),
                date = datetime.datetime.now()).where(posts.c.id == post_id)
                connection.execute(s)

        # show successful feedback to webpage
        flash("post updated")

        return redirect("/manage")
    else:
        return render_template("edit.html", post=post)


# Delete the post from the database given the url's parameter for post_id
@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    # connect to the database
    with engine.connect() as connection:
        # select the post with matching post id
        s = posts.delete().where(posts.c.id == post_id)
        connection.execute(s)

        # show successful feedback to webpage
        flash("Post deleted")

        return redirect("/manage")


# Retrieve the image file from the local filesystem in the project folders
# given the url's query for filename
@app.route('/<path:filename>') 
def send_file(filename): 
    return send_from_directory('uploads', filename)


# A function that retrieves the user's details given the in-session data
def get_user():
    # connect to the database
    with engine.connect() as connection:
        # select the user with matching username
        s = users.select().where(users.c.username == session["username"])
        user = connection.execute(s).fetchone()

        #if user doesn't exist return error page
        if user is None:
            apology("Error with fetching user")
        return user


# a function that returns the post's contents from the database
# given the post's id
def get_post(post_id):

    # connect to the database
    with engine.connect() as connection:
        # select the post with matching post's id
        s = posts.select().where(posts.c.id == post_id)
        post = connection.execute(s).fetchone()

        #if post doesn't exist return error page
        if post is None:
            apology("Error with fetching post")
        return post



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
