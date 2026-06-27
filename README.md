# fraud-inference-service
Real-time transaction fraud evaluation using FastAPI and LangGraph multi-agent orchestration.
# Real-Time Agentic Fraud Inference Service

An intelligent, production-ready fraud detection engine containerized with **FastAPI** and orchestrated using a three-agent state machine mesh via **LangGraph**.

## 🛠️ System Architecture & Stack

* **API Framework:** FastAPI (Asynchronous high-performance payload parsing)
* **Orchestration Engine:** LangGraph (State machine managing multi-agent forensic coordination)
* **Agent 1 (Feature Investigator):** Simulates fetching context-driven behavioral markers.
* **Agent 2 (Risk Scorer):** Renders structured risk analysis and automated decisions.
* **Agent 3 (Compliance Auditor):** Compiles and generates official diagnostic audit strings.
* **Testing & CI/CD:** Containerized integration test sweeps executed via `pytest` and `httpx`.
* **Deployment:** Dockerized for cloud-agnostic microservice scalability.

## 🚀 Running the Automated Test Suite

To validate the multi-agent mesh and API endpoints seamlessly within the isolated Linux runtime environment, run the containerized test suite:

```bash
# Build the service container image
docker build -t fraud-service .

# Run the automated verification test loops
docker run --rm fraud-service python -m pytest tests/
