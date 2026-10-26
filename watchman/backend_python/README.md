# 🛡️ CampusGuard — Enterprise Python Backend

> Enterprise-grade layered FastAPI architecture following the software engineering guidelines of top tech MNCs (Amazon, Qualcomm, Google, Uber).

---

## 🏛️ Architecture Overview

The system uses **Clean Layered Architecture** with strict Separation of Concerns (SoC) and Inversion of Control (IoC):

```
backend_python/
├── app/
│   ├── api/                     # 🌐 API Routing Layer (FastAPI Controllers)
│   │   ├── v1/
│   │   │   ├── endpoints/       # Domain routers (auth, gate, visitors, etc.)
│   │   │   └── api.py           # V1 Router aggregator
│   ├── core/                    # ⚙️ Core Cross-Cutting Concerns
│   │   ├── config.py            # Pydantic Settings singleton (.env loader)
│   │   ├── dependencies.py      # FastAPI Dependency Injection (Auth, Roles)
│   │   ├── exceptions.py        # Centralized HTTP & Business Exceptions
│   │   └── security.py          # JWT generation/decoding & BCrypt hashing
│   ├── db/                      # 💾 Database Infrastructure
│   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   ├── init_db.py           # Auto-DDL & initial demo seed data
│   │   └── session.py           # Unit of Work / Engine & Session lifecycle
│   ├── models/                  # 📦 Domain Entity Models (SQLAlchemy ORM)
│   │   ├── emergency_alert.py
│   │   ├── gate_log.py
│   │   ├── handover_task.py
│   │   ├── out_pass.py
│   │   ├── parcel_log.py
│   │   ├── shift_handover.py
│   │   ├── student.py
│   │   ├── user.py
│   │   └── visitor_pass.py
│   ├── repositories/            # 🗄️ Data Access Layer (Repository Pattern)
│   │   ├── base_repository.py   # Generic CRUD BaseRepository[T]
│   │   ├── gate_repository.py
│   │   ├── handover_repository.py
│   │   ├── student_repository.py
│   │   ├── user_repository.py
│   │   └── visitor_repository.py
│   ├── schemas/                 # 📋 DTOs / Serialization (Pydantic v2)
│   │   ├── auth.py
│   │   ├── emergency.py
│   │   ├── gate.py
│   │   ├── handover.py
│   │   ├── out_pass.py
│   │   ├── parcel.py
│   │   └── visitor.py
│   ├── services/                # 🧠 Business Logic Layer (Service Pattern)
│   │   ├── auth_service.py
│   │   ├── emergency_service.py
│   │   ├── gate_service.py
│   │   ├── handover_service.py
│   │   ├── parcel_service.py
│   │   ├── student_service.py
│   │   └── visitor_service.py
│   └── main.py                  # 🚀 Application Factory & Lifespan
├── tests/                       # 🧪 Automated Test Suite (Pytest)
│   ├── conftest.py              # TestClient fixtures
│   ├── test_auth.py
│   └── test_health.py
├── .env.example                 # Environment configuration template
├── .gitignore                   # Enterprise gitignore
├── Dockerfile                   # Multi-stage production container
├── docker-compose.yml           # Local dev orchestrator with PostgreSQL
├── pyproject.toml               # Modern Python project configuration
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Linting, testing, and dev tools
└── run.py                       # Application execution entry point
```

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example if .env does not exist:
copy .env.example .env
```

### 3. Run Application
```bash
python run.py
```
Or with Uvicorn:
```bash
uvicorn app.main:app --reload --port 8080
```

### 4. Interactive Documentation
- **Swagger UI**: [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
- **ReDoc**: [http://localhost:8080/api/redoc](http://localhost:8080/api/redoc)
- **Health Check**: [http://localhost:8080/health](http://localhost:8080/health)

---

## 🏭 Design Patterns Applied

| Pattern | Where Used | Benefit |
|---------|------------|---------|
| **Layered Architecture** | `api/` → `services/` → `repositories/` → `db/` | Decouples business logic from HTTP and DB |
| **Generic Repository** | `BaseRepository[T]` | Eliminates boilerplate CRUD logic across all entities |
| **Dependency Injection** | `Depends(get_db)`, `Depends(get_current_user)` | Testable, pluggable authentication & sessions |
| **Application Factory** | `create_application()` in `main.py` | Clean testing and multi-environment configuration |
| **Data Transfer Objects** | Pydantic v2 in `schemas/` | Type-safety, automated validation & OpenAPI schema |
