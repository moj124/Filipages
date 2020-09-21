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

users = Table(
    'users', meta,
    Column('id', Integer, primary_key=True),
    Column('username', String, nullable=False),
    Column('hash', String, nullable=False),
    Column('type', String, nullable=False))

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

meta.create_all(engine)

@app.route("/")
@login_required
def index():
    with engine.connect() as connection:
        s = posts.select()
        rows = connection.execute(s)
        return render_template("index.html", posts=rows)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def upload_file():
    if request.method == 'POST':
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            with engine.connect() as connection:
                s = posts.insert().values(user = session["username"],
                    title = request.form.get("title"), description=request.form.get("description"), 
                    location=request.form.get("location") ,image = filename,
                    text = request.form.get("body"), date = datetime.datetime.now())
                connection.execute(s)

            return redirect("/manage")
    else:
        return render_template('add.html')


@app.route("/search", methods=["GET","POST"])
@login_required
def search_posts():
    with engine.connect() as connection:
        s = posts.select().where(posts.c.location == request.form.get("location"))
        rows = connection.execute(s)
        return render_template("search.html", rows = rows, location = request.form.get("location"))


@app.route("/manage", methods=['GET','POST'])
@login_required
def manage_posts():
    if request.method == 'POST':  
        pass
    else: 
        with engine.connect() as connection:
            s = posts.select().where(posts.c.user == session["username"])
            rows = connection.execute(s)
            return render_template('manage.html', rows = rows)   


@app.route("/account", methods=['GET', 'POST'])
@login_required
def manage_account():

    user = get_user()

    if request.method == 'POST':
        with engine.connect() as connection:
            s = users.select().where(users.c.username == session["username"])
            row = connection.execute(s).fetchone()

            if row and check_password_hash(row.hash, request.form.get("current_password")):
                with engine.connect() as connection:
                    s = users.update().values(username=request.form.get("username"), 
                        hash=generate_password_hash(request.form.get("new_password"))).where(users.c.username == session["username"])
                    connection.execute(s)
                
                if session["username"] != request.form.get("username"):
                    session["username"] =  request.form.get("username")

            else:
                return apology("current password is invalid")

            flash("account detail's updated")

    return render_template('account.html', user=user)


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


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

         # Query database for username
        with engine.connect()  as connection:
            s = users.select().where(users.c.id == request.form.get("username"))
            rows = connection.execute(s)

            if rows.scalar():
                return apology("username or password already registered", 403)

         # Query to insert user into database
        with engine.connect() as connection:
            s = users.insert().values(username=request.form.get("username"),
                    hash=generate_password_hash(request.form.get("password")), type="member")
            connection.execute(s)

        flash("You have been registered")

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route('/view/<int:post_id>')
@login_required
def post(post_id):
    post = get_post(post_id)
    print(os.path.join(basedir,'uploads'))
    return render_template('post.html', post=post, image_path= basedir+"/uploads"+post["image"])


@app.route("/edit/<int:post_id>", methods=["GET","POST"])
@login_required
def edit_post(post_id):

    post = get_post(post_id)

    if request.method == "POST":
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            with engine.connect() as connection:
                s = posts.update().values(title=request.form.get("title"), location=request.form.get("location"), description=request.form.get("description"),
                image=filename, text= request.form.get("body"), date = datetime.datetime.now()).where(posts.c.id == post_id)
                connection.execute(s)
        else:
            with engine.connect() as connection:
                s = posts.update().values(title=request.form.get("title"), location=request.form.get("location"),
                description=request.form.get("description"), text= request.form.get("body"),
                date = datetime.datetime.now()).where(posts.c.id == post_id)
                connection.execute(s)

        flash("post updated")
        return redirect("/manage")
    else:
        return render_template("edit.html", post=post)

@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    with engine.connect() as connection:
        s = posts.delete().where(posts.c.id == post_id)
        connection.execute(s)
        flash("Post deleted")
        return redirect("/manage")


@app.route('/<path:filename>') 
def send_file(filename): 
    return send_from_directory('uploads', filename)


def get_user():
    with engine.connect() as connection:
        s = users.select().where(users.c.username == session["username"])
        user = connection.execute(s).fetchone()
        if user is None:
            apology("Error with fetching user")
        return user

def get_post(post_id):
    with engine.connect() as connection:
        s = posts.select().where(posts.c.id == post_id)
        post = connection.execute(s).fetchone()
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
