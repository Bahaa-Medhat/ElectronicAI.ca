from flask import Flask, render_template, request, jsonify, send_file
import json
import os 
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from io import BytesIO

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SavedResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

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
            return redirect('/')
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
    messages = ChatMessage.query.filter_by(user_id=current_user.id).all()
    return render_template('history.html', messages=messages)

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Chat history cleared.', 'success')
    return redirect(url_for('history'))

#--- Chat Route ---#
@app.route('/chat', methods=['POST'])
@login_required
async def chat():
    user_message = request.json.get('message')
    print(f"User message received: {user_message}")

    user_entry = ChatMessage(role='user', message=user_message, user_id=current_user.id)
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

    ai_entry = ChatMessage(role='ai', message=ai_response, user_id=current_user.id)
    db.session.add(ai_entry)
    db.session.commit()
    return jsonify({'response': ai_response})

#--- Browse Component Route ---#
def get_nexar_token():
    import requests
    from dotenv import load_dotenv
    load_dotenv()

    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("NEXAR_CLIENT_ID"),
        "client_secret": os.getenv("NEXAR_CLIENT_SECRET"),
        "audience": "https://api.nexar.com/graphql"
    }

    res = requests.post("https://identity.nexar.com/connect/token", data=data)
    return res.json().get("access_token")

@app.route('/component_info')
def component_info():
    import requests

    part_name = request.args.get('q')
    if not part_name:
        return jsonify({"error": "Missing component query"}), 400

    try:
        def get_nexar_token():
            from dotenv import load_dotenv
            load_dotenv()

            data = {
                "grant_type": "client_credentials",
                "client_id": os.getenv("NEXAR_CLIENT_ID"),
                "client_secret": os.getenv("NEXAR_CLIENT_SECRET"),
                "audience": "https://api.nexar.com/graphql"
            }

            res = requests.post("https://identity.nexar.com/connect/token", data=data)
            return res.json().get("access_token")

        token = get_nexar_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        query = """
        query($q: String!) {
          supSearch(q: $q, limit: 1) {
            results {
              part {
                mpn
                manufacturer {
                  name
                }
                shortDescription
                images {
                  url
                }
              }
            }
          }
        }
        """

        response = requests.post(
            "https://api.nexar.com/graphql",
            headers=headers,
            json={"query": query, "variables": {"q": part_name}}
        )

        response.raise_for_status()

        data = response.json()
        results = data.get("data", {}).get("supSearch", {}).get("results", [])

        if not results:
            return jsonify({"error": "No components found"}), 404

        part = results[0]["part"]
        image_url = part.get("images", [{}])[0].get("url", "")
        name = part.get("mpn") or part.get("manufacturer", {}).get("name", part_name)

        return jsonify({
            "name": name,
            "manufacturer": part.get("manufacturer", {}).get("name"),
            "description": part.get("shortDescription"),
            "image": image_url,
            "datasheet": "Not available in this query"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#--- Save Response Route ---#
@app.route('/saved_responses')
@login_required
def saved_responses():
    user_saved_responses = SavedResponse.query.filter_by(user_id=current_user.id).order_by(SavedResponse.updated_at.desc()).all()
    return render_template('saved_responses.html', saved_responses=user_saved_responses)

@app.route('/update_response/<int:response_id>', methods=['POST'])
@login_required
def update_response(response_id):
    try:
        response_to_update = SavedResponse.query.get_or_404(response_id)

        # Ensure the current user owns this response
        if response_to_update.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        data = request.get_json()
        new_content = data.get('content')

        if not new_content:
            return jsonify({'success': False, 'message': 'Content cannot be empty.'}), 400

        response_to_update.content = new_content
        db.session.commit()
        return jsonify({'success': True, 'message': 'Response updated successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating response: {e}")
        return jsonify({'success': False, 'message': f'Error updating response: {str(e)}'}), 500

@app.route('/delete_response/<int:response_id>', methods=['POST'])
@login_required
def delete_response(response_id):
    try:
        response_to_delete = SavedResponse.query.get_or_404(response_id)

        # Ensure the current user owns this response
        if response_to_delete.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        db.session.delete(response_to_delete)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Response deleted successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting response: {e}")
        return jsonify({'success': False, 'message': f'Error deleting response: {str(e)}'}), 500

@app.route('/download_pdf/<int:response_id>', methods=['POST'])
@login_required
def download_pdf(response_id):
    # This route will receive the *current edited content* from the frontend,
    # not necessarily just what's in the database. This allows users to download
    # immediate edits without saving first.
    content_to_pdf = request.form.get('content')
    title_for_pdf = request.form.get('title', f"ElectronicAI_Response_{response_id}")

    if not content_to_pdf:
        flash("Could not generate PDF: content missing.", "danger")
        return redirect(url_for('saved_responses'))

    try:
        import pdfkit
        wkhtmltopdf_path = os.getenv('WKHTMLTOPDF_PATH')
        if not wkhtmltopdf_path:
            flash("wkhtmltopdf path not set. Please set WKHTMLTOPDF_PATH in your .env file.", "danger")
            return redirect(url_for('saved_responses'))

        # Define PDF options here
        options = {
            'encoding': 'UTF-8',
            'enable-local-file-access': None
        }

        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        pdf = pdfkit.from_string(content_to_pdf, False, options=options, configuration=config)

        response = send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{title_for_pdf.replace(' ', '_')}.pdf"
        )
        return response

    except ImportError:
        flash("PDF generation library (pdfkit) not installed. Please install it (`pip install pdfkit`) and wkhtmltopdf.", "danger")
        print("PDF generation library (pdfkit) not found. Please install it and wkhtmltopdf.")
        return redirect(url_for('saved_responses'))
    except Exception as e:
        flash(f"Error generating PDF: {str(e)}", "danger")
        print(f"Error generating PDF: {e}")
        return redirect(url_for('saved_responses'))

@app.route('/save_response', methods=['POST'])
@login_required
def save_response():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    if not title or not content:
        return jsonify({'message': 'Title and content are required.'}), 400

    try:
        new_response = SavedResponse(
            user_id=current_user.id,
            title=title,
            content=content
        )
        db.session.add(new_response)
        db.session.commit()
        return jsonify({'message': 'Response saved successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Failed to save response: {str(e)}'}), 500
    
#--- Main Entry Point ---#
if __name__ == '__main__':
    app.run(debug=True)