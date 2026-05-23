# Copy this file to seed_data.py and fill in your own data.
"""
Candidate profile data for the knowledge graph.
Every metric is locked here — never modify values in this file after seeding.
"""

CANDIDATE = {
    "id": "alexjohnson",
    "name": "Alex Johnson",
    "email": "alex@example.com",
    "phone": "+1 555-000-0000",
    "location": "San Francisco, CA",
    "github": "github.com/alexjohnson",
    "linkedin": "linkedin.com/in/alexjohnson",
}

# ─── EDUCATION ────────────────────────────────────────────────────────────────

EDUCATION = [
    {
        "id": "edu_stanford",
        "school": "Stanford University",
        "degree": "Masters",
        "field": "Computer Science",
        "location": "Stanford, CA",
        "start_date": "Sep 2023",
        "end_date": "Jun 2025",
        "gpa": "3.88",
        "gpa_scale": "4.0",
        "courses": [
            "Distributed Systems",
            "Machine Learning",
            "Algorithms",
            "Deep Learning",
            "Database Systems",
            "Cloud Computing",
        ],
        "honors": [
            "Teaching Assistant: Machine Learning (150+ graduate students)",
            "Graduate Research Fellowship",
        ],
    },
    {
        "id": "edu_ucsd",
        "school": "University of California, San Diego",
        "degree": "B.S.",
        "field": "Computer Science",
        "location": "San Diego, CA",
        "start_date": "Sep 2019",
        "end_date": "Jun 2023",
        "gpa": "3.75",
        "gpa_scale": "4.0",
        "courses": [
            "Data Structures & Algorithms",
            "OOP (Java)",
            "Computer Networks",
            "Operating Systems",
            "Linear Algebra",
        ],
        "honors": ["Provost Honors (6 quarters)", "ACM Club Officer"],
    },
]

COURSES = [
    {"id": "course_dist", "name": "Distributed Systems", "school": "Stanford", "keywords": ["distributed systems", "consensus", "replication", "fault tolerance", "raft", "paxos"]},
    {"id": "course_ml", "name": "Machine Learning", "school": "Stanford", "keywords": ["machine learning", "supervised learning", "regression", "classification", "neural networks"]},
    {"id": "course_algo", "name": "Algorithms", "school": "Stanford", "keywords": ["algorithms", "complexity", "dynamic programming", "graphs", "optimization"]},
    {"id": "course_dl", "name": "Deep Learning", "school": "Stanford", "keywords": ["deep learning", "pytorch", "transformers", "cnn", "backpropagation", "fine-tuning"]},
    {"id": "course_db", "name": "Database Systems", "school": "Stanford", "keywords": ["databases", "sql", "query optimization", "transactions", "indexing", "postgresql"]},
    {"id": "course_cloud", "name": "Cloud Computing", "school": "Stanford", "keywords": ["cloud", "aws", "gcp", "kubernetes", "docker", "serverless", "microservices"]},
    {"id": "course_dsa", "name": "Data Structures & Algorithms", "school": "UCSD", "keywords": ["dsa", "sorting", "trees", "heaps", "graphs", "dynamic programming"]},
    {"id": "course_oop", "name": "OOP (Java)", "school": "UCSD", "keywords": ["oop", "java", "design patterns", "inheritance", "polymorphism"]},
    {"id": "course_networks", "name": "Computer Networks", "school": "UCSD", "keywords": ["networking", "tcp/ip", "http", "dns", "protocols", "rest"]},
    {"id": "course_os", "name": "Operating Systems", "school": "UCSD", "keywords": ["os", "concurrency", "threads", "memory management", "linux", "scheduling"]},
]

# ─── EXPERIENCE ───────────────────────────────────────────────────────────────

