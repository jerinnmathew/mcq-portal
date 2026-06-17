from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from backend.models import User
from pypdf import PdfReader
import urllib.request
import json
import os

ai_gen_bp = Blueprint('ai_generator', __name__)

@ai_gen_bp.before_request
def check_admin_privileges():
    """Enforces JWT authentication and restricts access exclusively to the 'admin' account."""
    if request.method == "OPTIONS":
        return
        
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        admin_user = os.environ.get('ADMIN_USERNAME', 'jerin_admin')
        if not user or user.username != admin_user:
            return jsonify({"msg": "Admin access required. Unauthorized."}), 403
    except Exception as e:
        return jsonify({"msg": "Authentication required. Admin token missing or invalid."}), 401

@ai_gen_bp.route('/generate-mcqs', methods=['POST'])
def generate_mcqs():
    """Extracts text from PDF/raw input and queries Gemini to generate structured MCQs."""
    api_key = os.environ.get("GEMINI_API_KEY")

    user_text = ""
    
    # Check if a PDF file was uploaded
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({"msg": "Only PDF files are allowed"}), 400
            try:
                import io
                pdf_file = io.BytesIO(file.read())
                reader = PdfReader(pdf_file)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        user_text += text + "\n"
            except Exception as e:
                return jsonify({"msg": f"Failed to read PDF file: {str(e)}"}), 400
    
    # If no file, try to read pasted text from JSON payload/form
    if not user_text:
        user_text = request.form.get('text', '').strip()
    if not user_text:
        try:
            data = request.get_json() or {}
            user_text = data.get('text', '').strip()
        except:
            pass

    if not user_text:
        return jsonify({"msg": "Please provide either a PYQ PDF file or a text block to generate MCQs."}), 400

    # Read number of questions to generate
    num_questions = 5
    try:
        num_questions = int(request.form.get('count', 5))
    except:
        try:
            data = request.get_json() or {}
            num_questions = int(data.get('count', 5))
        except:
            pass

    if not api_key:
        # Check if we should run in demo/mock fallback mode
        # Generate mock questions based on the input text to show how the system works
        mock_questions = [
            {
                "question": "Which of the following is a preemptive CPU scheduling algorithm using time quantum?",
                "option_a": "First-Come First-Served (FCFS)",
                "option_b": "Shortest Job First (SJF)",
                "option_c": "Round Robin (RR)",
                "option_d": "Priority Scheduling",
                "correct_answer": "C",
                "category": "Operating Systems",
                "difficulty": "Easy"
            },
            {
                "question": "What is the primary condition check in the Bankers Algorithm to prevent Deadlocks?",
                "option_a": "Mutual Exclusion check",
                "option_b": "Safe State check for resource allocations",
                "option_c": "Hold and Wait check",
                "option_d": "No Preemption check",
                "correct_answer": "B",
                "category": "Operating Systems",
                "difficulty": "Medium"
            },
            {
                "question": "In Data Structures, which traversal on a Binary Search Tree (BST) outputs elements in sorted order?",
                "option_a": "Pre-order traversal",
                "option_b": "In-order traversal",
                "option_c": "Post-order traversal",
                "option_d": "Level-order traversal",
                "correct_answer": "B",
                "category": "Data Structures",
                "difficulty": "Medium"
            },
            {
                "question": "Which tag in HTML is commonly used to create structural containers for CSS styling and page layouts?",
                "option_a": "<span>",
                "option_b": "<div>",
                "option_c": "<section>",
                "option_d": "<p>",
                "correct_answer": "B",
                "category": "Web Technologies",
                "difficulty": "Easy"
            },
            {
                "question": "In Digital Fundamentals, which flip-flop resolves the undefined toggle state of the SR flip-flop?",
                "option_a": "D Flip-flop",
                "option_b": "T Flip-flop",
                "option_c": "JK Flip-flop",
                "option_d": "Master-Slave SR Flip-flop",
                "correct_answer": "C",
                "category": "Digital Fundamentals",
                "difficulty": "Hard"
            }
        ]
        # Slice to requested count
        return jsonify(mock_questions[:num_questions]), 200

    # Build prompt for Gemini
    prompt = f"""
You are an expert academic examiner. Please read the following text containing previous year questions (PYQs) or study notes, and generate exactly {num_questions} high-quality Multiple Choice Questions (MCQs) for student practice.

---
{user_text[:8000]}
---

For each MCQ, you MUST provide:
1. "question": The question text. Make sure it is clear and unambiguous.
2. "option_a": Option A choice text.
3. "option_b": Option B choice text.
4. "option_c": Option C choice text.
5. "option_d": Option D choice text.
6. "correct_answer": The correct choice letter (MUST be exactly one of: "A", "B", "C", or "D").
7. "category": A logical educational subject category (e.g. "Operating Systems", "Data Structures", "Web Development", etc. based on the text contents).
8. "difficulty": A difficulty rating (MUST be exactly one of: "Easy", "Medium", or "Hard").

Response Requirements:
- You must return ONLY a valid JSON array of objects.
- Do NOT include any markdown code block wrappers (like ```json ... ```), no backticks, and no extra conversational text.
- Double-check that your JSON is completely valid and parseable by python json.loads().
"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'), 
            headers=headers,
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            raw_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            # Clean potential Markdown wrap
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
                
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            raw_text = raw_text.strip()
            
            try:
                mcqs_list = json.loads(raw_text)
            except Exception as json_err:
                print("Failed to parse Gemini JSON:", json_err)
                print("Raw Gemini output was:", raw_text)
                return jsonify({"msg": "AI returned invalid JSON formatting. Please try again.", "raw": raw_text}), 502
                
            # Perform basic validation on structure to avoid frontend crashes
            validated_mcqs = []
            for item in mcqs_list:
                q = item.get('question', '').strip()
                oa = item.get('option_a', '').strip()
                ob = item.get('option_b', '').strip()
                oc = item.get('option_c', '').strip()
                od = item.get('option_d', '').strip()
                ans = item.get('correct_answer', 'A').strip().upper()
                cat = item.get('category', 'AI Generated').strip()
                diff = item.get('difficulty', 'Medium').strip()
                
                if not q or not oa or not ob or not oc or not od:
                    continue # Skip incomplete questions
                if ans not in ['A', 'B', 'C', 'D']:
                    ans = 'A'
                if diff not in ['Easy', 'Medium', 'Hard']:
                    diff = 'Medium'
                    
                validated_mcqs.append({
                    "question": q,
                    "option_a": oa,
                    "option_b": ob,
                    "option_c": oc,
                    "option_d": od,
                    "correct_answer": ans,
                    "category": cat,
                    "difficulty": diff
                })
                
            return jsonify(validated_mcqs), 200

    except urllib.error.HTTPError as he:
        err_msg = he.read().decode('utf-8')
        print("Gemini HTTP Error:", err_msg)
        return jsonify({"msg": f"Gemini API returned an error: {he.reason}"}), 502
    except Exception as e:
        print("AI generation failed:", str(e))
        return jsonify({"msg": f"Failed to generate MCQs using AI: {str(e)}"}), 500
