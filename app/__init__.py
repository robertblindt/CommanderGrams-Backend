from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS


# Create an instance of the flask class
app = Flask(__name__)


# Configure out app with a secret key
app.config.from_object(Config)

# add CORS to app
CORS(app, resources={r"/api/*": {'origins':'*'}})

# Create an instance of SQLAlchemy to represent our DB
db = SQLAlchemy(app)

# Create an instance of Migrate to handle the data migrations of our flask app
migrate = Migrate(app, db)

# Create an instance of Login Manager to handle authentication
login = LoginManager(app)
# This redirects Illegal requests due to not being logged in to the 'login' page.
login.login_view = 'login'
login.login_message = 'Hey you need to be logged in to do that!'
login.login_message_category = 'info'

from app.blueprints.api import api
app.register_blueprint(api)

# import all of the routes from the routes files
from app import routes, models