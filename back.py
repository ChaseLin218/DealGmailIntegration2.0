import csv
import re
import sys
import os
import base64
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

# Initialize the Ollama model
model = OllamaLLM(model="llama3.2")

# Full LLM prompt template
template = """
You are an AI assistant for David, investment director at EnvisionX Capital. We are a venture capital firm empowering founders to scale their businesses through expert operational support and a global network of resources. Design an email for us to send to {ceo}, the CEO of the startup named {dealname}({orgweb}), which will be referred to as the startup. The email should consist of 5 subparagraphs as below and write the email more like a real human instead of ai chatbot:
1. Begin by congratulating the startup on its recent achievements or milestones to show we are aware of its progress and interested in its success. Search on the internet to find one most relevant and important achievement or milestone with specific details. If there are not public news about this startup within 3 months, use the recent linkedin post by the founder. The email title should be direct about our interest in investing and be related to this with some keywords. Link the source just as reference. Keep this paragraph short and concise and do not use fundraising information.
2. Based on the information provided on the startup’s website, clearly state our genuine interest in their business and growth trajectory. Highlight what specifically impresses us about the startup.
3. Provide a brief introduction about EnvisionX Capital, as an early growth stage vc focus on AI, and enterprise SaaS. We normally invest from Seed to Series B. Starting in Oct 2023, we have invested in StreamNative, ScienceIO(acq. by Veradigm), Subtle Medical, etc. We not only provide capital but also offer operational guidance to all entrepreneurs to scale go-to-market strategy and operational efficiency. Can add more info from our website https://www.envisionxcapital.com/
4. Briefly mention that besides the capital, and operational guidance, we are also well-connected in the industry, such as top-tier VCs (e.g. a16z)
5. Close the email by expressing our interest in further discussion about the startup’s latest progress as well as staying in touch for potential future fundraising when the startup starts its next round of financing.
Overall keep it to the point by omit all of long and general sentences and keep the overall length below 250 words. At the end, provide my name David, title as investment director, company name as EnvisionX Capital. Attach my linkedin profile link(https://www.linkedin.com/in/david-wang-866a9a82/) and Calendly account(https://calendly.com/davidwang-envisionxcapital) at the end.

Write only the email without describing the content or using citations.

Note: Compare the web results with the startup description and use only relevant details that match the description.

Important note: PLEASE USE CRUNCHBASE URL AS THE MAIN SOURCE OF INFORMATION FOR THE STARTUP. IF CRUNCHBASE URL IS NOT PROVIDED, USE THE OFFICIAL WEBSITE INSTEAD. MAKE SURE TO CROSSCHECK OTHER DATA WITH THESE TWO FIRST BEFORE USING THEM!!!!

"""

description_instr = " The below is a short summary/description of the startup: "

searchaddon_instr = """
The below are raw search snippets from the web. Clean the company name by stripping any 'Seed Round -' or 'Preseed Round -' prefixes before searching. Provide all results to the language model along with the CSV description; it should compare each snippet against the description and include only those details that directly match. Use the Crunchbase summary and official website context preferentially.
"""

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def send_email_via_gmail(to_addr: str, subject: str, body: str) -> dict:
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)

    msg = MIMEText(body)
    msg['to'] = to_addr
    msg['subject'] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(userId='me', body={'raw': raw}).execute()

def get_crunchbase_summary(cb_url: str) -> str:
    try:
        resp = requests.get(cb_url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"name":"description"})
        if meta and meta.get("content"):
            return meta["content"].strip()
    except Exception as e:
        print(f"Warning: Crunchbase fetch failed: {e}", file=sys.stderr, flush=True)
    return ""

def get_search_snippet(query: str, num_results: int = 5) -> str:
    headers = {"User-Agent":"Mozilla/5.0"}
    snippets = []
    try:
        resp = requests.get("https://www.bing.com/search", params={"q":query}, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, "html.parser")
        hits = soup.find_all("li", {"class":"b_algo"})[:num_results]
        for h in hits:
            p = h.find("p")
            if p and p.get_text(strip=True):
                snippets.append(p.get_text(strip=True))
    except Exception as e:
        print(f"Warning: Search fetch failed: {e}", file=sys.stderr, flush=True)
    return "\n".join(snippets)

def get_field(row: dict, norm2orig: dict, *candidates: str) -> str:
    # Try exact normalized header matches first
    for cand in candidates:
        key = cand.strip().lower()
        if key in norm2orig:
            return row.get(norm2orig[key], "").strip()
    # Fallback: partial match on normalized header
    for cand in candidates:
        sub = cand.strip().lower()
        for norm, orig in norm2orig.items():
            if sub in norm:
                return row.get(orig, "").strip()
    return ""

def csv_search_generate(targetdeal: str, targetcsv: str) -> str:
    dealname = ceo_name = ceo_email = orgweb = description = crunch_url = ""
    with open(targetcsv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        print("DEBUG: CSV headers:", headers, file=sys.stderr, flush=True)
        norm2orig = {h.strip().lower(): h for h in headers}

        for row in reader:
            raw = get_field(row, norm2orig, "Transaction Name", "Deal Name", "Name")
            if raw.lower() == targetdeal.lower():
                dealname = re.sub(r'(?i)^(Seed Round|Preseed Round)\s*-\s*', "", raw).strip()
                email_raw = get_field(row, norm2orig, "Email", "CEO Email", "Contact")
                parts = [p.strip() for p in email_raw.split(",", 1)]
                ceo_name  = parts[0] if parts else ""
                ceo_email = parts[1] if len(parts) > 1 else ""
                orgweb      = get_field(row, norm2orig, "Organization Website", "Website", "URL")
                crunch_url  = get_field(row, norm2orig, "Transaction Name URL", "Crunchbase URL")
                description = get_field(row, norm2orig, "Organization Description", "Description")
                break

    print(f"DEBUG: Parsed — dealname='{dealname}', ceo_name='{ceo_name}', ceo_email='{ceo_email}', orgweb='{orgweb}'", file=sys.stderr, flush=True)

    if not dealname or not ceo_name or not orgweb:
        raise ValueError(f"Missing required fields for deal '{targetdeal}': dealname='{dealname}', ceo_name='{ceo_name}', orgweb='{orgweb}'")

    cb_summary  = get_crunchbase_summary(crunch_url)
    search_q    = dealname + (f" site:{orgweb}" if orgweb else "")
    search_snip = get_search_snippet(search_q)

    full_prompt = (
        template
      + description_instr + description + "\n"
      + (cb_summary + "\n" if cb_summary else "")
      + searchaddon_instr + search_snip
    )

    print("\n\n\n\n cb_summary:", cb_summary, file=sys.stderr, flush=True)
    print("\n\n\n")

    prompt = ChatPromptTemplate.from_template(full_prompt)
    chain  = prompt | model
    return chain.invoke({
        "ceo":      ceo_name,
        "dealname": dealname,
        "orgweb":   orgweb
    })