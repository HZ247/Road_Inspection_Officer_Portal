# FVO Portal — Field Verification Officer System

A lightweight web app for government field officers to record site attendance,
conduct road inspections with live camera + GPS, verify materials on-site —
and for admins to review and approve all submissions.

Built with **Python + Flask + SQLite + plain HTML/JS**. No build tools, no frameworks.

---

## What it does

| Role | Can do |
|---|---|
| **Field Officer** | GPS check-in/out · Road inspection with live camera + GPS trail · Material & equipment quantity verification |
| **Admin** | View live stats · Review inspections with GPS map + photos · Review material checks · Approve or flag submissions |

---

## Tech Stack

- **Backend** — Python 3, Flask, SQLite
- **Frontend** — Plain HTML, CSS, Vanilla JS
- **Auth** — JWT (PyJWT) + bcrypt
- **Maps** — Leaflet.js (CDN, no install)

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/HZ247/Road_Inspection_Officer_Portal.git
```

### 2. Install dependencies

```bash
pip install flask flask-cors pyjwt bcrypt
```

### 3. Run

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

On first run the database is created automatically and seeded with:
- Default admin account
- 4 dummy contracts with material items

---

## Default Login

| Role | Employee ID | Password |
|---|---|---|
| Admin | `ADMIN001` | `admin123` |
| Officer | FVO123 | OFFICER123 |

---

## Project Structure

```
fvo-app/
├── app.py                  # Flask entry point
├── server/
│   ├── database.py         # SQLite setup + seed data
│   ├── auth_middleware.py  # JWT auth decorator
│   ├── uploads/            # Inspection photos saved here
│   └── routes/
│       ├── auth.py
│       ├── attendance.py
│       ├── inspection.py
│       ├── material.py
│       └── admin.py
└── client/
    ├── login.html
    ├── register.html
    ├── otp.html
    ├── fvo/                # Officer pages
    └── admin/              # Admin pages
```

---

## Notes

- Camera and GPS require browser permission when prompted
- OTP verification is mocked — any 6-digit number is accepted
- SQLite is file-based; for multi-device use, host the server on a shared network machine and point all devices to its IP
- Camera (`getUserMedia`) requires HTTPS in production; for local network testing in Chrome go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