EXPERIENCES = [
    {
        "id": "exp_stripe",
        "company": "Stripe",
        "title": "Software Engineer Intern",
        "location": "San Francisco, CA",
        "start_date": "May 2024",
        "end_date": "Aug 2024",
        "bullets": [
            "Built a high-throughput event ingestion service in Go processing 50K+ transactions/second, deployed across 12 availability zones with 99.99% uptime; collaborated with payments infra team in two-week sprints",
            "Reduced P99 API latency by 35% through connection pool tuning, query batching, and Redis caching; instrumented with Prometheus and Grafana to surface bottlenecks in production workloads",
            "Delivered 3 full-stack features (Go backend, React dashboard) from design doc through code review to prod rollout within 6 weeks; received strong mid-term and final intern evaluations",
        ],
        "metrics": [
            "50K+ transactions/second",
            "35% P99 latency reduction",
            "99.99% uptime",
            "12 availability zones",
        ],
    },
    {
        "id": "exp_databricks",
        "company": "Databricks",
        "title": "Software Engineer Intern",
        "location": "San Francisco, CA (remote)",
        "start_date": "May 2023",
        "end_date": "Aug 2023",
        "bullets": [
            "Implemented incremental checkpoint pruning for Delta Lake, cutting storage overhead by 28% on customer clusters with 500TB+ data lakes; change shipped to production in the 12.3 LTS release",
            "Wrote end-to-end Spark job performance benchmarks (Python, PySpark) automating regression detection across 8 cluster sizes; reduced manual QA time by 40%",
        ],
        "metrics": [
            "28% storage reduction",
            "500TB+ data lakes",
            "40% QA time savings",
            "8 cluster configurations",
        ],
    },
    {
        "id": "exp_palantir",
        "company": "Palantir Technologies",
        "title": "Forward Deployed Engineer Intern",
        "location": "New York, NY",
        "start_date": "Jan 2023",
        "end_date": "Apr 2023",
        "bullets": [
            "Deployed a Foundry pipeline for a healthcare client processing 3M+ patient records weekly; designed data ontology and built TypeScript/React dashboards used by 200+ analysts",
            "Partnered with client operations and data science teams to translate ambiguous analytical requirements into production-grade data transforms, improving reporting cycle time by 50%",
        ],
        "metrics": [
            "3M+ patient records weekly",
            "200+ analyst users",
            "50% reporting cycle improvement",
        ],
    },
    {
        "id": "exp_startup",
        "company": "Nimbus AI",
        "title": "Software Engineer Intern",
        "location": "San Francisco, CA",
        "start_date": "Jun 2022",
        "end_date": "Aug 2022",
        "bullets": [
            "Shipped 8 product features in a fast-paced seed-stage startup (Python/FastAPI backend, React frontend); drove a 30% increase in user session length as measured by PostHog analytics",
            "Integrated OpenAI API for document summarization, reducing average user review time from 12 minutes to under 2 minutes; designed prompt templates and evaluation harness in Python",
        ],
        "metrics": [
            "8 features delivered",
            "30% session length increase",
            "12 minutes to under 2 minutes",
        ],
    },
]

# ─── METRICS (IMMUTABLE — NEVER CHANGE THESE VALUES) ─────────────────────────

