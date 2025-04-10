from flask import Flask, render_template, request, redirect, url_for, flash
from resume_parser import analyze_resume_with_gemini
import os
from werkzeug.utils import secure_filename
import json
import re

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_job_requirements(text):
    """Extract key requirements from job description"""
    skills = re.findall(r"(?i)\b(python|javascript|java|c\+\+|c#|go|ruby|php|swift|kotlin|typescript|react|angular|vue|node\.?js|express|django|flask|spring|laravel|rails|\.net|sql|nosql|mysql|postgresql|mongodb|aws|azure|gcp|docker|kubernetes|terraform|ansible|jenkins|git|machine learning|deep learning|data science|ai|artificial intelligence|nlp|computer vision|big data|hadoop|spark|tableau|power bi|excel)\b", text)
    return list(set(skill.lower() for skill in skills))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'resume' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['resume']
        job_desc = request.form.get('job_description', '')
        
        # If user does not select file, browser submits empty file
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Analyze resume with Gemini API
                analysis_result = analyze_resume_with_gemini(filepath, job_desc)
                
                # Process the results
                if isinstance(analysis_result, dict):
                    # Extract skills from job description for comparison
                    job_skills = extract_job_requirements(job_desc) if job_desc else []
                    resume_skills = [skill['name'].lower() for skill in analysis_result.get('skills', [])]
                    
                    # Calculate matching skills
                    matched_skills = [skill for skill in resume_skills if skill in job_skills]
                    missing_skills = [skill for skill in job_skills if skill not in resume_skills]
                    
                    # Add comparison results to analysis
                    analysis_result['skill_comparison'] = {
                        'matched': matched_skills,
                        'missing': missing_skills,
                        'match_percentage': len(matched_skills) / len(job_skills) * 100 if job_skills else 0
                    }
                    
                    return render_template('analysis.html', data=analysis_result)
                else:
                    flash('Error analyzing resume. Please try again.')
                    return redirect(url_for('upload_file'))
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}')
                return redirect(url_for('upload_file'))
            
        else:
            flash('Allowed file types are pdf, doc, docx, txt')
            return redirect(url_for('upload_file'))
    
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)