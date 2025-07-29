# Deals App

A Flask‑based web app for generating and sending personalized emails to startup CEOs using the Ollama LLM and the Gmail API.

## Features

- Upload a CSV of deals and founder info  
- Generate tailored emails via Ollama (Llama 3.2)  
- Persist generated emails in `generated_emails.csv`  
- Send emails through Gmail API (OAuth 2.0 Desktop flow)  
- Batch “Generate All” with progress logging  
- Status badges (Pass, Generated, Sent, Error) & instant client‑side filter  

## Prerequisites

- **Python 3.8+**  
- **Ollama CLI**: install from https://ollama.com/docs/installation  
- **Google Cloud**: enable Gmail API, create an **OAuth 2.0 Desktop** client  

## Installation

```bash
git clone https://github.com/ChaseLin218/DealGmailIntegration2.0
cd <repo-folder>

python3 -m venv venv
# Unix/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt

export FLASK_APP=main.py       # Unix/macOS
set FLASK_APP=main.py          # Windows
flask run

go to http://127.0.0.1:5000/