METRICS = [
    # Stanford
    {"id": "m_stanford_gpa", "source": "Stanford", "label": "GPA", "value": "3.88/4.0", "context": "Masters in Computer Science"},
    {"id": "m_stanford_ta", "source": "Stanford", "label": "TA students", "value": "150+", "context": "Machine Learning course"},
    # Stripe
    {"id": "m_stripe_tps", "source": "Stripe", "label": "transactions per second", "value": "50K+", "context": "event ingestion service"},
    {"id": "m_stripe_latency", "source": "Stripe", "label": "P99 latency reduction", "value": "35%", "context": "Redis caching and query batching"},
    {"id": "m_stripe_uptime", "source": "Stripe", "label": "uptime", "value": "99.99%", "context": "payments infrastructure"},
    {"id": "m_stripe_az", "source": "Stripe", "label": "availability zones", "value": "12", "context": "multi-region deployment"},
    # Databricks
    {"id": "m_db_storage", "source": "Databricks", "label": "storage reduction", "value": "28%", "context": "Delta Lake checkpoint pruning"},
    {"id": "m_db_datalake", "source": "Databricks", "label": "data lake size", "value": "500TB+", "context": "customer clusters"},
    {"id": "m_db_qa", "source": "Databricks", "label": "QA time savings", "value": "40%", "context": "automated Spark benchmarks"},
    # Palantir
    {"id": "m_pal_records", "source": "Palantir", "label": "patient records processed weekly", "value": "3M+", "context": "Foundry healthcare pipeline"},
    {"id": "m_pal_users", "source": "Palantir", "label": "analyst users", "value": "200+", "context": "TypeScript/React dashboards"},
    {"id": "m_pal_cycle", "source": "Palantir", "label": "reporting cycle improvement", "value": "50%", "context": "data ontology redesign"},
    # Nimbus AI
    {"id": "m_nimbus_features", "source": "Nimbus AI", "label": "features delivered", "value": "8", "context": "seed-stage startup"},
    {"id": "m_nimbus_session", "source": "Nimbus AI", "label": "session length increase", "value": "30%", "context": "React/Python product"},
    {"id": "m_nimbus_review", "source": "Nimbus AI", "label": "document review time", "value": "12 min to under 2 min", "context": "OpenAI-powered summarization"},
    # ClearRoute
    {"id": "m_cr_accuracy", "source": "ClearRoute", "label": "ETA prediction accuracy", "value": "92%", "context": "LSTM traffic forecasting"},
    {"id": "m_cr_routes", "source": "ClearRoute", "label": "daily route computations", "value": "1.2M+", "context": "real-time routing engine"},
    # LangGraph Agent
    {"id": "m_lg_agents", "source": "LangGraph Agent", "label": "concurrent agents", "value": "64", "context": "multi-agent orchestration"},
    {"id": "m_lg_latency", "source": "LangGraph Agent", "label": "tool call latency", "value": "sub-200ms", "context": "cached RAG retrieval"},
    # VectorSearch
    {"id": "m_vs_qps", "source": "VectorSearch", "label": "queries per second", "value": "10K+", "context": "HNSW index with FAISS"},
    {"id": "m_vs_recall", "source": "VectorSearch", "label": "recall@10", "value": "97.4%", "context": "1M-vector benchmark"},
    # DataLens
    {"id": "m_dl_datasets", "source": "DataLens", "label": "datasets integrated", "value": "12", "context": "ETL pipeline"},
    {"id": "m_dl_records", "source": "DataLens", "label": "records processed", "value": "5M+", "context": "PostgreSQL data warehouse"},
]

# ─── PROJECTS ─────────────────────────────────────────────────────────────────

