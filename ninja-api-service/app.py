# web server for api calls
import firebase_admin
from firebase_admin import credentials, auth
from flask import Flask, render_template, request, jsonify
from functools import wraps

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")

# Initialize the Flask application.
# CORRECTED: The static_folder path is now 'static', which matches the
# directory structure inside the Docker container where '/app/static' exists.
app = Flask(__name__, static_folder='static', template_folder='templates')

def check_auth(f):
    """
    A decorator to protect endpoints that require authentication.
    It checks for a valid Firebase ID token in the Authorization header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        id_token = None
        if 'Authorization' in request.headers and request.headers['Authorization'].startswith('Bearer '):
            id_token = request.headers['Authorization'].split('Bearer ')[1]

        if not id_token:
            return jsonify({"message": "Authentication token is missing!"}), 401

        try:
            # Verify the ID token while checking if the token is revoked.
            decoded_token = auth.verify_id_token(id_token, check_revoked=True)
            # Add the user's UID to the request context for the decorated function to use.
            request.user = decoded_token
        except auth.RevokedIdTokenError:
            return jsonify({"message": "Token has been revoked."}), 401
        except auth.InvalidIdTokenError:
            return jsonify({"message": "Invalid authentication token!"}), 401
        except Exception as e:
            return jsonify({"message": f"An error occurred: {e}"}), 500

        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home():
    """Renders the main homepage."""
    return render_template('index.html', title='Trading Ninja Home')


@app.route('/api/status')
def api_status():
    """A simple public API endpoint to check the service status."""
    return {"status": "ok", "service": "ninja-api-service"}


@app.route('/api/profile')
@check_auth
def profile():
    """
    A protected endpoint that only authenticated users can access.
    It returns the user's profile information from the decoded token.
    """
    # The user's info is available in request.user from the check_auth decorator
    user_info = request.user
    return jsonify({
        "message": f"Welcome, you are authenticated as {user_info.get('name', 'Unknown')}!",
        "uid": user_info.get('uid'),
        "email": user_info.get('email')
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

