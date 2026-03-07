### Placyx – Placement Management Portal

Placyx is a web-based placement management system designed to streamline the campus recruitment process by connecting students, companies, and administrators on a single platform.

The application automates the placement workflow from company registration and job posting to student applications, candidate selection, and placement tracking.

The system is implemented using Flask, SQLAlchemy, and SQLite, with a responsive interface built using Bootstrap and Jinja2 templates.
---
## Key Features
Role-Based Access System

The platform supports three different user roles:

# Administrator

- Approve or reject company registrations
- Approve or reject job posts
- View all placement drives
- View all student applications
- Search students and companies
- Deactivate or reactivate accounts
- Monitor placement statistics

# Company
- Register company account
- Post placement drives
- View job applicants
- View candidate profiles
- Shortlist or reject applicants
- Select final candidates
- Close placement drives
- Update company profile and logo

# Student
- Register and create profile
- Upload resume and profile photo
- Browse available placement drives
- View job details and company information
- Apply for placement drives
- Track application status
---
##  Placement Workflow

The application models the real campus recruitment lifecycle:

Company Registration
-→ Admin Approval
-→ Company Posts Job
-→ Admin Approves Job Post
-→ Students View and Apply
-→ Company Shortlists Candidates
-→ Company Selects Candidate
-→ Student Marked as Placed
-→ Placement Drive Closed

---

## Project Structure
```bash

Placement-App/
│
├── placyx/
│ ├── templates/
│ │ └── layouts/
| │ │ └── base_dashboard.html
│ │ ├── admin_all_jobs.html
│ │ ├── admin_applications.html
│ │ ├── admin_company_approval.html
│ │ ├── admin_dashboard.html
│ │ ├── admin_job_approval.html
│ │ ├── admin_manage_companies.html
│ │ ├── admin_manage_students.html
│ │ ├── admin_placements.html
│ │ ├── company_candidate_details.html
│ │ ├── company_create_job.html
│ │ ├── company_dashboard.html
│ │ ├── company_jobs.html
│ │ ├── company_profile.html
│ │ ├── company_view_applicants.html
│ │ ├── index.html
│ │ ├── login.html
│ │ ├── register_company.html
│ │ ├── register_student.html
│ │ ├── student_applications.html
│ │ ├── student_job_details.html
│ │ └── student_profile.html
│ │
│ ├── static/
│ │ └── uploads/
│ │
│ ├── instance/
│ │ └── placyx.db
│ ├── app.py
│ ├── models.py
│ ├── config.py
│ ├── local.ps1
│ ├── requirements.txt
│ └──  venv/
│
└──README.md

```
---

# Technologies Used


| Technology    | Purpose                                   |
|---------------|-------------------------------------------|
| Flask         | Backend web framework                     |
| SQLAlchemy    | ORM for database management               |
| SQLite        | Lightweight relational database           |
| Flask-Login   | Authentication and session management     |
| Jinja2        | Dynamic HTML templating                   |
| Bootstrap 5   | Responsive UI design                      |
| Chart.js      | Dashboard analytics visualization         |
| Werkzeug      | Password hashing and file upload handling |
| HTML / CSS    | Frontend layout and styling               |

---

# Database Overview

The system database contains the following main tables:

- **Users** – Stores authentication credentials and roles  
- **Students** – Contains academic and personal details of students  
- **Companies** – Stores company information and approval status  
- **JobPosts** – Represents placement drives created by companies  
- **Applications** – Tracks student applications and selection status  
- **College** – Represents the institution managing placements  

Relationships include:

- One-to-Many → Companies → JobPosts  
- One-to-Many → Students → Applications  
- One-to-Many → JobPosts → Applications  

---

# Installation and Setup

## 1. Clone the Repository

```bash
git clone https://github.com/24f2003142/Placement-App.git
cd Placement-App/placyx
./local.psi
```

- These commands will launch create venv download necessary dependencies create database and launch the web application

