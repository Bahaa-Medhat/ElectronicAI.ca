# ElectronicAI.ca

A Flask-based web application that allows users to register, log in, chat with an AI powered by the Google Gemini API, and search for electronic components using the Nexar API. All chat history is stored in a local SQLite database.

## Features

- User registration and authentication (Flask-Login)
- Secure password hashing (Werkzeug)
- Chat interface with AI responses (Google Gemini API)
- Chat history stored in SQLite (SQLAlchemy)
- Asynchronous API calls for fast AI responses (httpx)
- Electronic component search via Nexar API
- Environment variable support via python-dotenv

## Requirements

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/)
- Google Gemini API key
- Nexar API credentials

## Setup

1. **Clone the repository:**
    ```sh
    git clone https://github.com/Bahaa-Medhat/ElectronicAI.ca.git
    ```

2. **Create and activate a virtual environment (optional but recommended):**
    ```sh
    python -m venv venv
    venv\Scripts\activate
    ```

3. **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up environment variables:**

    Create a `.env` file in the project root with the following content:
    ```
    SECRET_KEY=your_secret_key
    GEMINI_API_KEY=your_gemini_api_key
    NEXAR_CLIENT_ID=your_nexar_client_id
    NEXAR_CLIENT_SECRET=your_nexar_client_secret
    ```

5. **Initialize the database:**
    ```sh
    python
    >>> from app import db
    >>> db.create_all()
    >>> exit()
    ```

6. **Run the application:**
    ```sh
    python app.py
    ```

7. **Open your browser and go to:**
    ```
    http://127.0.0.1:5000/
    ```

## Usage

- Register a new user account.
- Log in with your credentials.
- Start chatting with the AI!
- View your chat history on the `/history` page.
- Search for electronic components in the Browse Components section.

## Technologies Used

- Flask
- Flask-Login
- Flask-SQLAlchemy
- httpx (for async API calls)
- requests (for Nexar API)
- python-dotenv
- Google Gemini API
- Nexar API

## License

This project is licensed under the MIT License.

---

**Note:**  
You must have valid Google Gemini and Nexar API credentials to use all features.