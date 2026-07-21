import csv
import io
import json
import os

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from backend.models import db, MCQ, User, Attempt, Stats, Subject

admin_bp = Blueprint('admin', __name__)


def resolve_subject(category=None, subject_id=None):
    """Resolve a Subject by subject_id or exact name match."""
    if subject_id is not None and str(subject_id).strip() != '':
        try:
            subject = Subject.query.get(int(subject_id))
            if subject:
                return subject
        except (ValueError, TypeError):
            pass

    if category:
        return Subject.query.filter_by(name=category.strip()).first()

    return None


@admin_bp.before_request
def check_admin_privileges():
    """Enforces JWT authentication and restricts access exclusively to the 'admin' account."""
    # Skip CORS preflight OPTIONS requests automatically
    if request.method == "OPTIONS":
        return
        
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(int(user_id))
        import os
        admin_user = os.environ.get('ADMIN_USERNAME')
        if not admin_user:
            return jsonify({"msg": "Admin not configured. Set ADMIN_USERNAME/ADMIN_PASSWORD env vars."}), 500
        if not user or user.username != admin_user:
            return jsonify({"msg": "Admin access required. Unauthorized."}), 403
    except Exception as e:
        return jsonify({"msg": "Authentication required. Admin token missing or invalid."}), 401

@admin_bp.route('/mcqs', methods=['GET'])
def get_all_questions():
    """Lists all questions in the bank, including the correct answers. Supports optional subject_id filter."""
    subject_id = request.args.get('subject_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 200, type=int)
    per_page = min(per_page, 1000)  # cap at 1000

    query = MCQ.query
    if subject_id:
        query = query.filter_by(subject_id=subject_id)

    total = query.count()
    questions = query.order_by(MCQ.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "questions": [q.to_dict(include_correct=True) for q in questions],
        "total": total,
        "page": page,
        "per_page": per_page
    }), 200


@admin_bp.route('/mcqs', methods=['POST'])
def create_question():
    """Creates a new MCQ in the question database."""
    data = request.get_json() or {}
    
    question = data.get('question', '').strip()
    option_a = data.get('option_a', '').strip()
    option_b = data.get('option_b', '').strip()
    option_c = data.get('option_c', '').strip()
    option_d = data.get('option_d', '').strip()
    correct_answer = data.get('correct_answer', '').strip().upper()
    category = data.get('category', 'General').strip()
    subject_id = data.get('subject_id')

    if not all([question, option_a, option_b, option_c, option_d, correct_answer]):
        return jsonify({"msg": "All fields except category and subject are required"}), 400

    subject = None
    if subject_id is not None and str(subject_id).strip() != '':
        try:
            subject = Subject.query.get(int(subject_id))
        except (ValueError, TypeError):
            subject = None
        if not subject:
            return jsonify({"msg": "Subject not found for provided subject_id"}), 400

    if subject:
        category = subject.name

    if correct_answer not in ['A', 'B', 'C', 'D']:
        return jsonify({"msg": "Correct answer must be 'A', 'B', 'C', or 'D'"}), 400

    try:
        new_q = MCQ(
            question=question,
            option_a=option_a,
            option_b=option_b,
            option_c=option_c,
            option_d=option_d,
            correct_answer=correct_answer,
            category=category,
            subject_id=subject.id if subject else None
        )
        db.session.add(new_q)
        db.session.commit()
        return jsonify({"msg": "MCQ added successfully", "mcq": new_q.to_dict(include_correct=True)}), 210
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add question: {str(e)}")
        return jsonify({"msg": "Failed to add question"}), 500


