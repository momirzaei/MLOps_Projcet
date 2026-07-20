# Medallion SQL Agent - End-to-End MLOps Pipeline

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking-blue.svg)](https://mlflow.org/)
[![DVC](https://img.shields.io/badge/DVC-Data_Versioning-orange.svg)](https://dvc.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF.svg)](https://github.com/features/actions)

---

# Project Overview

This project implements an intelligent **LLM-powered SQL Agent** capable of translating natural language questions into SQL queries and executing them on a **Medallion Architecture** database.

Beyond the AI component, the repository demonstrates a complete **End-to-End MLOps workflow**, including:

- LLM-powered SQL generation
- Data Version Control (DVC)
- Experiment Tracking with MLflow
- Automated Evaluation
- Continuous Integration (GitHub Actions)
- Docker-based deployment
- Streamlit web interface

---

# Architecture & Tech Stack

- **LLM:** Llama-3-70B-Versatile (Groq API)
- **Framework:** LangChain
- **Database:** SQLite (Medallion Architecture)
- **Experiment Tracking:** MLflow
- **Data Versioning:** DVC + DagsHub
- **Containerization:** Docker
- **CI/CD:** GitHub Actions
- **Frontend:** Streamlit

---

# Project Structure

```text
MLOps_Project
│
├── .dvc/                      # DVC configuration
├── .github/workflows/         # GitHub Actions pipelines
├── .env.example               # Environment variables template
├── .gitignore
├── Dockerfile
├── golden_set.json            # Benchmark dataset
├── main.py                    # Streamlit application
├── mlflow_evaluator.py        # MLflow evaluation script
├── requirements.txt
├── retail_gold.db.dvc         # DVC pointer
└── sql_agent.py               # LangChain SQL Agent
```

---

# Features

- Natural Language → SQL using Llama-3
- Automatic SQL execution
- Prompt evaluation using MLflow
- Data versioning with DVC
- Remote storage using DagsHub
- Dockerized deployment
- Streamlit interface
- Automated CI/CD pipeline

---

# Getting Started

## 1. Clone the Repository

```bash
git clone https://github.com/momirzaei/MLOps_Projcet.git

cd MLOps_Projcet
```

---

## 2. Configure Environment Variables

Create a `.env` file in the project root.

```text
GROQ_API_KEY=your_groq_api_key
MLFLOW_TRACKING_URI=your_dagshub_mlflow_uri
```

---

## 3. Download the Dataset

Authenticate DVC with DagsHub and pull the database.

```bash
dvc pull
```

---

## 4. Run with Docker

```bash
docker build -t medallion-sql-agent .

docker run -p 8000:8000 --env-file .env medallion-sql-agent
```

---

## 5. Run Streamlit

```bash
streamlit run main.py
```

---

# MLflow Evaluation

The evaluation script executes the benchmark contained in `golden_set.json` and records:

- SQL execution accuracy
- Response latency
- Token usage
- Estimated API cost
- Prompt version
- Dataset version

Run manually:

```bash
python mlflow_evaluator.py
```

---

# Continuous Integration (GitHub Actions)

Every push to the repository automatically triggers the CI pipeline.

The workflow performs the following steps:

1. Install project dependencies
2. Pull the required dataset using DVC
3. Execute the MLflow evaluation script
4. Log evaluation metrics
5. Build the Docker image if all tests pass

This ensures that every new commit is automatically validated before deployment.

---

# MLflow Dashboard

All evaluation runs generated locally or through GitHub Actions are automatically logged to the remote MLflow server hosted on DagsHub.

View all experiment runs, metrics, parameters and comparisons here:

**https://dagshub.com/MahdiAGS/MLOps_DVC_Storage.mlflow/#/**

---

# CI/CD Workflow

```text
Developer Push
       │
       ▼
GitHub Actions
       │
       ├── Install Dependencies
       ├── DVC Pull
       ├── MLflow Evaluation
       ├── Log Metrics
       └── Docker Build
               │
               ▼
      DagsHub MLflow Tracking
```

---

# Technologies Used

| Component | Technology |
|------------|------------|
| LLM | Llama-3-70B-Versatile |
| Framework | LangChain |
| Database | SQLite |
| Data Versioning | DVC |
| Remote Storage | DagsHub |
| Experiment Tracking | MLflow |
| CI/CD | GitHub Actions |
| Containerization | Docker |
| UI | Streamlit |

---

# License

This project is intended for educational and research purposes.