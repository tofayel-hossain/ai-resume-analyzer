import re
from collections import OrderedDict

from core.text_utils import normalize_token


SKILL_ALIASES = {
    "Python": ["python"],
    "Java": ["java"],
    "C": [" c ", "c programming"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "c sharp"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "PHP": ["php"],
    "Ruby": ["ruby"],
    "Go": ["golang", " go "],
    "Rust": ["rust"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "R": [" r programming", " r language"],
    "MATLAB": ["matlab"],
    "SQL": ["sql"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "reactjs", "react.js"],
    "Next.js": ["next.js", "nextjs"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular"],
    "Svelte": ["svelte"],
    "Node.js": ["node.js", "nodejs"],
    "Express.js": ["express.js", "expressjs", "express"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Spring Boot": ["spring boot"],
    ".NET": [".net", "asp.net", "dotnet"],
    "Laravel": ["laravel"],
    "Ruby on Rails": ["ruby on rails", "rails"],
    "REST API": ["rest api", "restful api", "restful services"],
    "GraphQL": ["graphql"],
    "Microservices": ["microservices", "micro services"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "SQLite": ["sqlite"],
    "MongoDB": ["mongodb", "mongo db"],
    "Redis": ["redis"],
    "Oracle": ["oracle database", "oracle db"],
    "Microsoft SQL Server": ["sql server", "mssql"],
    "Firebase": ["firebase"],
    "Supabase": ["supabase"],
    "Elasticsearch": ["elasticsearch", "elastic search"],
    "DynamoDB": ["dynamodb"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["microsoft azure", "azure"],
    "Google Cloud": ["gcp", "google cloud", "google cloud platform"],
    "Docker": ["docker", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "Linux": ["linux", "ubuntu"],
    "Nginx": ["nginx"],
    "Apache": ["apache http server", "apache server"],
    "Git": ["git"],
    "GitHub": ["github"],
    "GitLab": ["gitlab"],
    "Jira": ["jira"],
    "Agile": ["agile"],
    "Scrum": ["scrum"],
    "DevOps": ["devops"],
    "MLOps": ["mlops"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "Natural Language Processing": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision", "cv"],
    "Generative AI": ["generative ai", "genai", "gen ai"],
    "Large Language Models": ["large language model", "large language models", "llm", "llms"],
    "RAG": ["retrieval augmented generation", "rag"],
    "Prompt Engineering": ["prompt engineering"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "Keras": ["keras"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "SciPy": ["scipy"],
    "Matplotlib": ["matplotlib"],
    "OpenCV": ["opencv"],
    "Hugging Face": ["hugging face", "huggingface"],
    "Transformers": ["transformers", "bert"],
    "Sentence Transformers": ["sentence transformers", "sentence-transformers", "sbert"],
    "FAISS": ["faiss"],
    "pgvector": ["pgvector"],
    "LangChain": ["langchain"],
    "LlamaIndex": ["llamaindex", "llama index"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Science": ["data science"],
    "Data Engineering": ["data engineering"],
    "ETL": ["etl", "extract transform load"],
    "Apache Spark": ["apache spark", "spark"],
    "Hadoop": ["hadoop"],
    "Kafka": ["kafka", "apache kafka"],
    "Airflow": ["airflow", "apache airflow"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Excel": ["microsoft excel", "excel"],
    "Statistics": ["statistics", "statistical analysis"],
    "A/B Testing": ["a/b testing", "ab testing"],
    "Figma": ["figma"],
    "UI/UX": ["ui/ux", "user interface", "user experience"],
    "Responsive Design": ["responsive design", "mobile-first", "mobile first"],
    "Selenium": ["selenium"],
    "Playwright": ["playwright"],
    "Pytest": ["pytest"],
    "Jest": ["jest"],
    "Cypress": ["cypress"],
    "Unit Testing": ["unit testing", "unit tests"],
    "API Testing": ["api testing"],
    "Postman": ["postman"],
    "OAuth": ["oauth", "oauth2"],
    "JWT": ["jwt", "json web token"],
    "Cybersecurity": ["cybersecurity", "cyber security"],
    "OWASP": ["owasp"],
    "Networking": ["networking", "computer networks"],
    "TCP/IP": ["tcp/ip"],
    "Embedded Systems": ["embedded systems", "embedded system"],
    "Arduino": ["arduino"],
    "Raspberry Pi": ["raspberry pi"],
    "IoT": ["iot", "internet of things"],
    "Leadership": ["leadership", "team lead", "led a team"],
    "Project Management": ["project management", "project manager"],
    "Communication": ["communication", "communication skills"],
    "Problem Solving": ["problem solving", "problem-solving"],
}


BOUNDARY_ALIASES = {
    "c", "r", "go", "sql", "js", "ts", "ml", "dl", "aws", "gcp",
    "jwt", "etl", "rag", "iot", "git", "php", "cv", "nlp", "llm", "llms"
}


def _contains_alias(normalized_text: str, alias: str) -> bool:
    alias = normalize_token(alias).strip()
    if not alias:
        return False
    if alias in BOUNDARY_ALIASES:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized_text))
    return alias in normalized_text


def extract_skills(text: str) -> list[str]:
    padded = f" {normalize_token(text)} "
    found = OrderedDict()
    for canonical, aliases in SKILL_ALIASES.items():
        if any(_contains_alias(padded, alias) for alias in aliases):
            found[canonical] = True
    return list(found.keys())


def match_skills(resume_text: str, jd_text: str) -> dict:
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    resume_set = set(resume_skills)
    jd_set = set(jd_skills)

    matched = sorted(jd_set & resume_set)
    missing = sorted(jd_set - resume_set)

    if jd_skills:
        score = round((len(matched) / len(jd_skills)) * 100, 1)
    else:
        score = None

    return {
        "resume_skills": resume_skills,
        "jd_skills": jd_skills,
        "matched": matched,
        "missing": missing,
        "score": score,
    }