PROJECTS = [
    {
        "id": "proj_clearroute",
        "name": "ClearRoute",
        "description": "Real-time traffic routing engine with LSTM-based ETA prediction achieving 92% accuracy, processing 1.2M+ route computations daily with sub-100ms response time",
        "tech": ["Python", "FastAPI", "React", "TypeScript", "PostgreSQL", "Redis", "Docker", "AWS", "TensorFlow"],
        "metrics": ["m_cr_accuracy", "m_cr_routes"],
        "github": "github.com/alexjohnson/clearroute",
        "category": "Full-Stack / ML",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_langgraph_agent",
        "name": "LangGraph Multi-Agent Orchestrator",
        "description": "Multi-agent LLM orchestration framework with 64 concurrent agents, cached RAG retrieval at sub-200ms tool-call latency; used for automated code review and documentation generation",
        "tech": ["Python", "LangGraph", "LangChain", "FastAPI", "PostgreSQL", "Redis", "OpenAI API", "FAISS", "Docker"],
        "metrics": ["m_lg_agents", "m_lg_latency"],
        "github": "github.com/alexjohnson/langgraph-orchestrator",
        "category": "AI/LLM",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_vectorsearch",
        "name": "VectorSearch",
        "description": "High-performance approximate nearest-neighbor search service backed by FAISS HNSW index, achieving 97.4% recall@10 at 10K+ QPS on a 1M-vector benchmark",
        "tech": ["Python", "FAISS", "FastAPI", "gRPC", "Docker", "Kubernetes", "NumPy", "Go"],
        "metrics": ["m_vs_qps", "m_vs_recall"],
        "github": "github.com/alexjohnson/vectorsearch",
        "category": "Backend / ML Infra",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_datalens",
        "name": "DataLens",
        "description": "ETL platform integrating 12 public data sources into a PostgreSQL warehouse, processing 5M+ records with automated schema inference, incremental loads, and D3.js dashboards",
        "tech": ["Python", "PostgreSQL", "Airflow", "D3.js", "Node.js", "Docker", "AWS S3", "pandas"],
        "metrics": ["m_dl_datasets", "m_dl_records"],
        "github": "github.com/alexjohnson/datalens",
        "category": "Data Engineering",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_transformer_scratch",
        "name": "Transformer from Scratch",
        "description": "Full GPT-2-style transformer implementation in PyTorch with FlashAttention, trained on WikiText-103; includes tokenizer, training loop, and perplexity evaluation harness",
        "tech": ["Python", "PyTorch", "CUDA", "NumPy", "Hugging Face Datasets"],
        "metrics": [],
        "github": "github.com/alexjohnson/transformer-scratch",
        "category": "Machine Learning",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_distributed_kv",
        "name": "Distributed KV Store",
        "description": "Linearizable key-value store implementing Raft consensus from scratch in Go; supports leader election, log replication, snapshotting, and linearizable reads under network partition",
        "tech": ["Go", "gRPC", "Raft", "Docker", "Prometheus"],
        "metrics": [],
        "github": "github.com/alexjohnson/distributed-kv",
        "category": "Distributed Systems",
        "loc": 0,
        "commits": 0,
    },
    {
        "id": "proj_codebuddy",
        "name": "CodeBuddy",
        "description": "VS Code extension + FastAPI backend providing AI-powered code review using GPT-4o; streams inline suggestions as diagnostics; 400+ installs on the VS Code Marketplace",
        "tech": ["TypeScript", "Python", "FastAPI", "OpenAI API", "VS Code Extension API", "WebSockets"],
        "metrics": [],
        "github": "github.com/alexjohnson/codebuddy",
        "category": "Developer Tools",
        "loc": 0,
        "commits": 120,
    },
    {
        "id": "proj_portfolio",
        "name": "alexjohnson.dev",
        "description": "Personal portfolio and blog built with Next.js, TailwindCSS, and MDX; deployed on Vercel with CI/CD",
        "tech": ["Next.js", "TypeScript", "TailwindCSS", "MDX", "Vercel"],
        "metrics": [],
        "github": "github.com/alexjohnson/alexjohnson.dev",
        "category": "Full-Stack Web",
        "loc": 12500,
        "commits": 0,
    },
]

# ─── SKILLS ───────────────────────────────────────────────────────────────────

