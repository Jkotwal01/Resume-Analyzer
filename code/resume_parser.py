import os
from dotenv import load_dotenv
import google.generativeai as genai
import fitz  # PyMuPDF for PDF processing
from docx import Document  # For DOCX processing
import re
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('GMINI_API_KEY'))

# Set up the model
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
    safety_settings=safety_settings
)

def extract_text_from_file(file_path):
    """Extract text from different file formats"""
    if file_path.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.endswith(('.doc', '.docx')):
        return extract_text_from_docx(file_path)
    else:  # Assume plain text
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

def extract_text_from_pdf(file_path):
    """Extract text from PDF using PyMuPDF"""
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_docx(file_path):
    """Extract text from DOCX using python-docx"""
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def analyze_resume_with_gemini(file_path, job_description=None):
    """Analyze resume using Gemini API"""
    try:
        # Extract text from resume file
        resume_text = extract_text_from_file(file_path)
        
        # Prepare the prompt for Gemini
        prompt = f"""
        Analyze the following resume in detail and provide a comprehensive JSON response with the following structure:
        
        {{
            "name": "Full name of the candidate",
            "email": "Email address if found",
            "phone": "Phone number if found",
            "summary": "Professional summary/objective",
            "education": [
                {{
                    "degree": "Degree name",
                    "institution": "Institution name",
                    "year": "Graduation year",
                    "gpa": "GPA if mentioned"
                }}
            ],
            "experience": [
                {{
                    "title": "Job title",
                    "company": "Company name",
                    "duration": "Employment duration",
                    "description": "Job description",
                    "achievements": ["Key achievements"]
                }}
            ],
            "skills": [
                {{
                    "name": "Skill name",
                    "category": "Technical/Soft/Language etc.",
                    "proficiency": "Beginner/Intermediate/Expert"
                }}
            ],
            "projects": [
                {{
                    "name": "Project name",
                    "description": "Project description",
                    "technologies": ["Technologies used"],
                    "outcome": "Project outcome"
                }}
            ],
            "certifications": ["List of certifications"],
            "languages": ["List of languages"],
            "analysis": {{
                "strengths": ["List of strengths"],
                "weaknesses": ["List of weaknesses"],
                "ats_compatibility": "Score out of 10",
                "suggestions": ["Improvement suggestions"]
            }}
        }}
        
        Resume Text:
        {resume_text}
        """
        
        if job_description:
            prompt += f"""
            
            Additionally, compare this resume with the following job description and provide a compatibility score:
            
            Job Description:
            {job_description}
            
            Add these fields to the JSON response:
            {{
                "job_compatibility": {{
                    "score": "Compatibility score out of 10",
                    "matching_keywords": ["List of matching keywords"],
                    "missing_keywords": ["List of missing keywords"],
                    "recommendations": ["Specific recommendations to improve match"]
                }}
            }}
            """
        
        # Call Gemini API
        response = model.generate_content(prompt)
        
        # Parse the response
        try:
            # Extract JSON from markdown if present
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            
            analysis_result = json.loads(json_str)
            
            # Add timestamp and filename
            analysis_result['metadata'] = {
                'timestamp': datetime.now().isoformat(),
                'filename': os.path.basename(file_path)
            }
            
            return analysis_result
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print("Raw response:", response.text)
            return {"error": "Failed to parse analysis results"}
            
    except Exception as e:
        print(f"Error analyzing resume: {str(e)}")
        return {"error": str(e)}