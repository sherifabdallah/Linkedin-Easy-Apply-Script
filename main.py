"""
LinkedIn AI Job Application Agent - Complete Fixed Version
Applies to jobs immediately as they're found with AI-powered form filling
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from dotenv import load_dotenv
import requests
import logging
from pathlib import Path

# Fix Windows console encoding FIRST
if os.name == 'nt':
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except:
            pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('job_agent.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class JobApplication:
    job_id: str
    title: str
    company: str
    location: str
    timestamp: str
    status: str
    url: str


class GroqAgent:
    """Interface to Groq API for intelligent decision making"""
    
    def __init__(self, model: str = "llama-3.1-70b-versatile"):
        self.model = model
        self.api_key = os.getenv('GROQ_API_KEY')
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY must be set in .env file. Get one free at https://console.groq.com")
        
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.verify_connection()
    
    def verify_connection(self):
        try:
            logger.info("Testing Groq API connection...")
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 10
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("[OK] Connected to Groq API successfully")
            elif response.status_code == 401:
                raise ValueError("Invalid GROQ_API_KEY")
            else:
                logger.warning(f"Groq API responded with status {response.status_code}")
        except Exception as e:
            logger.error(f"[ERROR] Groq API connection failed: {e}")
            raise
    
    def query(self, prompt: str, system_prompt: str = "") -> str:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 500
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Error querying Groq: {e}")
        return ""
    
    def should_apply(self, job_description: str, profile_data: Dict) -> tuple[bool, str]:
        system_prompt = "You are an expert career advisor. Analyze if this job matches software engineering criteria. Return ONLY 'YES' or 'NO' followed by a brief reason."
        
        prompt = f"""Job Description: {job_description[:500]}
Candidate Skills: {', '.join(profile_data.get('skills', []))}

