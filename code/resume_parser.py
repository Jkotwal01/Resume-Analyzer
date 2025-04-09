import requests
import fitz  # PyMuPDF
import re
import json
import PyPDF2
import os
from typing import Dict, List, Union
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
                # Try PyMuPDF first
                doc = fitz.open(file_path)
                for page in doc:
                    text += page.get_text()
            except Exception:
                # Fallback to PyPDF2
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
            # Try GMINI API first
            response = self._call_gmini_api(file_path)
            if response and response.get('status_code') == 200:
                return self._parse_gmini_response(response)
            
            # Fallback to local parsing
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
        
        # Enhanced regex patterns
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
        
        # Count mentions
        mentions = context.count(skill_lower)
        # Look for experience indicators
        expert_indicators = ['expert', 'advanced', 'senior', 'lead']
        intermediate_indicators = ['intermediate', 'proficient']
        
        if any(indicator in context[max(0, context.find(skill_lower)-50):context.find(skill_lower)+50] 
               for indicator in expert_indicators):
            return 5
        elif any(indicator in context[max(0, context.find(skill_lower)-50):context.find(skill_lower)+50] 
                for indicator in intermediate_indicators):
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

    def analyze_job_fit(self, resume_text: str, job_title: str = "Software Engineer") -> Dict:
        """Analyze resume fit for a job using Gemini API"""
        try:
            url = f"{GMINI_API_URL}"  # Remove :generateContent?key={GMINI_API_KEY}
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GMINI_API_KEY}'
            }
            
            prompt = {
                "contents": [{
                    "parts": [{
                        "text": f"""Analyze this resume for a {job_title} position and provide a detailed scoring:

                        Resume Text:
                        {resume_text}

                        Provide a detailed analysis with the following scores in JSON format:
                        1. Job Fit Score (0-100): Based on overall match for the position
                        2. Technical Skills Match (0-100): Based on required technical skills
                        3. Experience Relevance (0-100): Based on relevant work experience
                        4. Education Match (0-100): Based on educational requirements
                        5. Skills Gap Analysis: List of present and missing critical skills
                        6. Career Level Assessment: Junior/Mid/Senior based on experience
                        7. Improvement Recommendations: Prioritized list of areas to improve

                        Return the analysis in this exact JSON structure:
                        {{
                            "job_fit_score": {{
                                "overall_score": number,
                                "technical_match": number,
                                "experience_match": number,
                                "education_match": number,
                                "detailed_breakdown": {{
                                    "technical_skills": number,
                                    "experience": number,
                                    "education": number,
                                    "project_relevance": number,
                                    "industry_alignment": number
                                }}
                            }}
                        }}"""
                    }]
                }]
            }

            print("Calling Gemini API...")
            response = requests.post(url, headers=headers, json=prompt)
            print(f"API Response Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    try:
                        analysis_text = result['candidates'][0]['content']['parts'][0]['text']
                        analysis = json.loads(analysis_text)
                        
                        # Calculate weighted job fit score
                        weights = {
                            'technical_skills': 0.35,
                            'experience': 0.25,
                            'education': 0.15,
                            'project_relevance': 0.15,
                            'industry_alignment': 0.10
                        }
                        
                        detailed_scores = analysis['job_fit_score']['detailed_breakdown']
                        weighted_score = sum(
                            detailed_scores[key] * weight 
                            for key, weight in weights.items()
                        )
                        
                        analysis['job_fit_score']['overall_score'] = round(weighted_score, 1)
                        return analysis
                        
                    except (KeyError, json.JSONDecodeError) as e:
                        print(f"Error parsing API response: {e}")
                        return self._generate_fallback_analysis()
            
            print(f"API Error Response: {response.text}")
            return self._generate_fallback_analysis()
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return self._generate_fallback_analysis()

    def _structure_text_response(self, text: str) -> Dict:
        """Convert unstructured text response to structured format"""
        # Basic text analysis to extract information
        skills = re.findall(r'(?i)(?:skills?|technologies?|programming|languages?)[:]\s*([^\n]+)', text)
        experience = re.findall(r'(?i)(?:experience|work history)[:]\s*([^\n]+)', text)
        education = re.findall(r'(?i)(?:education|qualification)[:]\s*([^\n]+)', text)
        
        return {
            "ats_score": {
                "score": 75,  # Default score
                "format_score": 80,
                "keyword_score": 70,
                "optimization_tips": ["Format detected skills sections well", 
                                    "Include more specific achievements"]
            },
            "job_fit_score": 70,  # Default score
            "technical_assessment": {
                "present_skills": skills[0].split(',') if skills else [],
                "missing_skills": [],
                "skill_levels": {}
            },
            "improvement_areas": [{
                "area": "Skills Enhancement",
                "importance": "high",
                "action_items": ["Consider adding more technical skills",
                               "Quantify achievements with metrics"]
            }],
            "strengths": [{
                "category": "experience",
                "description": experience[0] if experience else "Experience section needs review",
                "relevance": 80
            }],
            "career_trajectory": {
                "current_level": "mid",
                "potential_roles": ["Senior Developer", "Team Lead"],
                "development_path": ["Enhance technical skills", "Gain leadership experience"]
            }
        }

    def _enhance_analysis(self, analysis: Dict) -> Dict:
        """Enhance the analysis with additional metrics"""
        # Calculate overall strength score
        strength_score = sum(s['relevance'] for s in analysis.get('strengths', []))
        
        # Calculate skill gap score
        present_skills = len(analysis.get('technical_assessment', {}).get('present_skills', []))
        missing_skills = len(analysis.get('technical_assessment', {}).get('missing_skills', []))
        skill_gap_score = (present_skills / (present_skills + missing_skills)) * 100 if (present_skills + missing_skills) > 0 else 0
        
        # Add enhanced metrics
        analysis['enhanced_metrics'] = {
            'strength_score': min(strength_score, 100),
            'skill_gap_score': round(skill_gap_score, 2),
            'improvement_priority_distribution': {
                'high': len([i for i in analysis.get('improvement_areas', []) if i['importance'] == 'high']),
                'medium': len([i for i in analysis.get('improvement_areas', []) if i['importance'] == 'medium']),
                'low': len([i for i in analysis.get('improvement_areas', []) if i['importance'] == 'low'])
            }
        }
        
        return analysis

    def _generate_fallback_analysis(self) -> Dict:
        """Generate fallback analysis when API fails"""
        return {
            "job_fit_score": {
                "overall_score": 65,
                "technical_match": 70,
                "experience_match": 65,
                "education_match": 80,
                "detailed_breakdown": {
                    "technical_skills": 70,
                    "experience": 65,
                    "education": 80,
                    "project_relevance": 60,
                    "industry_alignment": 65
                }
            },
            "ats_score": {
                "score": 70,
                "format_score": 80,
                "keyword_score": 60,
                "optimization_tips": [
                    "Use industry-standard section headings",
                    "Include more keywords from job description",
                    "Quantify achievements with metrics"
                ]
            },
            "technical_assessment": {
                "present_skills": ["Python", "JavaScript", "SQL"],
                "missing_skills": ["AWS", "Docker", "Kubernetes"],
                "skill_levels": {
                    "Python": {
                        "level": "intermediate",
                        "confidence": 80
                    }
                }
            },
            "improvement_areas": [
                {
                    "title": "Cloud Technologies",
                    "details": "Gain experience with major cloud platforms",
                    "priority": "high",
                    "icon": "cloud"
                },
                {
                    "title": "DevOps Skills",
                    "details": "Learn containerization and CI/CD practices",
                    "priority": "medium",
                    "icon": "cog"
                }
            ],
            "recommendations": [
                {
                    "title": "Cloud Certification",
                    "details": "Obtain AWS or Azure certification",
                    "type": "certification",
                    "priority": "high",
                    "icon": "certificate"
                },
                {
                    "title": "Portfolio Enhancement",
                    "details": "Build projects showcasing cloud and DevOps skills",
                    "type": "project",
                    "priority": "medium",
                    "icon": "folder"
                }
            ],
            "strengths": [
                {
                    "title": "Strong Programming Foundation",
                    "details": "Solid understanding of programming fundamentals and algorithms",
                    "icon": "code"
                },
                {
                    "title": "Technical Skills",
                    "details": "Proficient in multiple programming languages and frameworks",
                    "icon": "chip"
                },
                {
                    "title": "Problem Solving",
                    "details": "Strong analytical and problem-solving capabilities",
                    "icon": "puzzle"
                }
            ],
            "career_trajectory": {
                "current_level": "mid",
                "potential_roles": ["Senior Software Engineer", "Lead Developer"],
                "development_path": ["Get cloud certification", "Lead team projects"]
            }
        }
