"""video-service: camera registry for the soufiane-easy platform."""
from flask_sqlalchemy import SQLAlchemy

# Single shared SQLAlchemy handle, bound to the app in run.py::create_app().
db = SQLAlchemy()
