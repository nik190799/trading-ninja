AI Stock Prediction Dashboard - Backend Server
This project contains the Python backend server that powers the AI Stock Prediction Dashboard. It uses Flask to create an API that calls AI models (GPT-5 and Grok-4) to generate stock predictions.

Project Structure
server.py: The main Flask application file. It exposes the API endpoints.

stock_predictions.html: The frontend user interface (updated to use the API).

GPT.py, GROK.py, main.py: Your original Python helper scripts.

requirements.txt: A list of Python packages required to run the server.

.env: A file to store your secret API keys (you need to create this).

Setup and Running the Server
Follow these steps to get the backend server running.

1. Prerequisites
Python 3.8 or newer.

An OpenAI API key.

An xAI (Grok) API key.

2. Install Dependencies
Install all the required Python packages using pip and the requirements.txt file.

pip install -r requirements.txt

3. Create .env file for API Keys
Create a file named .env in the same directory as server.py. This file will hold your secret API keys. Add your keys to it like this:

OPENAI_API_KEY="your_openai_api_key_here"
XAI_API_KEY="your_xai_api_key_here"

Important: Do not share this file or commit it to version control.

4. Run the Server
Start the Flask server by running the server.py script from your terminal:

python server.py

You should see output indicating that the server is running on http://127.0.0.1:5000.

5. View the Dashboard
With the server running, open the stock_predictions.html file in your web browser. It will now connect to your local server, fetch the live AI-powered predictions, and display them. The data will refresh every 5 minutes.