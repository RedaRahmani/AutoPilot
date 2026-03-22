# AutoPilot

**AutoPilot** is an AI-powered workflow automation platform designed to automate repetitive, document-centric, and communication-centric business tasks.

It ingests inputs from multiple channels such as uploaded files, emails, scheduled jobs, and later webhook events, then processes them through an AI pipeline:

**parse → OCR (if needed) → classify → extract structured data → validate → persist → route for review**

The platform exposes the full workflow through an admin dashboard where users can monitor runs, inspect extracted results, and review low-confidence cases.

---

## Why AutoPilot?

Many businesses still process documents and requests manually:

- reading supplier emails and copying invoice data into spreadsheets or ERP systems
- reviewing uploaded expense reports by hand
- classifying incoming requests and routing them to the right team
- manually checking low-quality or incomplete extracted data

AutoPilot is built to reduce that friction by combining:

- AI-powered extraction
- OCR for scanned files
- structured workflow execution
- human-in-the-loop review
- dashboard visibility into every run

---

## Project Goal

The goal of AutoPilot is to become a production-style internal automation system that demonstrates:

- **AI engineering**
- **backend engineering**
- **full-stack development**
- **workflow automation**
- **document intelligence**
- **production-minded architecture**

This project is also meant to be a strong portfolio piece for roles such as:

- AI Engineer
- Full-Stack AI Engineer
- Backend Engineer
- ML Platform Engineer
- Workflow Automation Engineer

---

## MVP Goal

The MVP answers one core question:

> **Can a user upload a file, have it processed by an AI pipeline in the background, and see the structured result in a dashboard?**

### MVP features

- User authentication
- File upload (PDF, PNG, JPEG)
- Background processing worker
- OCR for scanned documents/images
- LLM-based structured extraction
- Result persistence in PostgreSQL
- Confidence-based review queue
- Admin dashboard with run history and status
- Basic logging

---

## What is intentionally postponed?

To keep the first version focused and buildable, these features are postponed:

- Email ingestion
- Multiple user roles / RBAC
- Workflow builder UI
- Multiple LLM providers
- Webhook triggers
- Advanced ML classifiers
- Real-time websocket updates
- Multi-tenancy
- Full audit trail UI
- Complex Celery-based distributed setup from day one

---

## High-Level Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   React Admin UI                                                │
│   - Dashboard                                                   │
│   - Run List                                                    │
│   - Run Detail                                                  │
│   - Review Queue                                                │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTPS REST API
┌────────────────────▼────────────────────────────────────────────┐
│                         API LAYER                               │
│   FastAPI                                                       │
│   - Auth endpoints                                              │
│   - Upload endpoint                                             │
│   - Workflow run endpoints                                      │
│   - Review queue endpoints                                      │
│   - Dashboard metrics endpoints                                 │
└────────┬───────────────────────────────────┬────────────────────┘
         │ DB reads/writes                   │ Enqueue processing job
┌────────▼──────────┐              ┌─────────▼────────────────────┐
│   PostgreSQL       │              │   Queue / Worker Layer       │
│   - users          │              │   Redis + worker system      │
│   - documents      │              │   (RQ / ARQ first, Celery    │
│   - workflow_runs  │              │    possible later)           │
│   - extraction     │              └─────────┬────────────────────┘
│   - review_queue   │                        │
│   - logs/events    │                        │
└───────────────────┘              ┌─────────▼────────────────────┐
         ▲                         │    Document Processing        │
         │                         │    Pipeline                   │
         │                         │    1. File detection          │
         │                         │    2. Text extraction         │
         │                         │    3. OCR if needed          │
         │                         │    4. Classification         │
         │                         │    5. Structured extraction  │
         │                         │    6. Validation             │
         │                         │    7. Confidence scoring     │
         │                         │    8. Persistence / routing  │
         │                         └──────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│                        FILE STORAGE                             │
│   Local storage for MVP                                         │
│   S3 / MinIO later                                              │
└─────────────────────────────────────────────────────────────────┘