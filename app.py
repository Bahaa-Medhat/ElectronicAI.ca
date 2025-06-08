from flask import Flask, render_template, request, jsonify
import json
import os 
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

load_dotenv()  

# --- Flask app setup ---#
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#--- Models ---#
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10))
    message = db.Column(db.Text)

#--- User Loader ---#
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#--- Auth Routes ---#
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return render_template('index.html')
        flash('Login failed. Check email and password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#--- Main Routes ---#
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html')
    else:
        return render_template('login.html')

@app.route('/history')
@login_required
def history():
    messages = ChatMessage.query.all()
    return render_template('history.html', messages=messages)

#--- Chat Route ---#
@app.route('/chat', methods=['POST'])
@login_required
async def chat():
    user_message = request.json.get('message')
    print(f"User message received: {user_message}")

    user_entry = ChatMessage(role='user', message=user_message)
    db.session.add(user_entry)

    chat_history = []
    chat_history.append({ "role": "user", "parts": [{ "text": user_message }] })
    payload = { "contents": chat_history }

    api_key = os.getenv("GEMINI_API_KEY")
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    ai_response = "I'm sorry, I couldn't get a response from the AI at this moment. Please try again later."

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload, headers={'Content-Type': 'application/json'})

            print(f"Gemini API Response Status: {response.status_code}")
            print(f"Gemini API Response Body: {response.text}")

            response.raise_for_status()

            result = response.json()

            if result.get('candidates') and len(result['candidates']) > 0 and \
               result['candidates'][0].get('content') and \
               result['candidates'][0]['content'].get('parts') and \
               len(result['candidates'][0]['content']['parts']) > 0:
                ai_response = result['candidates'][0]['content']['parts'][0]['text']
            else:
                print("Unexpected response structure from Gemini API. Result:", result)
                ai_response = "I received an unexpected response structure from the AI. Please try rephrasing your question."

    except httpx.RequestError as e:
        print(f"Request to Gemini API failed due to network, DNS, or timeout issue: {e}")
        ai_response = "Failed to connect to the AI service. Please check your network connection, ensure 'httpx' is installed, or try again later."
    except httpx.HTTPStatusError as e:
        print(f"Gemini API returned an HTTP error: Status {e.response.status_code} - Response: {e.response.text}")
        ai_response = f"The AI service returned an error (Status: {e.response.status_code}). Please try again with a different query. Details: {e.response.text[:100]}..."
    except Exception as e:
        print(f"An unexpected error occurred during AI response generation: {e}")
        ai_response = "An internal error occurred while processing your request."

    ai_entry = ChatMessage(role='ai', message=ai_response)
    db.session.add(ai_entry)
    db.session.commit()
    return jsonify({'response': ai_response})

#--- Main Entry Point ---#
if __name__ == '__main__':
    app.run(debug=True)