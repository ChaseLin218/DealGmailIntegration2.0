# Setup
git clone <repo-url>
cd your‑app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ollama
# 1) Install the Ollama CLI: https://ollama.com/docs/installation
# 2) Pull your model: `ollama pull llama3.2`
# 3) Start the server: `ollama serve`

# Gmail API
# Place credentials.json in this folder (OAuth “Desktop app”)
# The first time you click Send you’ll get a browser prompt.

# Run
export FLASK_APP=main.py
flask run