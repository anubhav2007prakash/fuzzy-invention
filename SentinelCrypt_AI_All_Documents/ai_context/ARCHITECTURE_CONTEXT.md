# Architecture Context
Approved dependency direction: React -> FastAPI -> Services -> ML/XAI/Crypto -> Repositories -> Database. API routes must not contain business logic, ML algorithms, crypto primitives, or raw persistence logic. Keep the MVP modular but not microservice-based.
