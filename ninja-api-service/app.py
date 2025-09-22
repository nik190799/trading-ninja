# web server for api calls
import firebase_admin
from firebase_admin import credentials
from flask import Flask, render_template

# Initialize Firebase Admin SDK
# Note: The GOOGLE_APPLICATION_CREDENTIALS environment variable should be set
# to the path of your serviceAccountKey.json file.
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Initialize the Flask application
# The static_folder path has been corrected from '../static' to 'static'.
# This path is now correct for the Docker container's file structure.
app = Flask(__name__, static_folder='static', template_folder='templates')


@app.route('/')
def home():
    """
    Renders the main homepage.
    The template is loaded from the 'templates' directory.
    """
    return render_template('index.html', title='Trading Ninja Home')


@app.route('/api/status')
def api_status():
    """
    A simple API endpoint to check the service status.
    """
    return {
        "status": "ok",
        "service": "ninja-api-service"
    }


if __name__ == '__main__':
    # This block is for local development.
    # Gunicorn runs the app in the Cloud Run container.
    app.run(host='0.0.0.0', port=8080, debug=True)