Is this a software engineering related position? Answer YES or NO and brief reason."""
        
        try:
            response = self.query(prompt, system_prompt)
            should_apply = 'yes' in response.lower()[:20]
            return should_apply, response
        except:
            # Fallback
            desc_lower = job_description.lower()
            eng_keywords = ['software engineer', 'developer', 'programmer', 'backend', 'frontend', 'full stack', 'fullstack']
            has_eng = any(k in desc_lower for k in eng_keywords)
            return has_eng, "Keyword match" if has_eng else "No match"


class ProfileManager:
    def __init__(self, profile_path: str = "profile.txt"):
        self.profile_path = profile_path
        self.profile_data = self.load_profile()
    
    def load_profile(self) -> Dict:
        try:
            with open(self.profile_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            profile = {
                'name': self._extract_field(content, 'name'),
                'email': self._extract_field(content, 'email'),
                'phone': self._extract_field(content, 'phone'),
                'location': self._extract_field(content, 'location'),
                'skills': self._extract_list(content, 'skills'),
                'years_experience': self._extract_field(content, 'years_experience'),
                'current_title': self._extract_field(content, 'current_title'),
                'linkedin': self._extract_field(content, 'linkedin'),
                'github': self._extract_field(content, 'github'),
                'website': self._extract_field(content, 'website'),
                'resume_path': self._extract_field(content, 'resume_path'),
                'expected_salary_in_egp': self._extract_field(content, 'expected_salary_in_egp'),
                'expected_salary_in_usd': self._extract_field(content, 'expected_salary_in_usd'),
                'work_experience': self._extract_field(content, 'work_experience'),
                'education': self._extract_field(content, 'education'),
                'willing_to_relocate': self._extract_field(content, 'willing_to_relocate'),
                'requires_sponsorship': self._extract_field(content, 'requires_sponsorship'),
                'willing_to_commute': self._extract_field(content, 'willing_to_commute'),
                'notice_period': self._extract_field(content, 'notice_period'),
                'remote_preference': self._extract_field(content, 'remote_preference'),
            }
            
            # Extract tech-specific experience
            tech_list = ['python', 'javascript', 'react', 'vue', 'angular', 'node', 'nextjs', 
                        'dotnet', 'aspnet', 'java', 'sql', 'aws', 'docker', 'kubernetes']
            for tech in tech_list:
                profile[f'{tech}_experience'] = self._extract_field(content, f'{tech}_experience')
            
            logger.info(f"[OK] Profile loaded: {profile['name']}")
            return profile
        except FileNotFoundError:
            logger.error("[ERROR] profile.txt not found")
            raise
    
    def _extract_field(self, content: str, field: str) -> str:
        pattern = rf'{field}:\s*(.+?)(?:\n|$)'
        match = re.search(pattern, content, re.IGNORECASE)
        return match.group(1).strip() if match else ''
    
    def _extract_list(self, content: str, field: str) -> List[str]:
        pattern = rf'{field}:\s*(.+?)(?:\n\n|\Z)'
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            items = match.group(1).strip()
            return [item.strip() for item in re.split(r'[,\n]', items) if item.strip()]
        return []


class LinkedInJobAgent:
    def __init__(self):
        load_dotenv()
        
        self.email = os.getenv('LINKEDIN_EMAIL')
        self.password = os.getenv('LINKEDIN_PASSWORD')
        
        if not self.email or not self.password:
            raise ValueError("LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env")
        
        self.profile_manager = ProfileManager()
        
        try:
            self.ai_agent = GroqAgent()
        except Exception as e:
            logger.warning(f"[WARNING] Could not connect to Groq: {e}")
            logger.warning("[WARNING] Continuing in basic mode")
            self.ai_agent = None
        
        self.driver = None
        self.applied_jobs = self.load_applied_jobs()
        self.session_stats = {'searched': 0, 'applied': 0, 'skipped': 0, 'errors': 0}
    
    def load_applied_jobs(self) -> set:
        try:
            with open('applied_jobs.json', 'r') as f:
                return set(json.load(f).get('job_ids', []))
        except FileNotFoundError:
            return set()
    
    def save_applied_job(self, job_app: JobApplication):
        try:
            data = {'job_ids': list(self.applied_jobs), 'applications': []}
            try:
                with open('applied_jobs.json', 'r') as f:
                    data = json.load(f)
            except FileNotFoundError:
                pass
            
            data['job_ids'] = list(self.applied_jobs)
            data['applications'].append(asdict(job_app))
            
            with open('applied_jobs.json', 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving: {e}")
    
    def setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--start-maximized')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        logger.info("[OK] Browser initialized")
    
    def login(self):
        try:
            logger.info("Logging in to LinkedIn...")
            self.driver.get('https://www.linkedin.com/login')
            time.sleep(2)
            
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, 'username')))
            email_field.send_keys(self.email)
            
            password_field = self.driver.find_element(By.ID, 'password')
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            
            time.sleep(3)
            
            if 'check' in self.driver.current_url:
                logger.warning("[WARNING] Security check - please solve manually")
                time.sleep(60)
            
            logger.info("[OK] Login successful")
            return True
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def search_jobs(self, keywords: str, location: str = ""):
        try:
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords.replace(' ', '%20')}&f_AL=true"
            if location:
                search_url += f"&location={location.replace(' ', '%20')}"
            
            logger.info(f"Searching jobs: {keywords}")
            self.driver.get(search_url)
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Search error: {e}")
            return False
    
    def process_current_job(self) -> bool:
        """Process the currently selected job and try to apply"""
        try:
            job_id = self._extract_job_id()
            title = self._extract_job_title()
            company = self._extract_job_company()
            
            if not job_id or not title:
                return False
            
            if job_id in self.applied_jobs:
                logger.info(f"[SKIP] Already applied: {title}")
                self.session_stats['skipped'] += 1
                return False
            
            logger.info(f"[CHECKING] {title} at {company}")
            
            job_description = self._extract_job_description()
            
            if self.ai_agent:
                should_apply, reason = self.ai_agent.should_apply(job_description, self.profile_manager.profile_data)
                if not should_apply:
                    logger.info(f"[SKIP] {reason}")
                    self.session_stats['skipped'] += 1
                    return False
                logger.info(f"[MATCH] {reason}")
            
            logger.info(f"[APPLY] Applying to: {title}")
            
            try:
                easy_apply_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.jobs-apply-button'))
                )
                easy_apply_button.click()
                time.sleep(2)
            except TimeoutException:
                logger.info("[SKIP] Not an Easy Apply job")
                self.session_stats['skipped'] += 1
                return False
            
            if self._complete_application():
                self.applied_jobs.add(job_id)
                job_app = JobApplication(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location="",
                    timestamp=datetime.now().isoformat(),
                    status='submitted',
                    url=self.driver.current_url
                )
                self.save_applied_job(job_app)
                self.session_stats['applied'] += 1
                logger.info(f"[SUCCESS] Application submitted!")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error processing job: {e}")
            self.session_stats['errors'] += 1
            return False
    
    def _extract_job_id(self) -> str:
        try:
            current_url = self.driver.current_url
            match = re.search(r'currentJobId=(\d+)', current_url)
            if not match:
                match = re.search(r'jobs/view/(\d+)', current_url)
            return match.group(1) if match else ""
        except:
            return ""
    
    def _extract_job_title(self) -> str:
        selectors = ['.jobs-unified-top-card__job-title', 'h1.t-24', 'h2.t-24']
        for selector in selectors:
            try:
                return self.driver.find_element(By.CSS_SELECTOR, selector).text.strip()
            except:
                continue
        return "Unknown Position"
    
    def _extract_job_company(self) -> str:
        selectors = ['.jobs-unified-top-card__company-name', 'a.app-aware-link']
        for selector in selectors:
            try:
                return self.driver.find_element(By.CSS_SELECTOR, selector).text.strip()
            except:
                continue
        return "Unknown Company"
    
    def _extract_job_description(self) -> str:
        try:
            desc = self.driver.find_element(By.CSS_SELECTOR, '.jobs-description, .jobs-description-content')
            return desc.text
        except:
            return f"{self._extract_job_title()} at {self._extract_job_company()}"
    
    def _complete_application(self) -> bool:
        """Complete the multi-step application process"""
        max_steps = 10
        
        for step in range(max_steps):
            try:
                if self._is_application_complete():
                    return True
                
                self._fill_application_form()
                time.sleep(1)
                
                if not self._click_next_button():
                    self._close_modal()
                    return False
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in step {step}: {e}")
                self._close_modal()
                return False
        
        logger.warning("Max steps reached")
        self._close_modal()
        return False
    
    def _fill_application_form(self):
        """Fill form fields with AI fallback for unknown questions"""
        try:
            logger.info("Filling application form...")
            filled_count = 0
            
            inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="text"], input[type="number"], input[type="email"], input[type="tel"], textarea')
            logger.info(f"Found {len(inputs)} input fields")
            
            for field in inputs:
                try:
                    current_value = field.get_attribute('value')
                    if current_value and current_value.strip():
                        continue
                    
                    label = self._get_field_label(field)
                    input_type = field.get_attribute('type') or 'text'
                    
                    logger.debug(f"Processing field: {label[:60]}")
                    
                    value = self._get_field_value_with_validation(label, input_type, field)
                    
                    if not value:
                        if self._is_descriptive_question(label, input_type, field):
                            if self.ai_agent:
                                logger.info(f"[AI DESCRIPTIVE] {label[:60]}")
                                value = self._ai_answer_field(label, input_type, field)
                            else:
                                value = self._get_generic_answer(label)
                        elif self.ai_agent:
                            logger.info(f"[AI FALLBACK] {label[:60]}")
                            value = self._ai_answer_field(label, input_type, field)
                    
                    if not value:
                        value = self._get_safe_default(label, input_type, field)
                    
                    if value:
                        field.clear()
                        time.sleep(0.2)
                        field.send_keys(str(value))
                        filled_count += 1
                        logger.info(f"[FILLED] {label[:50]} = {value}")
                        
                        field.send_keys(Keys.TAB)
                        time.sleep(0.3)
                    else:
                        logger.warning(f"[SKIP] Could not determine value for: {label[:60]}")
                        
                except Exception as e:
                    logger.debug(f"Error filling field: {e}")
                    continue
            
            selects = self.driver.find_elements(By.TAG_NAME, 'select')
            logger.info(f"Found {len(selects)} dropdown fields")
            for select in selects:
                try:
                    sel_obj = Select(select)
                    if len(sel_obj.options) > 1:
                        label = self._get_field_label(select)
                        selected = self._select_best_option(sel_obj, label)
                        if selected:
                            filled_count += 1
                except:
                    pass
            
            self._handle_questions()
            
            time.sleep(0.5)
            validation_errors = self.driver.find_elements(By.CSS_SELECTOR, '.artdeco-inline-feedback--error, [role="alert"]')
            if validation_errors:
                logger.warning(f"[VALIDATION] Found {len(validation_errors)} errors, attempting fixes...")
                for error_elem in validation_errors:
                    try:
                        error_text = error_elem.text
                        logger.warning(f"Error: {error_text}")
                        
                        parent = error_elem.find_element(By.XPATH, '..')
                        inputs = parent.find_elements(By.CSS_SELECTOR, 'input, select, textarea')
                        
                        for inp in inputs:
                            if not inp.get_attribute('value'):
                                label = self._get_field_label(inp)
                                input_type = inp.get_attribute('type') or 'text'
                                
                                value = self._get_field_value_with_validation(label, input_type, inp)
                                if not value and self.ai_agent:
                                    value = self._ai_answer_field(label, input_type, inp)
                                if not value:
                                    value = self._get_safe_default(label, input_type, inp)
                                
                                if value:
                                    inp.clear()
                                    inp.send_keys(str(value))
                                    inp.send_keys(Keys.TAB)
                                    logger.info(f"[FIXED] {label[:40]} = {value}")
                                    time.sleep(0.3)
                    except Exception as e:
                        logger.debug(f"Could not fix error: {e}")
            
            self._upload_resume()
            
            logger.info(f"Filled {filled_count} fields total")
        except Exception as e:
            logger.error(f"Error filling form: {e}")
    
    def _get_field_label(self, element) -> str:
        try:
            label = element.get_attribute('aria-label')
            if label:
                return label
            field_id = element.get_attribute('id')
            if field_id:
                return self.driver.find_element(By.CSS_SELECTOR, f'label[for="{field_id}"]').text
            return element.get_attribute('placeholder') or ""
        except:
            return ""
    
    def _get_field_value_with_validation(self, label: str, input_type: str, element) -> str:
        """Get field value from profile with validation"""
        label_lower = label.lower()
        p = self.profile_manager.profile_data
        
        if 'email' in label_lower:
            return p.get('email', '')
        
        if 'phone' in label_lower or 'mobile' in label_lower:
            return p.get('phone', '')
        
        if 'first name' in label_lower or 'given name' in label_lower:
            return p.get('name', '').split()[0] if p.get('name') else ''
        if 'last name' in label_lower or 'family name' in label_lower or 'surname' in label_lower:
            parts = p.get('name', '').split()
            return ' '.join(parts[1:]) if len(parts) > 1 else ''
        if 'full name' in label_lower and 'first' not in label_lower and 'last' not in label_lower:
            return p.get('name', '')
        
        if 'linkedin' in label_lower:
            return p.get('linkedin', '')
        if 'github' in label_lower:
            return p.get('github', '')
        if 'website' in label_lower or 'portfolio' in label_lower:
            return p.get('website', '')
        
        if 'city' in label_lower or ('location' in label_lower and 'relocate' not in label_lower):
            location = p.get('location', '')
            if location:
                return location.split(',')[0].strip()
            return ''
        
        tech_keywords = {
            'python': 'python_experience',
            'javascript': 'javascript_experience',
            'react': 'react_experience',
            'vue': 'vue_experience',
            'angular': 'angular_experience',
            'node': 'node_experience',
            'next.js': 'nextjs_experience',
            'next': 'nextjs_experience',
            '.net': 'dotnet_experience',
            'dotnet': 'dotnet_experience',
            'asp.net': 'aspnet_experience',
            'java': 'java_experience',
            'c++': 'cpp_experience',
            'c#': 'csharp_experience',
            'sql': 'sql_experience',
            'aws': 'aws_experience',
            'docker': 'docker_experience',
            'kubernetes': 'kubernetes_experience',
        }
        
        if 'years' in label_lower and 'experience' in label_lower:
            for tech, field_name in tech_keywords.items():
                if tech in label_lower:
                    years = p.get(field_name, p.get('years_experience', '0'))
                    return self._format_years(years, element)
            
            years = p.get('years_experience', '0')
            return self._format_years(years, element)
        
        if 'salary' in label_lower or 'compensation' in label_lower:
            currency = 'egp'
            
            if ('usd' in label_lower or '$' in label_lower or 'dollar' in label_lower) and \
               'egp' not in label_lower and 'egyptian' not in label_lower:
                currency = 'usd'
            
            if currency == 'usd':
                salary = p.get('expected_salary_in_usd', '700')
            else:
                salary = p.get('expected_salary_in_egp', '30000')
            
            logger.info(f"[SALARY] Using {currency.upper()}: {salary}")
            return self._format_number(salary, element)
        
        if 'start' in label_lower and ('date' in label_lower or 'when' in label_lower or 'available' in label_lower):
            notice = p.get('notice_period', '1 month')
            if 'immediate' in notice.lower() or 'asap' in notice.lower():
                return '0'
            match = re.search(r'(\d+)', notice)
            if match:
                num = match.group(1)
                if 'week' in notice.lower():
                    return str(int(num) * 7)
                elif 'month' in notice.lower():
                    return str(int(num) * 30)
                return num
            return '30'
        
        if 'current company' in label_lower or 'employer' in label_lower:
            work_exp = p.get('work_experience', '')
            if 'at ' in work_exp:
                company = work_exp.split('at ')[1].split('(')[0].strip()
                return company
            return ''
        
        return ""
    
    def _format_years(self, years: str, element) -> str:
        try:
            years_int = int(float(years))
            
            min_val = element.get_attribute('min')
            max_val = element.get_attribute('max')
            
            if min_val:
                years_int = max(years_int, int(min_val))
            if max_val:
                years_int = min(years_int, int(max_val))
            else:
                years_int = min(years_int, 99)
            
            years_int = max(years_int, 0)
            
            return str(years_int)
        except:
            return '1'
    
    def _format_number(self, value: str, element) -> str:
        try:
            num = float(value)
            
            step = element.get_attribute('step')
            min_val = element.get_attribute('min')
            
            if step and '.' in step:
                formatted = f"{num:.2f}"
            else:
                formatted = str(int(num))
            
            if min_val:
                min_float = float(min_val)
                if float(formatted) < min_float:
                    if step and '.' in step:
                        formatted = f"{min_float + 0.5:.2f}"
                    else:
                        formatted = str(int(min_float) + 1)
            
            return formatted
        except:
            return str(value)
    
    def _is_descriptive_question(self, label: str, input_type: str, element) -> bool:
        label_lower = label.lower()
        
        if element.tag_name == 'textarea':
            return True
        
        try:
            minlength = element.get_attribute('minlength')
            if minlength and int(minlength) > 50:
                return True
        except:
            pass
        
        descriptive_keywords = [
            'why', 'describe', 'tell us', 'explain', 'what makes',
            'how would', 'your biggest', 'your greatest',
            'achievement', 'experience with', 'motivate',
            'passion', 'interest in', 'fit for', 'contribute',
            'challenge', 'overcome', 'learn', 'strength',
            'weakness', 'improve', 'goal', 'aspiration'
        ]
        
        return any(keyword in label_lower for keyword in descriptive_keywords)
    
    def _get_generic_answer(self, label: str) -> str:
        label_lower = label.lower()
        p = self.profile_manager.profile_data
        
        if 'why' in label_lower and 'company' in label_lower:
            return f"I am excited about the opportunity to contribute my skills in {', '.join(p.get('skills', ['software development'])[:3])} to help drive innovation and growth."
        
        if 'why' in label_lower and ('position' in label_lower or 'role' in label_lower):
            return f"This role aligns perfectly with my {p.get('years_experience', '2')} years of experience and passion for building impactful solutions."
        
        if 'strength' in label_lower or 'strong' in label_lower:
            return f"My strengths include problem-solving, collaboration, and expertise in {', '.join(p.get('skills', ['software development'])[:3])}."
        
        if 'weakness' in label_lower:
            return "I sometimes focus too deeply on perfecting details, but I've learned to balance thoroughness with meeting deadlines."
        
        if 'achievement' in label_lower or 'accomplish' in label_lower:
            work_exp = p.get('work_experience', '')
            if work_exp:
                return work_exp.split('-')[1].strip() if '-' in work_exp else work_exp[:150]
            return "Successfully delivered multiple projects that improved system performance and user experience."
        
        if 'challenge' in label_lower:
            return "I tackled complex technical challenges by breaking them into manageable parts, collaborating with team members, and continuously learning new approaches."
        
        if 'goal' in label_lower:
            return f"My goal is to continue growing as a {p.get('current_title', 'software engineer')} while contributing to meaningful projects that make a positive impact."
        
        if 'learn' in label_lower and 'company' in label_lower:
            return "I'm eager to learn from experienced team members, explore new technologies, and contribute to innovative projects."
        
        return "I am highly motivated and committed to delivering quality work while continuously improving my skills."
    
    def _ai_answer_field(self, label: str, input_type: str, element) -> str:
        """Use AI to intelligently answer fields with ENHANCED profile context"""
        try:
            p = self.profile_manager.profile_data
            
            field_context = {
                'label': label,
                'type': input_type,
                'placeholder': element.get_attribute('placeholder') or '',
                'min': element.get_attribute('min') or '',
                'max': element.get_attribute('max') or '',
                'minlength': element.get_attribute('minlength') or '',
                'maxlength': element.get_attribute('maxlength') or '',
            }
            
            is_descriptive = self._is_descriptive_question(label, input_type, element)
            
            system_prompt = f"""You are a professional job application assistant helping a candidate apply for jobs.

