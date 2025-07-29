from flask import Flask

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = 'thisisthesecretkey'
    app.config['UPLOAD_FOLDER'] = 'website/static/uploads'

    return app
