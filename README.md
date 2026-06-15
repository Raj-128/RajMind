# Enterprise AI Knowledge Assistant

A multi-tenant SaaS platform that lets organizations create workspaces, upload documents, and query their knowledge base using AI-powered semantic search with source citations.

## Overview

Employees waste time searching scattered company knowledge — policies, SOPs, technical docs, past project files. This platform centralizes that knowledge and provides AI-powered question answering with citations back to source documents.

## Features

- JWT-based authentication with custom user model
- Multi-tenant workspaces with role-based access control (Owner, Admin, Member, Viewer)
- Document upload and processing (PDF, DOCX, TXT)
- RAG (Retrieval-Augmented Generation) pipeline: text extraction, chunking, vector embeddings
- AI-powered chat with source citations using Google Gemini
- Conversation history and multi-turn context
- Usage analytics dashboard (search volume, response times, active users)
- Background document processing via Celery + Redis
- Fully containerized with Docker Compose

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django, Django REST Framework |
| Database | PostgreSQL |
| Cache / Queue | Redis |
| Background Tasks | Celery |
| Vector Database | ChromaDB |
| AI / Embeddings | Google Gemini (gemini-2.5-flash, gemini-embedding-001) |
| Auth | JWT (SimpleJWT) |
| Containerization | Docker, Docker Compose |

## Architecture

```
Client (Postman / Frontend)
        |
        v
Django REST API (web)
        |
   -----------------------------------
   |          |          |           |
   v          v          v           v
PostgreSQL  Redis     ChromaDB    Celery Worker
(database)  (broker)  (vectors)   (background tasks)
                                       |
                                       v
                                  Google Gemini API
```

## Setup

### Prerequisites
- Docker Desktop
- A Google Gemini API key (get one at https://aistudio.google.com/app/apikey)

### Steps

1. Clone the repository:
```
git clone <your-repo-url>
cd enterprise-ai-knowledge-assistant
```

2. Copy `.env.example` to `.env` and fill in your values:
```
cp .env.example .env
```

3. Build and start all services:
```
docker-compose up --build
```

4. In a new terminal, run migrations and create a superuser:
```
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

5. The API is now available at `http://localhost:8000/`
   - Admin panel: `http://localhost:8000/admin/`

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register/` | POST | Register a new user |
| `/api/auth/login/` | POST | Login, returns JWT tokens |
| `/api/workspaces/` | GET/POST | List or create workspaces |
| `/api/workspaces/{id}/members/add/` | POST | Add member to workspace |
| `/api/workspaces/{id}/documents/` | GET/POST | List or upload documents |
| `/api/workspaces/{id}/chat/ask/` | POST | Ask a question (RAG) |
| `/api/workspaces/{id}/analytics/dashboard/` | GET | Usage analytics |

## Project Status

Core platform complete: authentication, multi-tenant workspaces with RBAC, document ingestion pipeline, vector search with semantic retrieval, AI-powered chat with citations, usage analytics, and background task processing — all containerized and verified end-to-end.