CANDIDATE PROFILE:
Name: {p.get('name', 'N/A')}
Current Title: {p.get('current_title', 'N/A')}
Experience: {p.get('years_experience', 'N/A')} years
Skills: {', '.join(p.get('skills', []))}
Education: {p.get('education', 'N/A')}
Work Experience: {p.get('work_experience', 'N/A')}

RESPONSE RULES:
- For numeric fields: Return ONLY the number (e.g., "2" or "2.5")
- For short text fields (name, email, etc.): Return exact value from profile
- For descriptive questions: Write professional, compelling 2-4 sentence answers using the profile data
- For yes/no: Return only "yes" or "no"
- For dates: Use realistic ISO format (YYYY-MM-DD) or relative time
- If unknown tech/skill: Return "0" for experience or "No experience yet, but eager to learn"
- Be honest, professional, and enthusiastic
- Match the tone to the field length (short fields = concise, long fields = detailed)
"""

            if is_descriptive:
                user_prompt = f"""Question: {label}
Field Type: {input_type} (text area/long answer expected)
{f"Minimum length: {field_context['minlength']} characters" if field_context['minlength'] else ''}

Write a professional, engaging answer (2-4 sentences) that:
1. Uses specific details from the candidate's profile
2. Shows enthusiasm and fit for the role
3. Demonstrates relevant skills and experience
4. Sounds natural and authentic

