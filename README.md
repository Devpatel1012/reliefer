# Reliefer 🚀
> **AI-Powered Resume Personalization & ATS Optimization Platform**

Reliefer is an intelligent, full-stack web application designed to help job seekers tailor their resumes for specific job roles using state-of-the-art Large Language Models (LLMs). Reliefer parses existing resumes (PDF/DOCX/TXT), extracts key candidate data into a structured profile, matches candidate qualifications against job descriptions, and generates beautifully formatted, ATS-compliant resumes ready for instant PDF export.

---

## ✨ Key Features

- 🤖 **AI Resume Personalization**: Leverages Hugging Face Inference APIs (Llama 3.3 70B, Qwen 2.5 72B, etc.) to tailor candidate summary, experience bullets, and skills specifically for target job postings.
- 📄 **Smart Resume Parsing**: Automatically extracts candidate contact information, work experience, projects, skills, education, and achievements from uploaded PDF/DOCX files or pasted raw text.
- 🎯 **ATS Optimization**: Structures generated resumes with clean heading hierarchies, bullet point alignment, and keyword integration to maximize Applicant Tracking System (ATS) match scores.
- 🎨 **Print-Friendly Web Viewer**: Provides an interactive, high-contrast visual resume preview alongside a raw Markdown view.
- 📥 **Multi-Format Export**: One-click download of tailored resumes as vector-rendered PDFs, plain text (`.txt`), or Markdown (`.md`).
- 🔐 **Robust Authentication & Security**: JWT bearer token authentication, bcrypt password hashing, CORS protection, and complete user-data isolation.
- 🛡️ **Intelligent LLM Fallbacks**: Features automatic model discovery and structured fallback mechanisms to ensure 100% uptime even during external API rate limits or quota constraints.

---

## 🛠️ Technology Stack

### **Backend**
- **Framework**: Python 3.11+ / FastAPI
- **Database**: SQLite (Development) / PostgreSQL (Production) via SQLAlchemy ORM
- **Security**: PyJWT, passlib (bcrypt), OAuth2 Password Bearer
- **PDF Generation & Parsing**: ReportLab (vector PDF renderer), `pdfplumber`, `pypdf`, `python-docx`
- **AI Integration**: Hugging Face Inference API / Chat Completions API (`requests`)
- **Testing**: Pytest, FastAPI TestClient

### **Frontend**
- **Interface**: HTML5, Vanilla JavaScript (ES6+), CSS3 with CSS Variables & Modern Aesthetics
- **Icons**: Lucide Icons
- **Design System**: Responsive glassmorphism cards, high-contrast dark/light document preview sheet

### **DevOps & Infrastructure**
- **Containerization**: Docker & Docker Compose
- **Deployment Configs**: Railway (`railway.json`), Render (`render.yaml`)

---

## 📁 Project Architecture

```
relexer/
├── backend/
│   ├── main.py                  # FastAPI application entry point & CORS configuration
│   ├── database.py              # SQLAlchemy database session & engine setup
│   ├── models.py                # Database models (User, Skill, Project, Experience, Education, etc.)
│   ├── schemas.py               # Pydantic data schemas & request/response validation
│   ├── security.py              # JWT token generation, password hashing & auth dependencies
│   ├── resume_ai.py             # LLM orchestration, model fallback router & ReportLab PDF renderer
│   ├── resume_formatter.py      # Structural post-processor & Markdown section normalizer
│   ├── scraper.py               # Resume text extractor (PDF/DOCX) & HTML scraper
│   ├── routers/
│   │   ├── auth_router.py       # Signup, Login, Profile endpoints (/me)
│   │   ├── profile_router.py    # CRUD endpoints for skills, experience, projects, education
│   │   └── resume_router.py     # Resume upload, AI generation, and PDF/TXT/MD export
│   ├── tests/                   # Comprehensive backend test suite (Pytest)
│   └── requirements.txt         # Python dependencies
├── Frontend/
│   └── User_Signup/
│       ├── dashboard.html       # Main user dashboard & AI Resume Builder UI
│       ├── dashboard.css        # Dashboard styles & high-contrast document viewer CSS
│       ├── dashboard.js         # Async API interactions, modal handling & state management
│       ├── index.html           # Landing page & authentication UI
│       ├── style.css            # Base design system & auth styling
│       └── script.js            # Auth tab switcher & form handlers
├── scripts/
│   └── generate_prod_secrets.py # Production secret key generator
├── docker-compose.yml           # Multi-container orchestration
├── Dockerfile                   # Production Docker build container
└── README.md                    # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- **Python**: 3.11 or higher
- **Git**
- **Hugging Face Token** *(Optional for AI generation; structured fallback mode is available automatically)*

---

### 1. Clone the Repository
```bash
git clone https://github.com/Devpatel1012/reliefer.git
cd reliefer
```

### 2. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file inside the `backend/` directory:
```env
SECRET_KEY=your_super_secret_jwt_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./reliefer.db
HUGGINGFACE_API_KEY=your_huggingface_token_here
```

### 5. Run the Backend Server
```bash
cd backend
python3 -m uvicorn main:app --reload --port 8000
```
The API server will run at: `http://localhost:8000`  
Swagger API Docs will be available at: `http://localhost:8000/docs`

### 6. Open Frontend
Open `Frontend/User_Signup/index.html` in your web browser, or serve it using any static file server:
```bash
python3 -m http.server 3000 --directory Frontend/User_Signup
```
Then visit `http://localhost:3000` in your browser.

---

## 🐳 Docker Deployment

Run the entire application in a containerized environment using Docker Compose:

```bash
docker-compose up --build
```
The app will be accessible at `http://localhost:8000`.

---

## 🧪 Running Tests

Reliefer includes an extensive automated test suite covering authentication, profile management, resume parsing, and AI generation:

```bash
cd backend
pytest
```

---

## 📡 API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/auth/signup` | Register a new user account |
| `POST` | `/auth/token` | User login & JWT token issuance |
| `GET` | `/me` | Get current authenticated user details |
| `POST` | `/resume/upload` | Upload & parse existing resume (PDF/DOCX/TXT) |
| `POST` | `/resume/paste` | Parse raw pasted resume text |
| `POST` | `/resume/generate` | Generate personalized ATS resume using AI |
| `GET` | `/resume/{id}/export-pdf` | Export tailored resume as vector-rendered PDF |
| `GET` | `/resume/{id}/export-txt` | Export tailored resume as plain text |
| `GET` | `/resume/{id}/export-md` | Export tailored resume as Markdown |

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!  
Feel free to check out the [Issues Page](https://github.com/Devpatel1012/reliefer/issues).

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Built with ❤️ by [Dev Patel](https://github.com/Devpatel1012)**
