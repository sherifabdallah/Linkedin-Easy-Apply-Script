# LinkedIn AI Job Application Agent

An intelligent Python bot that automatically applies to LinkedIn Easy Apply jobs using AI-powered form filling. The bot uses Groq's LLM to make smart decisions about job matching and to generate compelling, personalized answers to application questions.

## Features

- **AI-Powered Job Matching**: Uses Groq API to analyze job descriptions and determine fit
- **Intelligent Form Filling**: Automatically fills out application forms with data from your profile
- **Descriptive Question Handling**: AI generates professional, personalized answers to "Why do you want this job?" type questions
- **Resume Auto-Upload**: Automatically attaches your resume to applications
- **Duplicate Prevention**: Tracks applied jobs to avoid reapplying
- **Multi-Step Application Support**: Handles complex multi-page application forms
- **Validation Error Recovery**: Detects and fixes form validation errors automatically
- **EGP/USD Salary Handling**: Prioritizes Egyptian Pounds with smart currency detection

## Prerequisites

- Python 3.8+
- Chrome browser installed
- ChromeDriver (compatible with your Chrome version)
- LinkedIn account
- Groq API key (free tier available)

## Installation

1. **Clone or download this repository**

2. **Install required packages:**
```bash
pip install selenium python-dotenv requests
```

3. **Download ChromeDriver:**
   - Visit: https://chromedriver.chromium.org/downloads
   - Download version matching your Chrome browser
   - Add to system PATH or place in project directory

4. **Get a free Groq API key:**
   - Visit: https://console.groq.com
   - Sign up for free account
   - Generate API key

## Configuration

### 1. Create `.env` file in project root:

```env
LINKEDIN_EMAIL=your.email@example.com
LINKEDIN_PASSWORD=your_password
GROQ_API_KEY=your_groq_api_key_here
```

### 2. Create `profile.txt` with your information:

```txt
name: Sherif Abdullah
email: sherif.abdullah@vertowave.com
phone: +201061403772
location: Cairo, Egypt

current_title: Senior Software Engineer
years_experience: 2
current_salary_in_egp: 25000
current_salary_in_usd: 500
expected_salary_in_egp: 30000
expected_salary_in_usd: 700

skills: Python, JavaScript, React, .NET, ASP.NET, AWS, Docker, Kubernetes, PostgreSQL, MongoDB, REST APIs, Git, CI/CD, Agile, Frontend, Backend, Microservices

# Technology-specific experience (years) - SET TO 0 IF YOU DON'T KNOW
python_experience: 2
javascript_experience: 2
react_experience: 2
vue_experience: 0
angular_experience: 0
dotnet_experience: 2
aspnet_experience: 2
nextjs_experience: 2
sql_experience: 2
aws_experience: 2
docker_experience: 2
kubernetes_experience: 2
node_experience: 1
java_experience: 0
typescript_experience: 2

education: Bachelor of Science in Computer Science, MTI University
education_level: Bachelor's Degree

linkedin: https://www.linkedin.com/in/your-profile/
github: https://github.com/yourusername
website: https://yourwebsite.com

resume_path: C:/path/to/your/resume.pdf

# Work Experience (used by AI for descriptive answers)
work_experience: Senior Software Engineer at VertoWave (2024-Present) - Led development of microservices architecture serving 10M+ users, reduced API response time by 60% through optimization, mentored team of 5 junior developers

# Preferences for Yes/No questions
notice_period: 1 month
available_to_start: 30 days
willing_to_relocate: yes
requires_sponsorship: no
willing_to_commute: yes
remote_preference: hybrid
english_level: Professional
```

**Important Notes:**
- Update the `resume_path` with the full absolute path to your resume
- Set tech experience to `0` for technologies you don't know (the bot will answer honestly)
- The `work_experience` field is used by AI to generate compelling answers

## Usage

### Basic Usage

Run the bot with default settings (applies to 10 software engineer jobs):

```bash
python main.py
```


### Run Options

```python
agent.run(
    keywords=keywords,  # Job search keywords
    location=location,                   # Location (empty = any)
    max_applications=10            # Stop after N applications
)
```

## How It Works

### 1. Job Discovery
- Searches LinkedIn using your keywords
- Filters for "Easy Apply" jobs only
- Processes jobs one-by-one (immediate application)

### 2. AI Job Matching
```
Job Description → Groq AI → Should Apply?
                    ↓
    YES: Proceed    NO: Skip to next job
```

### 3. Smart Form Filling

**Three-Level Fallback System:**

1. **Profile Lookup** (Fastest)
   - Direct field mapping from profile.txt
   - Email, phone, years of experience, etc.

2. **AI Generation** (For descriptive questions)
   - "Why do you want this job?" → AI writes personalized answer using your profile
   - "Describe your biggest achievement" → AI uses your work experience
   - "What makes you a good fit?" → AI highlights relevant skills

3. **Safe Defaults** (Last resort)
   - Unknown tech experience → 0
   - Date fields → 30 days from now

### 4. Validation & Recovery
- Detects red validation error messages
- Automatically retries filling problematic fields
- Uses AI to answer unclear questions

