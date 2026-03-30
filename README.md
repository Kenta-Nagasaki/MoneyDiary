# MoneyDiary

## Overview

MoneyDiary is a household budgeting web application designed not only to record daily income and expenses, but also to **visualize spending patterns, budget overruns, and savings trends to support better financial decisions**.

While existing budgeting apps often provide solid recording features, I felt that they still make it difficult to consistently understand:

- how much I have spent compared to my budget,
- what categories I am overspending on,
- and how much I am actually saving as a result.

To address this, I designed this app to combine **ease of continuous use through calendar-based input** with **category-based analysis, budget management, and cumulative savings visualization**, so that users can complete the entire cycle from recording to reflection within a single application.

---

## URL

The deployed application is available here:

**Demo:** https://moneydiary.onrender.com/

### Test Account
- Username: `test`
- Password: `test1234`

---

## Main Features

### 1. Calendar-based income and expense input
Users can click a date and record income or expenses for that day.  
Instead of using a simple list format, I adopted a calendar-based interface to make daily records easier to view and manage.

### 2. Category-based analysis
Income and expenses are aggregated by category and visualized with graphs.  
This makes it easier to get an overview of where money is being spent and to notice spending imbalances.

### 3. Subcategory analysis
Categories can be broken down into more detailed subcategories.  
For example, users can look beyond “Food” and understand its detailed breakdown, making it easier to identify specific areas for improvement.

### 4. Budget management
Users can set both a monthly overall budget and category-specific budgets.  
By checking progress, remaining budget, and overspending, the app encourages budget-conscious behavior rather than stopping at simple record-keeping.

### 5. Savings trend visualization
Instead of showing only monthly income and expenses, the app displays the **cumulative trend of “income − expenses.”**  
This makes it easier to understand whether overall savings are increasing or decreasing over time.

---

## Problem This App Aims to Solve

I believe budgeting often ends with simply entering numbers, and many users stop there.  
However, what really matters is not the act of recording itself, but **reflecting on spending habits and changing future behavior based on that reflection**.

With this in mind, I designed the app around the following flow:

**Record → Visualize → Notice → Improve**

Rather than being just an expense tracker, this app is intended to **provide useful insights for improving personal financial habits**.

---

## Design Considerations

### 1. Input UI designed for continued use
For an app used on a daily basis, I believed it was important to balance rich functionality with ease of input.  
For that reason, I centered the input experience around a calendar interface and prioritized intuitive usability.

### 2. A structure that connects recording and analysis
If recording and analysis are separated too much, reviewing financial habits becomes cumbersome.  
In this app, recorded data flows directly into analysis and budget tracking, making regular reflection easier.

### 3. Showing savings as a cumulative trend instead of monthly snapshots
I felt that looking only at monthly surplus or deficit makes it hard to understand whether money is increasing or decreasing overall.  
To solve this, savings are displayed as a **cumulative trend** rather than as isolated monthly results.

### 4. Minimum security measures for a publicly accessible app
I implemented the following security measures:

- Password hashing
- CSRF protection
- Login attempt limiting
- Security headers
- Session management

One of the key points of this app is that it was built not just to “work,” but with **deployment to a public environment in mind**.

---

## Tech Stack

### Frontend
- HTML
- CSS
- JavaScript
- Chart.js
- FullCalendar

### Backend
- Python
- Flask
- SQLAlchemy

### Database
- PostgreSQL (production)
- SQLite (local development)

*The database connection is switched depending on the environment using `DATABASE_URL`.*

### Infrastructure
- Render

---

## Technical Highlights

### 1. Data management with an ORM
By using SQLAlchemy, I was able to handle user data, transaction data, and budget data consistently in Python.  
I aimed for a structure that is easy to improve and extend later.

### 2. Deployment in a form that others can actually use
Instead of keeping the project limited to a local environment, I deployed it on Render so that **other people can actually access and use it**.

---

## Database Design

- `users`: user information
- `transactions`: income and expense data
- `budgets`: budget data
- `login_attempts`: login attempt records

---

## Screen Flow / How to Use

1. Click any date on the calendar screen  
2. Enter income or expense data  
3. Check category-based spending on the graph screen  
4. View the cumulative savings trend in the savings tab  
5. Check budgets and usage status on the analysis screen  

---

 ## Setup

```bash
git clone https://github.com/Kenta-Nagasaki/MoneyDiary.git
cd MoneyDiary

python -m venv venv