@admin_bp.route('/mcqs/<int:qid>', methods=['PUT'])
def edit_question(qid):
    """Updates an existing MCQ details."""
    mcq = MCQ.query.get(qid)
    if not mcq:
        return jsonify({"msg": "MCQ not found"}), 404

    data = request.get_json() or {}
    
    mcq.question = data.get('question', mcq.question).strip()
    mcq.option_a = data.get('option_a', mcq.option_a).strip()
    mcq.option_b = data.get('option_b', mcq.option_b).strip()
    mcq.option_c = data.get('option_c', mcq.option_c).strip()
    mcq.option_d = data.get('option_d', mcq.option_d).strip()
    
    correct = data.get('correct_answer', mcq.correct_answer).strip().upper()
    if correct in ['A', 'B', 'C', 'D']:
        mcq.correct_answer = correct

    subject_id = data.get('subject_id')
    if subject_id is not None and str(subject_id).strip() != '':
        try:
            subject = Subject.query.get(int(subject_id))
            if subject:
                mcq.subject_id = subject.id
                mcq.category = subject.name
        except (ValueError, TypeError):
            pass
    mcq.category = data.get('category', mcq.category).strip()

    try:
        db.session.commit()
        return jsonify({"msg": "MCQ updated successfully", "mcq": mcq.to_dict(include_correct=True)}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update MCQ: {str(e)}")
        return jsonify({"msg": "Failed to update MCQ"}), 500


@admin_bp.route('/mcqs/<int:qid>', methods=['DELETE'])
def delete_question(qid):
    """Deletes an MCQ from the database."""
    mcq = MCQ.query.get(qid)
    if not mcq:
        return jsonify({"msg": "MCQ not found"}), 404

    try:
        db.session.delete(mcq)
        db.session.commit()
        return jsonify({"msg": "MCQ deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete MCQ: {str(e)}")
        return jsonify({"msg": "Failed to delete MCQ"}), 500


@admin_bp.route('/mcqs/clear', methods=['POST'])
def clear_questions():
    """Deletes every question from the MCQ bank."""
    try:
        deleted_count = MCQ.query.delete()
        db.session.commit()
        return jsonify({"msg": f"Cleared {deleted_count} questions from the database."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to clear MCQ bank: {str(e)}")
        return jsonify({"msg": "Failed to clear MCQ bank"}), 500


@admin_bp.route('/import', methods=['POST'])
def import_questions():
    """Bulk imports questions from a JSON/CSV payload or uploaded file into the database."""
    payload = None
    request_subject_id = request.form.get('subject_id', '').strip()
    request_category = request.form.get('category', '').strip()
    form_subject_id = request_subject_id
    form_category = request_category
    wrapper_subject_id = None
    wrapper_category = ''

    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            filename = (file.filename or '').lower()
            content = file.read().decode('utf-8', errors='ignore')
            if filename.endswith('.json'):
                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    return jsonify({"msg": f"Invalid JSON file: {exc.msg}"}), 400
            elif filename.endswith('.csv'):
                rows = list(csv.DictReader(io.StringIO(content)))
                payload = rows
            else:
                return jsonify({"msg": "Only .json or .csv files are supported for bulk import"}), 400
        else:
            return jsonify({"msg": "No file selected"}), 400
    else:
        try:
            payload = request.get_json(silent=True)
        except Exception:
            payload = None

    if payload is None:
        payload = []

    if isinstance(payload, dict):
        wrapper_subject_id = payload.get('subject_id') or payload.get('subjectId')
        wrapper_category = str(payload.get('category') or payload.get('topic') or '').strip()

        items = payload.get('questions') or payload.get('data') or payload.get('items') or []
        if not isinstance(items, list):
            return jsonify({"msg": "Request payload must be a JSON array of questions or an object with a 'questions' array"}), 400
        payload = items
        if not form_subject_id and wrapper_subject_id is not None:
            form_subject_id = str(wrapper_subject_id)
        if not form_category and wrapper_category:
            form_category = wrapper_category

    if not isinstance(payload, list):
        return jsonify({"msg": "Request payload must be a JSON array of questions"}), 400

    imported_count = 0
    errors = []

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append(f"Row {idx+1}: Invalid row format.")
            continue

        # ---- Normalize question ----
        question = str(item.get('question', '') or item.get('prompt', '') or '').strip()

        # ---- Normalize options from multiple possible shapes ----
        def _pick_option(letter: str) -> str:
            """
            letter: 'A' | 'B' | 'C' | 'D'
            Supports:
              - option_a/optionA
              - options: {A,B,C,D} or {a,b,c,d}
              - options: [A, B, C, D] (list)
              - A/B/C/D keys directly
            """
            letter_u = letter.upper()
            letter_l = letter_u.lower()

            # common option keys
            direct = (
                item.get(f'option_{letter_l}') or
                item.get(f'option{letter_u}') or
                item.get(f'option{letter_l}') or
                item.get(letter_u) or
                item.get(letter_l)
            )

            if direct is not None and str(direct).strip() != '':
                return str(direct).strip()

            # nested options object or array
            opts = item.get('options')
            if isinstance(opts, dict):
                v = (
                    opts.get(letter_u) or
                    opts.get(letter_l)
                )
                if v is not None and str(v).strip() != '':
                    return str(v).strip()

            if isinstance(opts, list):
                idx = ord(letter_u) - ord('A')
                if 0 <= idx < len(opts):
                    v = opts[idx]
                    if v is not None and str(v).strip() != '':
                        return str(v).strip()

            return ''

        option_a = _pick_option('A')
        option_b = _pick_option('B')
        option_c = _pick_option('C')
        option_d = _pick_option('D')

        # ---- Normalize correct answer ----
        correct_answer_raw = (
            item.get('correct_answer') or
            item.get('correctAnswer') or
            item.get('correct_option') or
            item.get('correctOption') or
            item.get('answer') or
            item.get('correct') or
            item.get('Correct') or
            ''
        )
        
        correct_answer = str(correct_answer_raw or '').strip()
        if correct_answer.upper() in ['A', 'B', 'C', 'D']:
            correct_answer = correct_answer.upper()
        else:
            # Check if correct_answer matches any option values (case-insensitive)
            raw_s = correct_answer.lower()
            if raw_s:
                if option_a and raw_s == option_a.lower():
                    correct_answer = 'A'
                elif option_b and raw_s == option_b.lower():
                    correct_answer = 'B'
                elif option_c and raw_s == option_c.lower():
                    correct_answer = 'C'
                elif option_d and raw_s == option_d.lower():
                    correct_answer = 'D'
                else:
                    # Check if correct_answer is 0-indexed numeric index
                    try:
                        idx_val = int(correct_answer)
                        if 0 <= idx_val <= 3:
                            correct_answer = ['A', 'B', 'C', 'D'][idx_val]
                    except ValueError:
                        pass

        # ---- Defaults for category/subject ----
        category = str(item.get('category', '') or item.get('topic', '') or form_category or 'General').strip()

        subject_id = item.get('subject_id') or item.get('subjectId') or form_subject_id or None
        subject_name = str(item.get('subject') or item.get('subject_name') or item.get('subjectName') or '').strip() or None

        # Basic validation
        if not all([question, option_a, option_b, option_c, option_d, correct_answer]):
            errors.append(f"Row {idx+1}: Missing required fields.")
            continue

        if correct_answer not in ['A', 'B', 'C', 'D']:
            errors.append(f"Row {idx+1}: Invalid correct answer '{correct_answer}'. Must be A, B, C, or D.")
            continue

        resolved_subject_id = None
        subject = None
        if subject_id is not None and str(subject_id).strip() != '':
            try:
                resolved_subject_id = int(subject_id)
                subject = Subject.query.get(resolved_subject_id)
            except (ValueError, TypeError):
                subject = None
            if not subject:
                errors.append(f"Row {idx+1}: Subject with ID {subject_id} not found.")
                continue
        else:
            if subject_name:
                subject = resolve_subject(subject_name)
            elif category:
                subject = Subject.query.filter_by(name=category).first()
            if subject:
                resolved_subject_id = subject.id

        if subject and not str(item.get('category', '') or item.get('topic', '') or form_category or '').strip():
            category = subject.name
        elif subject and str(item.get('category', '') or item.get('topic', '') or form_category or '').strip():
            category = str(item.get('category', '') or item.get('topic', '') or form_category or '').strip()

        existing_question = MCQ.query.filter_by(question=question).first()
        if existing_question:
            errors.append(f"Row {idx+1}: Question already exists in the database and was skipped.")
            continue

        try:
            new_q = MCQ(
                question=question,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_answer=correct_answer,
                category=category,
                subject_id=resolved_subject_id
            )
            db.session.add(new_q)
            imported_count += 1
        except Exception as e:
            current_app.logger.error(f"Database error during question import at row {idx+1}: {str(e)}")
            errors.append(f"Row {idx+1}: Database error occurred.")

    if imported_count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to save imported questions: {str(e)}")
            return jsonify({"msg": "Failed to save imported questions"}), 500

    return jsonify({
        "msg": f"Successfully imported {imported_count} questions.",
        "errors": errors
    }), 200


@admin_bp.route('/users', methods=['GET'])
def get_users_list():
    """Returns a list of all registered users (excluding the admin) and their stats."""
    import os
    admin_user = os.environ.get('ADMIN_USERNAME')
    if not admin_user:
        return jsonify({"msg": "Admin not configured. Set ADMIN_USERNAME env var."}), 500

    users = User.query.filter(User.username != admin_user).order_by(User.id.asc()).all()
    user_list = []
    
    for u in users:
        stats_dict = u.stats.to_dict() if u.stats else {}
        user_list.append({
            "id": u.id,
            "username": u.username,
            "streak": u.streak,
            "xp_points": u.xp_points,
            "badge": u.badge,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "stats": stats_dict
        })
        
    return jsonify(user_list), 200


@admin_bp.route('/attempts', methods=['GET'])
def get_recent_attempts():
    """Lists global recent attempts (excluding the admin) with associated student username."""
    import os
    admin_user = os.environ.get('ADMIN_USERNAME')
    if not admin_user:
        return jsonify({"msg": "Admin not configured. Set ADMIN_USERNAME env var."}), 500

    attempts = (
        db.session.query(Attempt, User.username)
        .join(User, Attempt.user_id == User.id)
        .filter(User.username != admin_user)
        .order_by(Attempt.submitted_at.desc())
        .limit(100)
        .all()
    )

                         
    attempt_list = []
    for att, username in attempts:
        att_dict = att.to_dict()
        att_dict["username"] = username
        attempt_list.append(att_dict)
        
    return jsonify(attempt_list), 200


@admin_bp.route('/import-pdf', methods=['POST'])
def import_pdf_questions():
    """Extracts questions from an uploaded PDF and parses them into the database using a layout-free parser."""
    if 'file' not in request.files:
        return jsonify({"msg": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"msg": "No file selected"}), 400
        
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"msg": "Only PDF files are allowed"}), 400

    try:
        from pypdf import PdfReader
        import io
        import re

        # Read PDF text in memory
        pdf_file = io.BytesIO(file.read())
        reader = PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        lines = full_text.split('\n')
        
        parsed_questions = []
        skipped_count = 0

        current_question = None
        current_opt_a = None
        current_opt_b = None
        current_opt_c = None
        current_opt_d = None
        current_correct = None
        current_category = None
        
        last_field = None # 'question', 'a', 'b', 'c', 'd'

        def save_current_mcq():
            nonlocal current_question, current_opt_a, current_opt_b, current_opt_c, current_opt_d
            nonlocal current_correct, current_category, parsed_questions, skipped_count
            
            if current_question:
                q_prompt = current_question.strip()
                if q_prompt:
                    # Provide smart, layout-free defaults for missing choices and answers
                    opt_a = (current_opt_a or "Option A").strip()
                    opt_b = (current_opt_b or "Option B").strip()
                    opt_c = (current_opt_c or "Option C").strip()
                    opt_d = (current_opt_d or "Option D").strip()
                    correct = (current_correct or "A").strip().upper()
                    
                    parsed_questions.append({
                        "question": q_prompt,
                        "option_a": opt_a,
                        "option_b": opt_b,
                        "option_c": opt_c,
                        "option_d": opt_d,
                        "correct_answer": correct,
                        "category": (current_category or "Imported PDF").strip()
                    })
                else:
                    skipped_count += 1
                
                # Reset state
                current_question = None
                current_opt_a = None
                current_opt_b = None
                current_opt_c = None
                current_opt_d = None
                current_correct = None
                current_category = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 1. Match Options (e.g., A), A., (A), [A], a), a.)
            opt_a_match = re.match(r'^\s*\(?[aA][\.\)\s\]-]\s*(.+)$', line)
            opt_b_match = re.match(r'^\s*\(?[bB][\.\)\s\]-]\s*(.+)$', line)
            opt_c_match = re.match(r'^\s*\(?[cC][\.\)\s\]-]\s*(.+)$', line)
            opt_d_match = re.match(r'^\s*\(?[dD][\.\)\s\]-]\s*(.+)$', line)

            # 2. Match Question starts (e.g., Question 1:, Q1., 1.)
            q_match = re.match(r'^(?:question|q)[:\.\s-]*\d*[:\.\s-]*\s*(.+)$', line, re.IGNORECASE)
            num_match = re.match(r'^\d+[\.\s\)-]+\s*(.+)$', line)

            # 3. Match Correct Answers (e.g., Answer: A, Correct - B, Ans: C)
            ans_match = re.match(r'^(?:answer|correct|correct answer|ans)[:\.\s-]*\s*([A-D])\b', line, re.IGNORECASE)
            
            # Heuristic Search for answer inside the line (e.g., "The answer is B")
            ans_search = None
            if not ans_match:
                ans_search_match = re.search(r'\b(?:answer|ans|correct)[:\s\.-]*([A-D])\b', line, re.IGNORECASE)
                if ans_search_match:
                    ans_search = ans_search_match.group(1)

            # 4. Metadata tags (Category:)
            cat_match = re.match(r'^category[:\.-]\s*(.+)$', line, re.IGNORECASE)

            # Evaluator
            if q_match:
                save_current_mcq()
                current_question = q_match.group(1)
                last_field = 'question'
            elif num_match and not any([opt_a_match, opt_b_match, opt_c_match, opt_d_match, ans_match, cat_match]):
                save_current_mcq()
                current_question = num_match.group(1)
                last_field = 'question'
            elif line.endswith('?') and not any([opt_a_match, opt_b_match, opt_c_match, opt_d_match, ans_match, cat_match]):
                # If a line ends in a question mark, treat as a new question start if we already have choices active
                if current_question and (current_opt_a or current_opt_b or current_opt_c or current_opt_d):
                    save_current_mcq()
                
                if not current_question:
                    current_question = line
                else:
                    current_question += " " + line
                last_field = 'question'
            elif opt_a_match:
                current_opt_a = opt_a_match.group(1)
                last_field = 'a'
            elif opt_b_match:
                current_opt_b = opt_b_match.group(1)
                last_field = 'b'
            elif opt_c_match:
                current_opt_c = opt_c_match.group(1)
                last_field = 'c'
            elif opt_d_match:
                current_opt_d = opt_d_match.group(1)
                last_field = 'd'
            elif ans_match:
                current_correct = ans_match.group(1)
                last_field = None
            elif ans_search:
                current_correct = ans_search
                last_field = None
            elif cat_match:
                current_category = cat_match.group(1)
                last_field = None
            else:
                # Text continuation/multi-line wrapping
                if last_field == 'question' and current_question:
                    current_question += " " + line
                elif last_field == 'a' and current_opt_a:
                    current_opt_a += " " + line
                elif last_field == 'b' and current_opt_b:
                    current_opt_b += " " + line
                elif last_field == 'c' and current_opt_c:
                    current_opt_c += " " + line
                elif last_field == 'd' and current_opt_d:
                    current_opt_d += " " + line

        # Save trailing final question block
        save_current_mcq()

        if len(parsed_questions) == 0:
            return jsonify({"msg": "Could not parse any valid questions. Ensure the PDF contains readable text.", "skipped": skipped_count}), 400

        # Bulk write to database
        imported_count = 0
        for q in parsed_questions:
            new_q = MCQ(
                question=q["question"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_answer=q["correct_answer"],
                category=q["category"]
            )
            db.session.add(new_q)
            imported_count += 1
            
        db.session.commit()
        return jsonify({
            "msg": f"Successfully parsed and imported {imported_count} questions from PDF.",
            "skipped": skipped_count
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to process PDF: {str(e)}")
        return jsonify({"msg": "Failed to process PDF"}), 500


@admin_bp.route('/mcqs/by-subject/<int:subject_id>', methods=['DELETE'])
def delete_mcqs_by_subject(subject_id):
    """Deletes ALL questions linked to a specific subject."""
    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"msg": "Subject not found"}), 404

    count = MCQ.query.filter_by(subject_id=subject_id).count()
    if count == 0:
        return jsonify({"msg": f"No questions found for subject '{subject.name}'."}), 200

    try:
        MCQ.query.filter_by(subject_id=subject_id).delete(synchronize_session='fetch')
        db.session.commit()
        return jsonify({
            "msg": f"Successfully deleted all {count} questions for subject '{subject.name}'.",
            "deleted_count": count,
            "subject": subject.name
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete questions by subject: {str(e)}")
        return jsonify({"msg": "Failed to delete questions"}), 500


@admin_bp.route('/import/batch', methods=['POST'])
def import_questions_batch():
    """Imports a batch of questions with progress tracking. Accepts chunked arrays."""
    data = request.get_json() or {}
    questions = data.get('questions', [])
    subject_id = data.get('subject_id')
    batch_index = data.get('batch_index', 0)
    total_batches = data.get('total_batches', 1)

    if not isinstance(questions, list) or len(questions) == 0:
        return jsonify({"msg": "Batch must contain a non-empty 'questions' array"}), 400

    imported_count = 0
    errors = []

    for idx, item in enumerate(questions):
        if not isinstance(item, dict):
            errors.append(f"Row {idx+1}: Invalid row format.")
            continue

        question = str(item.get('question', '') or item.get('prompt', '') or '').strip()

        def pick_option(item, letter):
            letter_u = letter.upper()
            letter_l = letter_u.lower()
            direct = (
                item.get(f'option_{letter_l}') or
                item.get(f'option{letter_u}') or
                item.get(letter_u) or
                item.get(letter_l)
            )
            if direct is not None and str(direct).strip() != '':
                return str(direct).strip()
            opts = item.get('options')
            if isinstance(opts, dict):
                v = opts.get(letter_u) or opts.get(letter_l)
                if v is not None and str(v).strip() != '':
                    return str(v).strip()
            if isinstance(opts, list):
                idx_opt = ord(letter_u) - ord('A')
                if 0 <= idx_opt < len(opts):
                    v = opts[idx_opt]
                    if v is not None and str(v).strip() != '':
                        return str(v).strip()
            return ''

        option_a = pick_option(item, 'A')
        option_b = pick_option(item, 'B')
        option_c = pick_option(item, 'C')
        option_d = pick_option(item, 'D')

        correct_raw = (
            item.get('correct_answer') or item.get('correctAnswer') or
            item.get('correct_option') or item.get('correctOption') or
            item.get('answer') or ''
        )
        correct = str(correct_raw or '').strip().upper() if correct_raw else ''
        if correct not in ['A', 'B', 'C', 'D']:
            correct = ''
            raw_lower = str(correct_raw or '').lower()
            if raw_lower:
                if raw_lower == option_a.lower(): correct = 'A'
                elif raw_lower == option_b.lower(): correct = 'B'
                elif raw_lower == option_c.lower(): correct = 'C'
                elif raw_lower == option_d.lower(): correct = 'D'

        category = str(item.get('category', '') or item.get('topic', '') or data.get('category', 'General')).strip()

        resolved_subject_id = subject_id
        if not resolved_subject_id:
            sid = item.get('subject_id') or item.get('subjectId')
            if sid is not None:
                try:
                    resolved_subject_id = int(sid)
                except (ValueError, TypeError):
                    pass

        if not all([question, option_a, option_b, option_c, option_d, correct]):
            errors.append(f"Row {idx+1}: Missing required fields.")
            continue

        try:
            new_q = MCQ(
                question=question,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c,
                option_d=option_d,
                correct_answer=correct,
                category=category,
                subject_id=resolved_subject_id
            )
            db.session.add(new_q)
            imported_count += 1
        except Exception as e:
            current_app.logger.error(f"Batch import error at row {idx+1}: {str(e)}")
            errors.append(f"Row {idx+1}: Database error.")

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to save batch: {str(e)}")
        return jsonify({"msg": "Failed to save batch", "errors": errors}), 500

    return jsonify({
        "imported": imported_count,
        "errors": errors,
        "batch_index": batch_index,
        "total_batches": total_batches,
        "completed": batch_index + 1 >= total_batches
    }), 200


# ─────────────────────────────────────────────────────────────
#  Subject Management Routes
# ─────────────────────────────────────────────────────────────

@admin_bp.route('/subjects', methods=['GET'])
def admin_list_subjects():
    """Returns all subjects grouped by semester for admin management."""
    subjects = Subject.query.order_by(Subject.semester.asc(), Subject.name.asc()).all()
    grouped = {}
    for s in subjects:
        sem = str(s.semester)
        if sem not in grouped:
            grouped[sem] = []
        question_count = len(s.questions)
        grouped[sem].append({
            "id": s.id,
            "name": s.name,
            "semester": s.semester,
            "question_count": question_count
        })
    return jsonify({"grouped": grouped, "total": len(subjects)}), 200


@admin_bp.route('/subjects', methods=['POST'])
def admin_create_subject():
    """Creates a new subject."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    semester = data.get('semester')

    if not name:
        return jsonify({"msg": "Subject name is required"}), 400
    try:
        semester = int(semester)
        if semester < 1 or semester > 8:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"msg": "Semester must be a number between 1 and 8"}), 400

    existing = Subject.query.filter_by(name=name).first()
    if existing:
        return jsonify({"msg": f"Subject '{name}' already exists in Sem {existing.semester}"}), 409

    try:
        new_subject = Subject(name=name, semester=semester)
        db.session.add(new_subject)
        db.session.commit()
        return jsonify({"msg": f"Subject '{name}' added to Semester {semester}.", "subject": new_subject.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create subject: {str(e)}")
        return jsonify({"msg": "Failed to create subject"}), 500


@admin_bp.route('/subjects/<int:sid>', methods=['DELETE'])
def admin_delete_subject(sid):
    """Deletes a subject and detaches any linked questions."""
    subject = Subject.query.get(sid)
    if not subject:
        return jsonify({"msg": "Subject not found"}), 404

    linked_questions = MCQ.query.filter_by(subject_id=sid).all()
    linked_count = len(linked_questions)

    try:
        for mcq in linked_questions:
            mcq.subject_id = None

        db.session.delete(subject)
        db.session.commit()

        if linked_count > 0:
            return jsonify({
                "msg": f"Subject '{subject.name}' deleted successfully. {linked_count} linked question(s) were detached."
            }), 200

        return jsonify({"msg": f"Subject '{subject.name}' deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete subject: {str(e)}")
        return jsonify({"msg": "Failed to delete subject"}), 500


@admin_bp.route('/subjects/<int:sid>', methods=['PUT'])
def admin_update_subject(sid):
    """Renames a subject or changes its semester."""
    subject = Subject.query.get(sid)
    if not subject:
        return jsonify({"msg": "Subject not found"}), 404

    data = request.get_json() or {}
    name = (data.get('name') or subject.name).strip()
    semester = data.get('semester', subject.semester)
    try:
        semester = int(semester)
        if semester < 1 or semester > 8:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"msg": "Semester must be a number between 1 and 8"}), 400

    # Check name conflict with another subject
    conflict = Subject.query.filter(Subject.name == name, Subject.id != sid).first()
    if conflict:
        return jsonify({"msg": f"Subject name '{name}' is already used by another subject."}), 409

    try:
        subject.name = name
        subject.semester = semester
        db.session.commit()
        return jsonify({"msg": f"Subject updated successfully.", "subject": subject.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update subject: {str(e)}")
        return jsonify({"msg": "Failed to update subject"}), 500