SKILLS = [
    # Programming Languages
    {"id": "sk_python", "name": "Python", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_go", "name": "Go", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_java", "name": "Java", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_ts", "name": "TypeScript", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_js", "name": "JavaScript", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_cpp", "name": "C++", "category": "Programming Languages", "proficiency": "familiar"},
    {"id": "sk_rust", "name": "Rust", "category": "Programming Languages", "proficiency": "familiar"},
    {"id": "sk_sql", "name": "SQL", "category": "Programming Languages", "proficiency": "proficient"},
    {"id": "sk_shell", "name": "Shell Scripting", "category": "Programming Languages", "proficiency": "familiar"},
    # Web Development
    {"id": "sk_react", "name": "React", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_nextjs", "name": "Next.js", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_nodejs", "name": "Node.js", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_fastapi", "name": "FastAPI", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_grpc", "name": "gRPC", "category": "Web Development", "proficiency": "familiar"},
    {"id": "sk_restapi", "name": "RESTful APIs", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_tailwind", "name": "TailwindCSS", "category": "Web Development", "proficiency": "proficient"},
    {"id": "sk_fullstack", "name": "Full-Stack Development", "category": "Web Development", "proficiency": "proficient"},
    # Backend & Databases
    {"id": "sk_postgresql", "name": "PostgreSQL", "category": "Backend & Databases", "proficiency": "proficient"},
    {"id": "sk_mysql", "name": "MySQL", "category": "Backend & Databases", "proficiency": "familiar"},
    {"id": "sk_redis", "name": "Redis", "category": "Backend & Databases", "proficiency": "proficient"},
    {"id": "sk_sqlite", "name": "SQLite", "category": "Backend & Databases", "proficiency": "proficient"},
    {"id": "sk_db_design", "name": "Database Design", "category": "Backend & Databases", "proficiency": "proficient"},
    {"id": "sk_microservices", "name": "Microservices", "category": "Backend & Databases", "proficiency": "proficient"},
    # Developer Tools
    {"id": "sk_git", "name": "Git", "category": "Developer Tools", "proficiency": "proficient"},
    {"id": "sk_docker", "name": "Docker", "category": "Developer Tools", "proficiency": "proficient"},
    {"id": "sk_cicd", "name": "CI/CD Pipelines", "category": "Developer Tools", "proficiency": "proficient"},
    {"id": "sk_agile", "name": "Agile Development", "category": "Developer Tools", "proficiency": "proficient"},
    {"id": "sk_prometheus", "name": "Prometheus", "category": "Developer Tools", "proficiency": "familiar"},
    {"id": "sk_grafana", "name": "Grafana", "category": "Developer Tools", "proficiency": "familiar"},
    # Software Engineering
    {"id": "sk_dsa", "name": "Data Structures & Algorithms", "category": "Software Engineering", "proficiency": "proficient"},
    {"id": "sk_oop", "name": "Object-Oriented Programming", "category": "Software Engineering", "proficiency": "proficient"},
    {"id": "sk_design_patterns", "name": "Design Patterns", "category": "Software Engineering", "proficiency": "proficient"},
    {"id": "sk_distributed", "name": "Distributed Systems", "category": "Software Engineering", "proficiency": "proficient"},
    {"id": "sk_tdd", "name": "Test-Driven Development", "category": "Software Engineering", "proficiency": "familiar"},
    # Cloud & DevOps
    {"id": "sk_aws", "name": "AWS", "category": "Cloud & DevOps", "proficiency": "proficient"},
    {"id": "sk_gcp", "name": "GCP", "category": "Cloud & DevOps", "proficiency": "familiar"},
    {"id": "sk_kubernetes", "name": "Kubernetes", "category": "Cloud & DevOps", "proficiency": "proficient"},
    {"id": "sk_ec2", "name": "AWS EC2", "category": "Cloud & DevOps", "proficiency": "proficient"},
    {"id": "sk_s3", "name": "AWS S3", "category": "Cloud & DevOps", "proficiency": "proficient"},
    {"id": "sk_lambda", "name": "AWS Lambda", "category": "Cloud & DevOps", "proficiency": "familiar"},
    # Machine Learning & AI
    {"id": "sk_pytorch", "name": "PyTorch", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_tensorflow", "name": "TensorFlow", "category": "Machine Learning", "proficiency": "familiar"},
    {"id": "sk_sklearn", "name": "scikit-learn", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_numpy", "name": "NumPy", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_pandas", "name": "pandas", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_transformers", "name": "Transformers", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_langchain", "name": "LangChain", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_langgraph", "name": "LangGraph", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_rag", "name": "RAG", "category": "Machine Learning", "proficiency": "proficient"},
    {"id": "sk_faiss", "name": "FAISS", "category": "Machine Learning", "proficiency": "proficient"},
    # LLM / AI Frontier
    {"id": "sk_openai", "name": "OpenAI API", "category": "AI/LLM", "proficiency": "proficient"},
    {"id": "sk_prompt_eng", "name": "Prompt Engineering", "category": "AI/LLM", "proficiency": "proficient"},
    {"id": "sk_llm_general", "name": "Large Language Models", "category": "AI/LLM", "proficiency": "proficient"},
    {"id": "sk_finetuning", "name": "Fine-tuning", "category": "AI/LLM", "proficiency": "familiar"},
    # Communication
    {"id": "sk_collab", "name": "Team Collaboration", "category": "Communication & Collaboration", "proficiency": "proficient"},
    {"id": "sk_cross_func", "name": "Cross-Functional Communication", "category": "Communication & Collaboration", "proficiency": "proficient"},
    {"id": "sk_mentorship", "name": "Mentorship", "category": "Communication & Collaboration", "proficiency": "familiar"},
]

# ─── ROLE TYPES ───────────────────────────────────────────────────────────────

ROLE_TYPES = [
    {
        "id": "role_fullstack",
        "name": "Full-Stack SWE",
        "description": "Full-stack software engineer with React/TypeScript frontend and Python/Go/Node.js backend",
        "stripe_title": "Software Engineer Intern",
        "databricks_title": "Software Engineer Intern",
        "skills_order": [
            "Programming Languages",
            "Web Development",
            "Backend & Databases",
            "Developer Tools",
            "Software Engineering",
            "Cloud & DevOps",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_clearroute", "proj_codebuddy", "proj_datalens", "proj_portfolio"],
        "emphasis": [
            "React/TypeScript frontend",
            "Python/Go backend",
            "RESTful APIs",
            "End-to-end features",
            "Full-stack development",
        ],
    },
    {
        "id": "role_backend",
        "name": "Backend SWE",
        "description": "Backend engineer focused on scalable architecture, APIs, and databases",
        "stripe_title": "Software Engineer Intern",
        "databricks_title": "Software Engineer Intern",
        "skills_order": [
            "Programming Languages",
            "Backend & Databases",
            "Software Engineering",
            "Cloud & DevOps",
            "Developer Tools",
            "Web Development",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_distributed_kv", "proj_vectorsearch", "proj_clearroute"],
        "emphasis": [
            "Python/Go backend",
            "Scalable architecture",
            "Distributed systems",
            "High-throughput APIs",
            "Microservices",
        ],
    },
    {
        "id": "role_ml",
        "name": "ML Engineer",
        "description": "Machine learning engineer focused on model training, deployment, and production pipelines",
        "stripe_title": "Machine Learning Engineer Intern",
        "databricks_title": "Data Engineer Intern",
        "skills_order": [
            "Machine Learning",
            "Programming Languages",
            "Cloud & DevOps",
            "Software Engineering",
            "Developer Tools",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_clearroute", "proj_transformer_scratch", "proj_vectorsearch"],
        "emphasis": [
            "Model training/deployment",
            "PyTorch/TensorFlow",
            "Production ML pipelines",
            "Evaluation harnesses",
            "92% LSTM prediction accuracy",
        ],
    },
    {
        "id": "role_ai_llm",
        "name": "AI/LLM Engineer",
        "description": "AI engineer focused on LLM integration, RAG pipelines, and agent orchestration",
        "stripe_title": "AI Research Engineer Intern",
        "databricks_title": "Data Engineer Intern",
        "skills_order": [
            "AI/LLM",
            "Machine Learning",
            "Programming Languages",
            "Software Engineering",
            "Cloud & DevOps",
            "Developer Tools",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_langgraph_agent", "proj_codebuddy", "proj_transformer_scratch"],
        "emphasis": [
            "Multi-agent orchestration (LangGraph)",
            "RAG pipelines",
            "OpenAI/Anthropic API integration",
            "Prompt engineering",
            "Sub-200ms tool-call latency",
        ],
    },
    {
        "id": "role_data",
        "name": "Data Engineer",
        "description": "Data engineer focused on ETL pipelines, large-scale data processing, and SQL optimization",
        "stripe_title": "Data Engineer Intern",
        "databricks_title": "Data Engineer Intern",
        "skills_order": [
            "Programming Languages",
            "Backend & Databases",
            "Machine Learning",
            "Cloud & DevOps",
            "Software Engineering",
            "Developer Tools",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_datalens", "proj_clearroute"],
        "emphasis": [
            "ETL pipelines",
            "5M+ record processing",
            "PostgreSQL/SQL optimization",
            "28% storage reduction at Databricks",
            "Airflow orchestration",
        ],
    },
    {
        "id": "role_devops",
        "name": "DevOps/SRE",
        "description": "DevOps/SRE focused on Docker, Kubernetes, CI/CD, and production infrastructure",
        "stripe_title": "Software Engineer Intern",
        "databricks_title": "Software Engineer Intern",
        "skills_order": [
            "Cloud & DevOps",
            "Developer Tools",
            "Backend & Databases",
            "Programming Languages",
            "Software Engineering",
            "Web Development",
            "Communication & Collaboration",
        ],
        "project_priority": ["proj_distributed_kv", "proj_vectorsearch", "proj_datalens"],
        "emphasis": [
            "Docker/Kubernetes",
            "CI/CD pipelines",
            "99.99% uptime across 12 AZs",
            "AWS deployment",
            "Prometheus/Grafana observability",
        ],
    },
]

# ─── KEYWORDS BY ROLE ─────────────────────────────────────────────────────────

KEYWORDS = [
    # Full-Stack
    {"id": "kw_fs_react", "term": "React", "role_type": "role_fullstack", "priority": "HIGH"},
    {"id": "kw_fs_ts", "term": "TypeScript", "role_type": "role_fullstack", "priority": "HIGH"},
    {"id": "kw_fs_nodejs", "term": "Node.js", "role_type": "role_fullstack", "priority": "HIGH"},
    {"id": "kw_fs_restapi", "term": "RESTful APIs", "role_type": "role_fullstack", "priority": "HIGH"},
    {"id": "kw_fs_fullstack", "term": "Full-Stack", "role_type": "role_fullstack", "priority": "HIGH"},
    {"id": "kw_fs_pg", "term": "PostgreSQL", "role_type": "role_fullstack", "priority": "MEDIUM"},
    {"id": "kw_fs_docker", "term": "Docker", "role_type": "role_fullstack", "priority": "MEDIUM"},
    {"id": "kw_fs_agile", "term": "Agile", "role_type": "role_fullstack", "priority": "LOW"},
    # Backend
    {"id": "kw_be_python", "term": "Python", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_go", "term": "Go", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_java", "term": "Java", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_scalable", "term": "Scalable Architecture", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_microservices", "term": "Microservices", "role_type": "role_backend", "priority": "MEDIUM"},
    {"id": "kw_be_pg", "term": "PostgreSQL", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_redis", "term": "Redis", "role_type": "role_backend", "priority": "HIGH"},
    {"id": "kw_be_dist", "term": "Distributed Systems", "role_type": "role_backend", "priority": "HIGH"},
    # ML
    {"id": "kw_ml_pytorch", "term": "PyTorch", "role_type": "role_ml", "priority": "HIGH"},
    {"id": "kw_ml_tf", "term": "TensorFlow", "role_type": "role_ml", "priority": "HIGH"},
    {"id": "kw_ml_sklearn", "term": "scikit-learn", "role_type": "role_ml", "priority": "HIGH"},
    {"id": "kw_ml_mlops", "term": "MLOps", "role_type": "role_ml", "priority": "MEDIUM"},
    {"id": "kw_ml_deploy", "term": "Model Deployment", "role_type": "role_ml", "priority": "HIGH"},
    # AI/LLM
    {"id": "kw_llm_rag", "term": "RAG", "role_type": "role_ai_llm", "priority": "HIGH"},
    {"id": "kw_llm_transformers", "term": "Transformers", "role_type": "role_ai_llm", "priority": "HIGH"},
    {"id": "kw_llm_langchain", "term": "LangChain", "role_type": "role_ai_llm", "priority": "HIGH"},
    {"id": "kw_llm_langgraph", "term": "LangGraph", "role_type": "role_ai_llm", "priority": "HIGH"},
    {"id": "kw_llm_finetune", "term": "Fine-tuning", "role_type": "role_ai_llm", "priority": "MEDIUM"},
    {"id": "kw_llm_prompt", "term": "Prompt Engineering", "role_type": "role_ai_llm", "priority": "HIGH"},
    {"id": "kw_llm_agents", "term": "Agent Orchestration", "role_type": "role_ai_llm", "priority": "HIGH"},
    # Data
    {"id": "kw_de_etl", "term": "ETL", "role_type": "role_data", "priority": "HIGH"},
    {"id": "kw_de_pipeline", "term": "Data Pipelines", "role_type": "role_data", "priority": "HIGH"},
    {"id": "kw_de_sql", "term": "SQL", "role_type": "role_data", "priority": "HIGH"},
    {"id": "kw_de_spark", "term": "Apache Spark", "role_type": "role_data", "priority": "MEDIUM"},
    {"id": "kw_de_airflow", "term": "Airflow", "role_type": "role_data", "priority": "MEDIUM"},
    # DevOps
    {"id": "kw_do_docker", "term": "Docker", "role_type": "role_devops", "priority": "HIGH"},
    {"id": "kw_do_k8s", "term": "Kubernetes", "role_type": "role_devops", "priority": "HIGH"},
    {"id": "kw_do_cicd", "term": "CI/CD", "role_type": "role_devops", "priority": "HIGH"},
    {"id": "kw_do_aws", "term": "AWS", "role_type": "role_devops", "priority": "HIGH"},
    {"id": "kw_do_infra", "term": "Infrastructure as Code", "role_type": "role_devops", "priority": "MEDIUM"},
    {"id": "kw_do_obs", "term": "Observability", "role_type": "role_devops", "priority": "MEDIUM"},
]

# Maps project IDs to which metric IDs they carry
PROJECT_METRICS_MAP = {
    "proj_clearroute": ["m_cr_accuracy", "m_cr_routes"],
    "proj_langgraph_agent": ["m_lg_agents", "m_lg_latency"],
    "proj_vectorsearch": ["m_vs_qps", "m_vs_recall"],
    "proj_datalens": ["m_dl_datasets", "m_dl_records"],
}

EXPERIENCE_METRICS_MAP = {
    "exp_stripe": ["m_stripe_tps", "m_stripe_latency", "m_stripe_uptime", "m_stripe_az"],
    "exp_databricks": ["m_db_storage", "m_db_datalake", "m_db_qa"],
    "exp_palantir": ["m_pal_records", "m_pal_users", "m_pal_cycle"],
    "exp_startup": ["m_nimbus_features", "m_nimbus_session", "m_nimbus_review"],
}

# Skills used in each experience
EXPERIENCE_SKILLS_MAP = {
    "exp_stripe": ["sk_go", "sk_python", "sk_react", "sk_ts", "sk_redis", "sk_postgresql", "sk_docker", "sk_agile", "sk_prometheus"],
    "exp_databricks": ["sk_python", "sk_sql", "sk_postgresql", "sk_aws", "sk_docker"],
    "exp_palantir": ["sk_ts", "sk_react", "sk_python", "sk_sql", "sk_postgresql"],
    "exp_startup": ["sk_python", "sk_fastapi", "sk_react", "sk_ts", "sk_openai", "sk_prompt_eng"],
}

# Skills used in each project
PROJECT_SKILLS_MAP = {
    "proj_clearroute": ["sk_python", "sk_fastapi", "sk_react", "sk_ts", "sk_postgresql", "sk_redis", "sk_docker", "sk_aws", "sk_tensorflow"],
    "proj_langgraph_agent": ["sk_python", "sk_langchain", "sk_langgraph", "sk_fastapi", "sk_postgresql", "sk_redis", "sk_openai", "sk_faiss", "sk_rag", "sk_docker"],
    "proj_vectorsearch": ["sk_python", "sk_faiss", "sk_fastapi", "sk_grpc", "sk_docker", "sk_kubernetes", "sk_numpy", "sk_go"],
    "proj_datalens": ["sk_python", "sk_postgresql", "sk_nodejs", "sk_docker", "sk_s3", "sk_pandas"],
    "proj_transformer_scratch": ["sk_pytorch", "sk_numpy", "sk_transformers"],
    "proj_distributed_kv": ["sk_go", "sk_grpc", "sk_docker", "sk_prometheus"],
    "proj_codebuddy": ["sk_ts", "sk_python", "sk_fastapi", "sk_openai"],
    "proj_portfolio": ["sk_nextjs", "sk_ts", "sk_tailwind", "sk_nodejs"],
}
