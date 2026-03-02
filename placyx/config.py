import os

BASE_DIR = os.path.abspath(os.path.dirname("./instance"))

class Config:
    SECRET_KEY = "placyx-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "placyx.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True