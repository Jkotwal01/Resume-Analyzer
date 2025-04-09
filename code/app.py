from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from resume_parser import ResumeAnalyzer
import os
import re
from pathlib import Path
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Create uploads folder if it doesn't exist
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)

# Initialize resume analyzer
analyzer = ResumeAnalyzer()

ALLOWED_EXTENSIONS = {'pdf', 'docx'}

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, email=None, name=None):
        self.id = user_id
        self.email = email
        self.name = name or f"User {user_id}"
        self.avatar_url = f"https://ui-avatars.com/api/?name={self.name.replace(' ', '+')}&background=random"

    @staticmethod
    def get_user_by_email(email):
        # This should be replaced with actual database query
        # For demo, we'll create a fake user
        if '@' in email:
            return User(email, email=email, name=email.split('@')[0].title())
        return None

    @staticmethod
    def create_user(name, email, password):
        # This should be replaced with actual database insert
        # For demo, we'll just return a new user
        if '@' in email:
            return User(email, email=email, name=name)
        return None

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compare_skills(resume_skills, job_desc):
    """Compare resume skills with job description requirements"""
    # Enhanced skill pattern to match more technologies
    skill_pattern = r"""
        (Python|JavaScript|TypeScript|React|Angular|Vue|Node\.js|
        Express|Flask|Django|FastAPI|Spring|Java|Kotlin|Swift|
        AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|
        SQL|MongoDB|PostgreSQL|MySQL|Redis|
        C\+\+|C#|Go|Rust|Ruby|PHP|
        Machine\sLearning|Data\sScience|AI|TensorFlow|PyTorch|
        HTML5?|CSS3?|SASS|LESS|Webpack|Babel|
        DevOps|CI/CD|Agile|Scrum)
    """
    job_skills = re.findall(skill_pattern, job_desc, re.I | re.X)
    job_skills = [skill.lower() for skill in set(job_skills)]
    resume_skills = [skill.lower() for skill in resume_skills]

    matched = [skill for skill in resume_skills if skill in job_skills]
    missing = [skill for skill in job_skills if skill not in resume_skills]
    return matched, missing

@app.route('/')
def index():
    """Landing page route"""
    return render_template('index.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('analyze'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember_me') == 'on'

        user = User.get_user_by_email(email)
        if user:
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.name}!', 'success')
            # Redirect to next page if it exists and is safe, otherwise go to analyze page
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('analyze'))
        
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup'))
            
        user = User.create_user(name, email, password)
        if user:
            login_user(user)
            flash('Account created successfully!', 'success')
            return redirect(url_for('index'))
        
        flash('Error creating account', 'error')
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/analyze')
@login_required
def analyze():
    """Resume upload and analysis page"""
    return render_template('upload.html', user=current_user)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/history')
@login_required
def history():
    return render_template('history.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload_page')
def upload_page():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_resume():
    """Handle resume upload and analysis"""
    if 'resume' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('upload_page'))

    file = request.files['resume']
    candidate_name = request.form.get('candidate_name', 'Candidate')
    candidate_role = request.form.get('candidate_role', 'Not Specified')
    job_desc = request.form.get('job_description', '')
    job_title = request.form.get('job_title', 'Software Engineer')

    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('upload_page'))

    try:
        filename = secure_filename(file.filename)
        filepath = app.config['UPLOAD_FOLDER'] / filename
        file.save(filepath)

        print(f"Processing file: {filename}")  # Debug log
        
        # Extract text from resume
        resume_text = analyzer.extract_text(str(filepath))
        print(f"Extracted text length: {len(resume_text)}")  # Debug log
        
        # Get resume data
        resume_data = analyzer._local_parser(str(filepath))
        
        # Get job fit analysis
        job_analysis = analyzer.analyze_job_fit(resume_text, job_title)

        # Format the job fit score properly
        job_fit_data = {
            'score': job_analysis['job_fit_score']['overall_score'],
            'technical_match': job_analysis['job_fit_score']['technical_match'],
            'experience_match': job_analysis['job_fit_score']['experience_match'],
            'education_match': job_analysis['job_fit_score']['education_match'],
            'breakdown': job_analysis['job_fit_score']['detailed_breakdown']
        }

        # Combine all data
        data = {
            'name': candidate_name,
            'current_role': candidate_role,
            'target_role': job_title,
            'education': resume_data.get('education', 'Not specified'),
            'experience': resume_data.get('experience', 'Not specified'),
            'tech_stack': resume_data.get('tech_stack', {}),
            'categories': resume_data.get('categories', {}),
            'ats_score': job_analysis.get('ats_score', {'score': 70}),
            'job_fit': job_fit_data,  # Use the formatted job fit data
            'technical_assessment': job_analysis.get('technical_assessment', {}),
            'improvement_areas': job_analysis.get('improvement_areas', []),
            'recommendations': job_analysis.get('recommendations', []),
            'strengths': job_analysis.get('strengths', []),
            'career_trajectory': job_analysis.get('career_trajectory', {}),
            'present_skills': job_analysis.get('technical_assessment', {}).get('present_skills', []),
            'missing_skills': job_analysis.get('technical_assessment', {}).get('missing_skills', []),
            'career_recommendations': job_analysis.get('career_trajectory', {}).get('development_path', []),
            'required_skills': job_analysis.get('technical_assessment', {}).get('required_skills', []),
            'top_matches': [
                {'name': skill, 'match': score} 
                for skill, score in job_analysis.get('technical_assessment', {}).get('skill_matches', {}).items()
            ][:5],
            'fit_analysis': job_analysis.get('detailed_analysis', 'No detailed analysis available.')
        }
        
        return render_template('analysis.html', data=data)

    except Exception as e:
        print(f"Processing error: {str(e)}")  # Debug log
        flash(f'Error processing resume: {str(e)}', 'error')
        return redirect(url_for('upload_page'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.')
    return redirect(url_for('upload_page'))

@app.errorhandler(500)
def server_error(e):
    flash('Server error occurred. Please try again.')
    return redirect(url_for('upload_page'))

@login_manager.unauthorized_handler
def unauthorized():
    """Handle unauthorized access attempts"""
    flash('Please log in to analyze your resume', 'info')
    return redirect(url_for('login', next=request.path))

if __name__ == '__main__':
    app.run(debug=True)
