import os
from dotenv import load_dotenv  # Import the dotenv library
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.search import SearchParameters, x_source

# Load environment variables from the .env file
load_dotenv()

# It's recommended to set your API key as an environment variable for security
client = Client(api_key=os.getenv("XAI_API_KEY"))

# Create a chat session with the grok-4 model
# Set a low temperature for more deterministic output
# Include a seed for reproducibility
chat = client.chat.create(
    model="grok-4",
    temperature=0.2,
    # Note: The 'seed' parameter is a common feature for reproducibility,
    # but its specific implementation in the xai_sdk may vary.
    # Check the library's documentation for the correct syntax.
    seed=12345,
    search_parameters=SearchParameters(
        mode="auto",
        sources=[x_source()],
    ),
)

# Append your updated query to the chat, including the current price
chat.append(user("Given NVIDIA's closing price of $177 today, provide 5 potential high-gain stock tickers. For each, what is a potential price target for September 19th, 2025? Give the answer in one line per stock, including the ticker, price target, and percentage change."))

# Get and print the response
response = chat.sample()
print(response.content)