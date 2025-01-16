from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = "app/epub_files"  # Directory to store EPUB files
    app.config['SECRET_KEY'] = 'askjhf32khr98ydshluih8'    # Required for CSRF protection in Flask forms

    # Register Blueprints
    from .routes import main
    app.register_blueprint(main)

    return app