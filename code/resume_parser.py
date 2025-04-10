import requests
import fitz  # PyMuPDF
import re
import json
import PyPDF2
import os
from typing import Dict, List
from dotenv import load_dotenv
import docx

load_dotenv()
GMINI_API_KEY = os.getenv('GMINI_API_KEY')
GMINI_API_URL = os.getenv('GMINI_API_URL')

class ResumeAnalyzer:
    def __init__(self):
        self.categories = {
            'Frontend': ['HTML', 'CSS', 'JavaScript', 'React', 'Vue', 'Angular'],
            'Backend': ['Node.js', 'Express', 'Flask', 'Django', 'Spring', 'PHP'],
            'Data': ['Python', 'Pandas', 'NumPy', 'SQL', 'R', 'Excel'],
            'DevOps': ['Docker', 'Kubernetes', 'AWS', 'Azure', 'CI/CD'],
        }

    def extract_text(self, file_path: str) -> str:
        """Extract text from resume file (PDF or DOCX)"""
        text = ""
        if file_path.endswith('.pdf'):
            try:
                doc = fitz.open(file_path)
                for page in doc:
                    text += page.get_text()
            except Exception:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() or ""
        elif file_path.endswith('.docx'):
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        return text

    def extract_resume_data(self, file_path: str) -> Dict:
        """Extract and analyze resume data"""
        try:
            response = self._call_gmini_api(file_path)
            if response and response.get('status_code') == 200:
                return self._parse_gmini_response(response)
            return self._local_parser(file_path)
        except Exception as e:
            print(f"Error in resume analysis: {str(e)}")
            return self._local_parser(file_path)

    def _call_gmini_api(self, file_path: str) -> Dict:
        """Call GMINI API for resume parsing"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {'Authorization': f'Bearer {GMINI_API_KEY}'}
            response = requests.post(GMINI_API_URL, headers=headers, files=files)
            return {'status_code': response.status_code, 'data': response.json() if response.status_code == 200 else None}

    def _parse_gmini_response(self, response: Dict) -> Dict:
        """Parse GMINI API response"""
        result = response['data']
        return {
            "name": result.get("name", "Unknown"),
            "education": result.get("education", {}).get("degree", "Not found"),
            "experience": result.get("experience", {}).get("total_years", "Not found"),
            "tech_stack": self._extract_tech_stack(result.get("skills", [])),
            "categories": self._categorize_tech_stack(result.get("skills", [])),
            "role": result.get("role", "Not specified"),
            "summary": result.get("summary", ""),
            "projects": result.get("projects", [])
        }

    def _local_parser(self, file_path: str) -> Dict:
        """Local fallback parser"""
        text = self.extract_text(file_path)
        name = self._extract_name(text)
        education = re.findall(r"(?:B\.?Tech|M\.?Tech|Bachelor|Master|Ph\.?D\.?)(?:\sin\s)?(?:[A-Za-z\s]+)?", text)
        experience = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?years?(?:\sof\sexperience)?", text)
        skills = re.findall(r"(?i)(Python|Java|JavaScript|React|Flask|SQL|HTML|CSS|Docker|AWS|Azure|Node\.js)", text)
        tech_stack = {skill: self._estimate_skill_level(skill, text) for skill in set(skills)}
        return {
            "name": name,
            "education": education[0] if education else "Not found",
            "experience": f"{experience[0]} years" if experience else "Not found",
            "tech_stack": tech_stack,
            "categories": self._categorize_tech_stack([{'name': s} for s in tech_stack]),
            "role": self._extract_role(text),
            "summary": self._extract_summary(text),
            "projects": self._extract_projects(text)
        }

    def _extract_name(self, text: str) -> str:
        """Extract name from resume text"""
        name_patterns = [
            r"(?i)(?:name|resume)[:]\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})",
            r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})",
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})\s*(?:resume|cv)",
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0].strip()
        return "Candidate"

    def _estimate_skill_level(self, skill: str, text: str) -> int:
        """Estimate skill level based on context"""
        skill_lower = skill.lower()
        context = text.lower()
        mentions = context.count(skill_lower)
        expert_indicators = ['expert', 'advanced', 'senior', 'lead']
        intermediate_indicators = ['intermediate', 'proficient']
        if any(indicator in context[max(0, context.find(skill_lower)-50):context.find(skill_lower)+50] for indicator in expert_indicators):
            return 5
        elif any(indicator in context[max(0, context.find(skill_lower)-50):context.find(skill_lower)+50] for indicator in intermediate_indicators):
            return 4
        elif mentions > 3:
            return 4
        elif mentions > 1:
            return 3
        return 2

    def _categorize_tech_stack(self, skills: List[Dict]) -> Dict:
        """Categorize skills into tech categories"""
        counts = {cat: 0 for cat in self.categories}
        for skill in skills:
            for cat, items in self.categories.items():
                if skill['name'] in items:
                    counts[cat] += 1
        return counts

    def _extract_tech_stack(self, skills: List[Dict]) -> Dict:
        """Extract tech stack with proficiency levels"""
        return {skill['name']: skill.get('proficiency', 3) for skill in skills}

    def _extract_role(self, text: str) -> str:
        """Extract current/target role"""
        role_patterns = [
            r"(?i)(?:current role|position|job title)[:]\s*([^\n]+)",
            r"(?i)(?:senior|junior|lead)?\s*(?:software|data|frontend|backend|full stack|devops)\s*(?:engineer|developer|architect)",
        ]
        for pattern in role_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0].strip()
        return "Software Developer"

    def _extract_summary(self, text: str) -> str:
        """Extract professional summary"""
        summary_patterns = [
            r"(?i)(?:professional\s+summary|summary|profile)[:]\s*([^\n]+(?:\n[^\n]+){0,3})",
            r"(?i)(?:about\s+me)[:]\s*([^\n]+(?:\n[^\n]+){0,3})"
        ]
        for pattern in summary_patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0].strip()
        return ""

    def _extract_projects(self, text: str) -> List[Dict]:
        """Extract projects from resume text"""
        project_patterns = [
            r"(?i)(?:projects?|work experience)[:]\s*([^\n]+(?:\n[^\n]+){0,5})",
            r"(?i)(?:key projects?|notable projects?)[:]\s*([^\n]+(?:\n[^\n]+){0,5})"
        ]
        projects = []
        for pattern in project_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                projects.append({"description": match.strip()})
        return projects

    def calculate_ats_score(self, resume_data: Dict) -> int:
        """Calculate ATS compatibility score"""
        score = 70  # Base score
        
        # Check for key components
        if resume_data.get('name'): score += 5
        if resume_data.get('education'): score += 5
        if resume_data.get('experience'): score += 5
        if resume_data.get('tech_stack'): score += 5
        if resume_data.get('summary'): score += 5
        if resume_data.get('projects'): score += 5
        
        return min(score, 100)

    def calculate_job_fit(self, resume_data: Dict, job_title: str, job_desc: str = "") -> Dict:
        """Calculate job fit score and detailed analysis"""
        # Initialize scores
        technical_match = self._calculate_technical_match(resume_data.get('tech_stack', {}), job_title)
        experience_match = self._calculate_experience_match(resume_data.get('experience', ''), job_title)
        education_match = self._calculate_education_match(resume_data.get('education', ''), job_title)
        
        # Calculate overall score
        overall_score = int((technical_match * 0.5) + (experience_match * 0.3) + (education_match * 0.2))
        
        # Analyze skills
        required_skills = self._get_required_skills(job_title)
        present_skills = list(resume_data.get('tech_stack', {}).keys())
        missing_skills = [skill for skill in required_skills if skill not in present_skills]
        
        # Calculate skill matches
        skill_matches = {}
        for skill in present_skills:
            if skill in required_skills:
                skill_matches[skill] = min(resume_data['tech_stack'].get(skill, 3) * 20, 100)
        
        return {
            'overall_score': overall_score,
            'technical_match': technical_match,
            'experience_match': experience_match,
            'education_match': education_match,
            'present_skills': present_skills,
            'missing_skills': missing_skills,
            'skill_matches': skill_matches
        }

    def _calculate_technical_match(self, tech_stack: Dict, job_title: str) -> int:
        """Calculate technical skills match percentage"""
        required_skills = self._get_required_skills(job_title)
        if not required_skills:
            return 75  # Default score if no specific requirements
            
        matches = sum(1 for skill in tech_stack if skill in required_skills)
        return min(int((matches / len(required_skills)) * 100), 100)

    def _calculate_experience_match(self, experience: str, job_title: str) -> int:
        """Calculate experience match percentage"""
        try:
            years = float(re.findall(r"(\d+(?:\.\d+)?)", experience)[0])
            if 'senior' in job_title.lower():
                return min(int((years / 5) * 100), 100)
            elif 'mid' in job_title.lower():
                return min(int((years / 3) * 100), 100)
            else:
                return min(int((years / 2) * 100), 100)
        except:
            return 70  # Default score if experience cannot be parsed

    def _calculate_education_match(self, education: str, job_title: str) -> int:
        """Calculate education match percentage"""
        education = education.lower()
        if 'phd' in education:
            return 100
        elif 'master' in education:
            return 90
        elif 'bachelor' in education or 'b.tech' in education or 'b.e.' in education:
            return 80
        return 70  # Default score for other education levels

    def _get_required_skills(self, job_title: str) -> List[str]:
        """Get required skills based on job title"""
        title = job_title.lower()
        if 'frontend' in title:
            return ['JavaScript', 'HTML', 'CSS', 'React', 'Vue', 'Angular']
        elif 'backend' in title:
            return ['Python', 'Java', 'Node.js', 'SQL', 'MongoDB', 'Express']
        elif 'fullstack' in title or 'full stack' in title:
            return ['JavaScript', 'HTML', 'CSS', 'Python', 'SQL', 'React', 'Node.js']
        elif 'devops' in title:
            return ['Docker', 'Kubernetes', 'AWS', 'CI/CD', 'Linux', 'Python']
        else:
            return ['JavaScript', 'Python', 'Java', 'SQL', 'Git']
