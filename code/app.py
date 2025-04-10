from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from resume_parser import ResumeAnalyzer
import os
import re
from pathlib import Path
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = 'your-secret-key-here'

app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
analyzer = ResumeAnalyzer()

ALLOWED_EXTENSIONS = {'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compare_skills(resume_skills, job_desc):
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

def analyze_job_fit(resume_data, job_title, job_desc=""):
    """Analyze job fit based on resume data and job requirements"""
    ats_score = analyzer.calculate_ats_score(resume_data)
    job_fit = analyzer.calculate_job_fit(resume_data, job_title, job_desc)
    
    return {
        'ats_score': {'score': ats_score},
        'job_fit_score': {
            'overall_score': job_fit['overall_score'],
            'technical_match': job_fit['technical_match'],
            'experience_match': job_fit['experience_match'],
            'education_match': job_fit['education_match'],
            'detailed_breakdown': {
                'technical_skills': job_fit['technical_match'],
                'experience': job_fit['experience_match'],
                'education': job_fit['education_match'],
                'role_relevance': job_fit.get('role_relevance', 75),
                'industry_fit': job_fit.get('industry_fit', 80)
            }
        },
        'technical_assessment': {
            'present_skills': job_fit['present_skills'],
            'missing_skills': job_fit['missing_skills'],
            'skill_matches': job_fit['skill_matches']
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze')
def analyze():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('analyze'))

    file = request.files['resume']
    candidate_name = request.form.get('candidate_name', 'Candidate')
    candidate_role = request.form.get('candidate_role', 'Not Specified')
    job_desc = request.form.get('job_description', '')
    job_title = request.form.get('job_title', 'Software Engineer')

    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('analyze'))

    try:
        filename = secure_filename(file.filename)
        filepath = app.config['UPLOAD_FOLDER'] / filename
        file.save(filepath)

        resume_text = analyzer.extract_text(str(filepath))
        resume_data = analyzer.extract_resume_data(str(filepath))
        job_analysis = analyze_job_fit(resume_data, job_title, job_desc)

        data = {
            'name': candidate_name,
            'current_role': candidate_role,
            'target_role': job_title,
            'education': resume_data.get('education', 'Not specified'),
            'experience': resume_data.get('experience', 'Not specified'),
            'tech_stack': resume_data.get('tech_stack', {}),
            'categories': resume_data.get('categories', {}),
            'ats_score': job_analysis['ats_score'],
            'job_fit': {
                'score': job_analysis['job_fit_score']['overall_score'],
                'breakdown': job_analysis['job_fit_score']['detailed_breakdown']
            },
            'top_matches': [
                {'name': skill, 'match': score} 
                for skill, score in job_analysis['technical_assessment']['skill_matches'].items()
            ][:5]
        }

        return render_template('analysis.html', data=data)

    except Exception as e:
        flash(f'Error processing resume: {str(e)}', 'error')
        return redirect(url_for('analyze'))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.')
    return redirect(url_for('analyze'))

@app.errorhandler(500)
def server_error(e):
    flash('Server error occurred. Please try again.')
    return redirect(url_for('analyze'))

if __name__ == '__main__':
    app.run(debug=True)