Answer:"""
            else:
                user_prompt = f"""Question: {label}
Field Type: {input_type}
{f'Placeholder: {field_context["placeholder"]}' if field_context["placeholder"] else ''}
{f'Constraints: Min={field_context["min"]}, Max={field_context["max"]}' if field_context["min"] or field_context["max"] else ''}

Provide the appropriate answer. Return ONLY the value, no explanation.
Answer:"""

            response = self.ai_agent.query(user_prompt, system_prompt)
            
            answer = response.strip().strip('"').strip("'")
            
            if input_type == 'number':
                try:
                    float(answer)
                    return answer
                except:
                    logger.warning(f"AI returned non-numeric: {answer}")
                    return '0'
            
            if field_context['maxlength']:
                try:
                    max_len = int(field_context['maxlength'])
                    if len(answer) > max_len:
                        answer = answer[:max_len-3] + '...'
                except:
                    pass
            
            logger.info(f"[AI ANSWER] {answer[:80]}")
            return answer
            
        except Exception as e:
            logger.warning(f"AI answer failed: {e}")
            return ""
    
    def _get_safe_default(self, label: str, input_type: str, element) -> str:
        """Provide safe default values for unknown fields"""
        label_lower = label.lower()
        
        if input_type == 'number':
            if 'experience' in label_lower or 'years' in label_lower:
                return '0'
            
            min_val = element.get_attribute('min')
            if min_val:
                try:
                    return str(int(float(min_val)))
                except:
                    pass
            
            return '1'
        
        if 'start' in label_lower or 'available' in label_lower or 'join' in label_lower:
            if 'date' in label_lower:
                from datetime import timedelta
                future_date = datetime.now() + timedelta(days=30)
                return future_date.strftime('%Y-%m-%d')
            return '30'
        
        return ""
    
    def _select_best_option(self, select_obj: Select, label: str) -> bool:
        """Select the best option from a dropdown"""
        try:
            label_lower = label.lower()
            options = select_obj.options
            
            if len(options) <= 1:
                return False
            
            first_text = options[0].text.lower()
            if any(word in first_text for word in ['select', 'choose', 'please']):
                start_idx = 1
            else:
                start_idx = 0
            
            if 'education' in label_lower or 'degree' in label_lower:
                for opt in options[start_idx:]:
                    opt_text = opt.text.lower()
                    if 'bachelor' in opt_text or 'bsc' in opt_text or "b.s" in opt_text:
                        select_obj.select_by_visible_text(opt.text)
                        logger.info(f"Selected education: {opt.text}")
                        return True
            
            if 'english' in label_lower or 'language' in label_lower:
                for opt in options[start_idx:]:
                    opt_text = opt.text.lower()
                    if 'professional' in opt_text or 'fluent' in opt_text or 'advanced' in opt_text:
                        select_obj.select_by_visible_text(opt.text)
                        logger.info(f"Selected language: {opt.text}")
                        return True
            
            if len(options) > start_idx:
                select_obj.select_by_index(start_idx)
                logger.info(f"Selected default: {options[start_idx].text}")
                return True
            
            return False
        except Exception as e:
            logger.debug(f"Error selecting option: {e}")
            return False
    
    def _handle_questions(self):
        """Handle radio buttons and checkboxes with comprehensive logic"""
        try:
            p = self.profile_manager.profile_data
            
            fieldsets = self.driver.find_elements(By.CSS_SELECTOR, 'fieldset')
            
            for fieldset in fieldsets:
                try:
                    legend = fieldset.find_elements(By.TAG_NAME, 'legend')
                    question_text = legend[0].text if legend else fieldset.text
                    question_lower = question_text.lower()
                    
                    labels = fieldset.find_elements(By.TAG_NAME, 'label')
                    
                    if not labels:
                        continue
                    
                    logger.debug(f"[QUESTION] {question_text[:80]}")
                    
                    selected = False
                    
                    if any(word in question_lower for word in ['commut', 'location', 'travel to']):
                        willing = p.get('willing_to_commute', 'yes').lower()
                        target = 'yes' if willing == 'yes' else 'no'
                        selected = self._select_radio_option(labels, target, question_text)
                    
                    elif any(word in question_lower for word in ['sponsorship', 'visa', 'work authorization', 'authorized to work', 'right to work']):
                        requires = p.get('requires_sponsorship', 'no').lower()
                        target = 'no' if requires == 'no' else 'yes'
                        selected = self._select_radio_option(labels, target, question_text)
                    
                    elif any(word in question_lower for word in ['relocat', 'willing to move', 'open to relocat']):
                        willing = p.get('willing_to_relocate', 'yes').lower()
                        target = 'yes' if willing == 'yes' else 'no'
                        selected = self._select_radio_option(labels, target, question_text)
                    
                    elif any(word in question_lower for word in ['remote', 'work from home', 'hybrid']):
                        pref = p.get('remote_preference', 'hybrid').lower()
                        if 'hybrid' in pref:
                            target = 'hybrid'
                        elif 'remote' in pref:
                            target = 'remote'
                        else:
                            target = 'yes'
                        selected = self._select_radio_option(labels, target, question_text)
                    
                    elif 'clearance' in question_lower or 'security' in question_lower:
                        selected = self._select_radio_option(labels, 'no', question_text)
                    
                    elif 'background check' in question_lower or 'background screening' in question_lower:
                        selected = self._select_radio_option(labels, 'yes', question_text)
                    
                    elif 'drug' in question_lower and 'test' in question_lower:
                        selected = self._select_radio_option(labels, 'yes', question_text)
                    
                    elif any(word in question_lower for word in ['18 years', 'legal age', 'age of majority']):
                        selected = self._select_radio_option(labels, 'yes', question_text)
                    
                    elif 'eligible to work' in question_lower or 'legally authorized' in question_lower:
                        selected = self._select_radio_option(labels, 'yes', question_text)
                    
                    elif 'previously applied' in question_lower or 'applied before' in question_lower:
                        selected = self._select_radio_option(labels, 'no', question_text)
                    
                    elif 'know anyone' in question_lower or 'employee referral' in question_lower:
                        selected = self._select_radio_option(labels, 'no', question_text)
                    
                    elif 'immediately' in question_lower or 'urgent' in question_lower:
                        selected = self._select_radio_option(labels, 'yes', question_text)
                    
                    if not selected and labels:
                        try:
                            input_elem = labels[0].find_element(By.TAG_NAME, 'input')
                            if not input_elem.is_selected():
                                labels[0].click()
                                time.sleep(0.2)
                                logger.info(f"[DEFAULT] Selected first option: {labels[0].text[:30]}")
                        except:
                            pass
                            
                except Exception as e:
                    logger.debug(f"Error processing fieldset: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in _handle_questions: {e}")
    
    def _select_radio_option(self, labels, target: str, question: str) -> bool:
        """Helper to select radio button based on target keyword"""
        try:
            target_lower = target.lower()
            
            for label in labels:
                label_text = label.text.lower()
                
                try:
                    input_elem = label.find_element(By.TAG_NAME, 'input')
                    if input_elem.is_selected():
                        logger.debug(f"[ALREADY SELECTED] {label.text[:30]}")
                        return True
                except:
                    pass
                
                if target_lower in label_text or label_text in target_lower:
                    try:
                        label.click()
                        time.sleep(0.2)
                        logger.info(f"[SELECTED] {label.text[:40]} for: {question[:60]}")
                        return True
                    except Exception as e:
                        logger.debug(f"Click failed: {e}")
                        try:
                            input_elem = label.find_element(By.TAG_NAME, 'input')
                            input_elem.click()
                            time.sleep(0.2)
                            logger.info(f"[SELECTED via input] {label.text[:40]}")
                            return True
                        except:
                            pass
            
            if target_lower == 'yes':
                for label in labels:
                    label_text = label.text.lower()
                    if any(word in label_text for word in ['yes', 'i am', 'i do', 'willing', 'able']):
                        try:
                            label.click()
                            time.sleep(0.2)
                            logger.info(f"[SELECTED partial] {label.text[:40]}")
                            return True
                        except:
                            pass
            
            elif target_lower == 'no':
                for label in labels:
                    label_text = label.text.lower()
                    if any(word in label_text for word in ['no', 'not', "don't", 'unable', 'do not require']):
                        try:
                            label.click()
                            time.sleep(0.2)
                            logger.info(f"[SELECTED partial] {label.text[:40]}")
                            return True
                        except:
                            pass
            
            logger.warning(f"Could not find option '{target}' for: {question[:60]}")
            return False
            
        except Exception as e:
            logger.error(f"Error selecting radio: {e}")
            return False
    
    def _upload_resume(self):
        try:
            resume_path = self.profile_manager.profile_data.get('resume_path', '')
            if resume_path and Path(resume_path).exists():
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                for inp in file_inputs:
                    inp.send_keys(str(Path(resume_path).absolute()))
                    logger.info("[OK] Uploaded resume")
                    break
        except:
            pass
    
    def _click_next_button(self) -> bool:
        """Click next/submit button with improved detection and retry logic"""
        for attempt in range(3):
            try:
                time.sleep(0.5)
                
                button = None
                
                submit_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Submit application"]')
                if submit_btns:
                    button = submit_btns[0]
                    logger.info("Found 'Submit application' button")
                
                if not button:
                    review_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Review"]')
                    if review_btns:
                        button = review_btns[0]
                        logger.info("Found 'Review' button")
                
                if not button:
                    next_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Continue to next step"], button[aria-label*="Next"]')
                    if next_btns:
                        button = next_btns[0]
                        logger.info("Found 'Next' button")
                
                if not button:
                    all_buttons = self.driver.find_elements(By.CSS_SELECTOR, '.jobs-easy-apply-modal button, .artdeco-modal button')
                    for btn in all_buttons:
                        if not btn.is_displayed():
                            continue
                        text = btn.text.lower()
                        if any(word in text for word in ['submit', 'review', 'next', 'continue']):
                            button = btn
                            logger.info(f"Found button by text: {btn.text}")
                            break
                
                if not button:
                    logger.warning("No Next/Submit button found")
                    return False
                
                try:
                    modal = self.driver.find_element(By.CSS_SELECTOR, '.jobs-easy-apply-content, .artdeco-modal__content')
                    self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", modal)
                    time.sleep(0.5)
                except:
                    pass
                
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", button)
                time.sleep(0.5)
                
                if button.get_attribute('disabled'):
                    logger.warning("Button is disabled - may need to fill required fields")
                    return False
                
                self.driver.execute_script("arguments[0].click();", button)
                logger.info("Clicked button successfully")
                time.sleep(1)
                return True
                
            except StaleElementReferenceException:
                if attempt < 2:
                    logger.debug(f"Stale element, retrying... (attempt {attempt + 1})")
                    time.sleep(1)
                    continue
                else:
                    logger.warning("Stale element after 3 attempts")
                    return False
            except Exception as e:
                logger.debug(f"Click error on attempt {attempt + 1}: {e}")
                if attempt < 2:
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Failed to click after 3 attempts: {e}")
                    return False
        
        return False
    
    def _is_application_complete(self) -> bool:
        """Check if application is complete"""
        try:
            time.sleep(1)
            
            page_source = self.driver.page_source.lower()
            success_phrases = [
                'application sent',
                'application submitted',
                'successfully applied',
                'your application was sent',
                'application was sent to'
            ]
            
            for phrase in success_phrases:
                if phrase in page_source:
                    logger.info(f"Found success phrase: {phrase}")
                    try:
                        done_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="Dismiss"]')
                        done_btn.click()
                    except:
                        pass
                    return True
            
            try:
                done_buttons = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Done"]')
                if done_buttons:
                    logger.info("Found 'Done' button - application complete")
                    done_buttons[0].click()
                    time.sleep(1)
                    return True
            except:
                pass
            
            try:
                modal = self.driver.find_element(By.CSS_SELECTOR, '.jobs-easy-apply-modal')
                if not modal.is_displayed():
                    logger.info("Modal closed - application complete")
                    return True
            except:
                logger.info("Modal not found - application may be complete")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking completion: {e}")
            return False
    
    def _close_modal(self):
        try:
            close_btns = self.driver.find_elements(By.CSS_SELECTOR, 'button[aria-label*="Dismiss"]')
            if close_btns:
                close_btns[0].click()
                time.sleep(1)
                discard = self.driver.find_elements(By.CSS_SELECTOR, 'button[data-control-name*="discard"]')
                if discard:
                    discard[0].click()
        except:
            pass
    
    def click_next_job_card(self, current_index: int) -> bool:
        """Click the next job card in the list"""
        try:
            time.sleep(1)
            
            selectors = ['.scaffold-layout__list-item', 'li.jobs-search-results__list-item']
            job_cards = []
            
            for selector in selectors:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if len(job_cards) > current_index + 1:
                    break
            
            if len(job_cards) <= current_index + 1:
                return False
            
            next_card = job_cards[current_index + 1]
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_card)
            time.sleep(1)
            
            try:
                next_card.click()
            except:
                link = next_card.find_element(By.TAG_NAME, 'a')
                link.click()
            
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.debug(f"Error clicking next job card: {e}")
            return False
    
    def run(self, keywords: str = "software engineer", location: str = "", max_applications: int = 10):
        """Main execution loop - processes jobs one by one"""
        try:
            logger.info("=" * 60)
            logger.info("LinkedIn AI Job Application Agent Starting")
            logger.info("=" * 60)
            
            self.setup_driver()
            
            if not self.login():
                return
            
            time.sleep(3)
            
            if not self.search_jobs(keywords, location):
                return
            
            applications_submitted = 0
            current_job_index = 0
            max_jobs_per_page = 25
            
            while applications_submitted < max_applications:
                self.session_stats['searched'] += 1
                
                if self.process_current_job():
                    applications_submitted += 1
                    logger.info(f"Progress: {applications_submitted}/{max_applications} applications")
                    time.sleep(3)
                
                if not self.click_next_job_card(current_job_index):
                    logger.info("Moving to next page...")
                    try:
                        next_page = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="View next page"]')
                        next_page.click()
                        time.sleep(3)
                        current_job_index = -1
                    except:
                        logger.info("No more jobs available")
                        break
                
                current_job_index += 1
                
                if current_job_index >= max_jobs_per_page:
                    try:
                        next_page = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="View next page"]')
                        next_page.click()
                        time.sleep(3)
                        current_job_index = 0
                    except:
                        break
                
                time.sleep(2)
            
            logger.info("=" * 60)
            logger.info("Session Complete!")
            logger.info(f"Jobs Searched: {self.session_stats['searched']}")
            logger.info(f"Applications Submitted: {self.session_stats['applied']}")
            logger.info(f"Jobs Skipped: {self.session_stats['skipped']}")
            logger.info(f"Errors: {self.session_stats['errors']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            if self.driver:
                logger.info("Closing browser...")
                time.sleep(3)
                self.driver.quit()


def main():
    print("Please Edit Profile.txt and your cv path")
    keywords = input('Enter keywords (comma-separated) e.g."Software Engineer":')
    try:
        agent = LinkedInJobAgent()
        agent.run(
            keywords=keywords,
            location=keywords,
            max_applications=10
        )
    except KeyboardInterrupt:
        logger.info("\nStopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()