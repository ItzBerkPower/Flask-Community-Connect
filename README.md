# Community Connect

Community Connect is a web application designed to streamline the connection between volunteers and organisations. The platform allows volunteers to discover events that match their skills, while organisations can manage events and recruit volunteers effectively.

---

## Table of Contents
- [Features](#features)
- [Project Overview](#project-overview)
- [Database Models](#database-models)
- [Installation](#installation)
- [Usage](#usage)
- [Data Population](#data-population)
- [Security & Privacy](#security--privacy)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Features
- User authentication for volunteers and organisations
- Volunteers can create profiles, list skills, and join events
- Organisations can create and manage events
- Skill-based matching between volunteers and events
- Event requests with approval workflow
- Filtering options for volunteers and organisations
- Data integrity, input validation, and flash messaging for errors

---

## Project Overview
Community Connect solves the problem of connecting motivated volunteers with organisations in need of their skills. The system addresses challenges such as:
- Difficulty in finding volunteers or events
- Lack of transparency in volunteer-event matching
- Managing event capacities and volunteer requests efficiently

The application is built using **Python Flask**, **SQLite3**, **HTML/CSS/Bootstrap**, and **Jinja2 templating**.

---

## Database Models
The application uses a relational database with the following main tables:
- **user**: Stores login credentials and roles (volunteer or organisation)
- **volunteer**: Stores volunteer details (name, DOB, skills)
- **organisation**: Stores organisation details (name, description, contact)
- **event**: Stores event details, including max volunteers
- **skill**: List of available skills
- **volunteer_skill**: Junction table linking volunteers and skills
- **event_skill**: Junction table linking events and required skills
- **volunteer_event**: Junction table tracking confirmed volunteers for events
- **event_request**: Tracks volunteer requests to join events with statuses (pending/accepted/declined)

---

## Installation
1. Clone this repository:
```bash
git clone https://github.com/yourusername/community-connect.git
cd community-connect
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Initialise the database
```bash
python init_db.py
```

## Data Population
The database is pre-populated with sample data including:

- 5+ volunteers with different skills
- 5+ organisations
- 5+ events linked to organisations
- Skill assignments for both volunteers and events

This allows immediate testing of filtering and matching functionality.

## Security & Privacy
Authentication & Access Control: Volunteers and organisations have role-specific access

- **Input Validation:** Prevents duplicate accounts and invalid data
- **Data Protection:** Personal information is hashed (passwords) and access is restricted
- **Backups:** Regular backups recommended for organisational data
- **Compliance:** Designed in line with Australian Privacy Principles (APP5, APP10, APP11, APP12)
- **Ethical Considerations:** Data is collected and used responsibly, minimising exposure of personal information, respecting consent, and ensuring fairness.

## Future Improvements
- Add more advanced skill-based matching algorithms
- Implement email notifications for event requests and approvals
- Improve UI/UX design for better responsiveness
- Support multiple languages and internationalisation
- Include analytics dashboard for organisations

# Licence
This project is licensed under the MIT License. See LICENSE file for details.