## AI-Powered Features

### Job Matching
The AI analyzes job descriptions and compares them with your skills:
```
✓ Software Engineer + Python skills → APPLY
✗ Sales Manager + Python skills → SKIP
```

### Descriptive Answers
For questions like "Why are you interested?", the AI generates answers using your profile:

**Question:** "Why do you want to work at our company?"

**AI Answer:** "I'm excited to join your company because it aligns with my 2 years of experience in Python, JavaScript, and React. Having led microservices development serving 10M+ users at VertoWave, I'm eager to contribute my expertise in scalable architecture to your innovative team."

## Output Files

### `applied_jobs.json`
Tracks all submitted applications:
```json
{
  "job_ids": ["123456", "789012"],
  "applications": [
    {
      "job_id": "123456",
      "title": "Senior Software Engineer",
      "company": "Tech Corp",
      "timestamp": "2025-01-15T10:30:00",
      "status": "submitted",
      "url": "https://linkedin.com/jobs/view/123456"
    }
  ]
}
```

### `job_agent.log`
Detailed execution log:
```
2025-01-15 10:30:15 - INFO - [OK] Connected to Groq API
2025-01-15 10:30:20 - INFO - [CHECKING] Senior Software Engineer at Tech Corp
2025-01-15 10:30:22 - INFO - [MATCH] Strong fit - Python and AWS experience
2025-01-15 10:30:25 - INFO - [FILLED] Email = sherif.abdullah@vertowave.com
2025-01-15 10:30:27 - INFO - [AI DESCRIPTIVE] Why do you want this job?
2025-01-15 10:30:30 - INFO - [SUCCESS] Application submitted!
```

## Configuration Tips

### For Egyptian Market
```txt
expected_salary_in_egp: 30000  # Monthly salary in EGP
expected_salary_in_usd: 700    # If applying to international roles
location: Cairo, Egypt
```

### For International Roles
```txt
expected_salary_in_usd: 60000  # Annual salary in USD
willing_to_relocate: yes
requires_sponsorship: yes      # If you need visa sponsorship
```

### Common Questions Handling

**Sponsorship:** Set `requires_sponsorship: no` if you can work without visa

**Commuting:** Set `willing_to_commute: yes` for on-site roles

**Remote Work:** Set `remote_preference: remote` or `hybrid` or `onsite`

**Notice Period:** Set `notice_period: 1 month` (or your actual notice period)

## Troubleshooting

### Bot stops at security check
LinkedIn detected automation. **Solution:** Solve the CAPTCHA manually within 60 seconds.

### "ChromeDriver version mismatch"
Update ChromeDriver to match your Chrome version.

### "GROQ_API_KEY not found"
Ensure `.env` file exists in the project root with your API key.

### Salary showing wrong amount
Check your profile.txt:
- `expected_salary_in_egp` for Egyptian jobs
- `expected_salary_in_usd` for international jobs

### Bot not filling certain fields
Check logs for `[SKIP]` messages. Add the field to your profile.txt if needed.

### "Already applied" but you didn't
The job is in `applied_jobs.json`. Delete that job ID if you want to reapply.

## Ethical Usage Guidelines

**Use Responsibly:**
- Only apply to jobs you're genuinely qualified for
- Review generated answers to ensure accuracy
- Don't spam applications to every job
- Respect LinkedIn's terms of service
- Be prepared to interview for roles you apply to

**Recommended Limits:**
- Max 20-30 applications per day
- Add delays between applications (already implemented)
- Review `applied_jobs.json` regularly

## Limitations

- Only works with "Easy Apply" jobs
- Requires Chrome browser
- Cannot bypass LinkedIn security checks automatically
- Cover letters must be pre-written (resume auto-upload only)
- Some complex custom forms may not be fully supported

## Advanced Customization

### Change AI Model
Edit `GroqAgent.__init__()`:
```python
def __init__(self, model: str = "llama-3.1-70b-versatile"):
    # Available: llama-3.1-70b-versatile, mixtral-8x7b, etc.
```

### Adjust Search Filters
Edit `search_jobs()` method:
```python
search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&f_AL=true&f_E=2,3"
# f_E=2,3 = Mid-Senior level only
# f_WT=2 = Remote only
# Add more filters as needed
```

### Custom Logging
Edit `logging.basicConfig()`:
```python
level=logging.DEBUG  # More detailed logs
level=logging.WARNING  # Only warnings and errors
```

## Support

**Issues:**
- Check `job_agent.log` for detailed error messages
- Ensure all dependencies are installed
- Verify ChromeDriver version matches Chrome

**API Limits:**
- Groq free tier: Check https://console.groq.com for your quota
- LinkedIn rate limits: Space out applications over time

## License

This project is for educational purposes. Use responsibly and in accordance with LinkedIn's Terms of Service.

## Disclaimer

This bot automates job applications but does not guarantee job offers. Always review applications before submission in a production environment. The authors are not responsible for account suspensions or other consequences of automated activity on LinkedIn.

---

**Version:** 2.0  
**Last Updated:** 3 October 2025  
**Author:** Sherif Abdullah
