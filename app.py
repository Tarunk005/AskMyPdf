import os
import uuid
import json
import pdfplumber
import docx
import requests
from flask import Flask, render_template, request, jsonify, redirect, url_for

# === Flask App Config ===
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load API key securely
# OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY ="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"
# === Helper Functions ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to extract text from a PDF
def extract_text_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text()
    return text

# Function to extract text from a DOCX file
def extract_text_from_docx(docx_file):
    doc = docx.Document(docx_file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + '\n'
    return text
# === Routes ===
@app.route('/')
def front():
    return render_template('front.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        print(f"Email: {email}, Password: {password}")  # Debugging log
        if not email or not password:
            return "Please fill in both fields.", 400
        # Perform authentication logic here
        return redirect(url_for('index'))  # Redirect to the index page
    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']
    if file and allowed_file(file.filename):
        # Generate unique filename to avoid conflicts
        filename = f"{uuid.uuid4()}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Extract text based on file type
        try:
            if file.filename.endswith('.pdf'):
                text = extract_text_from_pdf(filepath)
            elif file.filename.endswith('.docx'):
                text = extract_text_from_docx(filepath)
        except Exception as e:
            return jsonify({'error': 'Failed to extract text from the file.'})

        app.config['extracted_text'] = text
        return jsonify({'message': 'File uploaded and text extracted successfully!'})
    else:
        return jsonify({'error': 'Invalid file format. Please upload a PDF or DOCX.'})

@app.route('/ask', methods=['POST'])
def ask_question():
    question = request.form.get('question', '').strip()
    context = app.config.get('extracted_text', '')

    if not context:
        return jsonify({'error': 'No document content available. Please upload a file first.'})
    if not question:
        return jsonify({'error': 'No question provided.'})
    if not OPENROUTER_API_KEY:
        return jsonify({'error': 'API key not configured on server.'})

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            data=json.dumps({
                "model": "mistralai/mistral-small-3.1-24b-instruct:free",
                "messages": [
                    {
                        "role": "system",
                        "content": "Answer only the question directly. Do not include greetings, thanks, or polite filler. Just give the answer."
                    },
                    {
                        "role": "user",
                        "content": f"Context: {context}\n\nQuestion: {question}"
                    }
                ],
                "top_p": 1,
                "temperature": 0.7,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "repetition_penalty": 1,
                "top_k": 0,
            })
        )
        print("API response:", response.json())
        result = response.json()["choices"][0]["message"]["content"]
        return jsonify({'answer': result})
    except Exception as e:
        print("API error:", e)
        return jsonify({'error': 'Error while generating answer from AI model.'})

if __name__ == '__main__':
    app.run(debug=True)
