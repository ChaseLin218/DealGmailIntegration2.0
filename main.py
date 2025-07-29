from website import create_app
from back import csv_search_generate, send_email_via_gmail
from flask import (
    render_template, request, redirect,
    url_for, flash, send_from_directory, jsonify
)
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SubmitField
from werkzeug.utils import secure_filename
import os, csv, datetime

app = create_app()

# --- Paths ---
BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, app.config['UPLOAD_FOLDER'])
MEMO_CSV   = os.path.join(BASE_DIR, "generated_emails.csv")

# ---------- Persistence helpers ----------
def load_generated_emails():
    """
    Returns:
      dict: { dealname: { 'subject':..., 'body':..., 'filename':..., 'updated_at':..., 'status': ... } }
    """
    data = {}
    if not os.path.exists(MEMO_CSV):
        return data
    with open(MEMO_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            data[r['dealname']] = {
                'subject':    r.get('subject', ''),
                'body':       r.get('body', ''),
                'filename':   r.get('filename', ''),
                'updated_at': r.get('updated_at', ''),
                'status':     r.get('status', 'generated')  # default
            }
    return data

def save_generated_email(dealname, subject, body, filename, status="generated"):
    exists = os.path.exists(MEMO_CSV)
    fieldnames = ['dealname', 'subject', 'body', 'filename', 'updated_at', 'status']
    rows = []
    if exists:
        with open(MEMO_CSV, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if r['dealname'] != dealname]

    rows.append({
        'dealname': dealname,
        'subject': subject,
        'body': body,
        'filename': filename,
        'updated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'status': status
    })

    with open(MEMO_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def update_status(dealname, status):
    """Quick helper to change only status."""
    mem = load_generated_emails()
    if dealname in mem:
        save_generated_email(
            dealname,
            mem[dealname]['subject'],
            mem[dealname]['body'],
            mem[dealname]['filename'],
            status=status
        )

# ---------- WTForms ----------
class UploadFileForm(FlaskForm):
    file = FileField(
        "Upload CSV",
        validators=[FileRequired(), FileAllowed(["csv"], "Only .csv files allowed")]
    )
    submit = SubmitField("Upload")

recent_uploads = []

# ---------- Routes ----------
@app.route('/', methods=['GET', 'POST'])
def index():
    form = UploadFileForm()
    if form.validate_on_submit():
        f  = form.file.data
        fn = secure_filename(f.filename)
        fp = os.path.join(UPLOAD_DIR, fn)
        f.save(fp)

        recent_uploads.insert(0, {
            'name': fn,
            'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        if len(recent_uploads) > 5:
            recent_uploads.pop()

        return redirect(url_for('home', filename=fn))
    return render_template('index.html', form=form, recent_uploads=recent_uploads)

@app.route('/sample')
def sample_csv():
    return send_from_directory('static', 'sample.csv', as_attachment=True)

@app.route('/home')
def home():
    filename = request.args.get('filename')
    if not filename:
        flash("No file specified. Please upload a CSV.", 'warning')
        return redirect(url_for('index'))

    fp = os.path.join(UPLOAD_DIR, filename)
    data_rows = []
    with open(fp, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)

    for idx, row in enumerate(rows):
        cleaned = row[:2] + row[4:8] + row[10:]
        if idx == 0:
            headers = cleaned + ['Actions']
        else:
            cleaned.append('n/a')
            data_rows.append(cleaned)

    mem_emails = load_generated_emails()
    gen_item  = request.args.get('gen_item', '')
    gen_email = request.args.get('gen_email', '')

    return render_template(
        'home.html',
        headers=headers,
        data=data_rows,
        gen_item=gen_item,
        gen_email=gen_email,
        filename=filename,
        mem_emails=mem_emails
    )

@app.route('/button_action1', methods=['POST'])
def button_action1():
    item = request.form['item_name']
    fn   = request.form.get('filename') or request.args.get('filename')
    fp   = os.path.join(UPLOAD_DIR, fn)

    try:
        result = csv_search_generate(item, fp)
        subject, body = (result.split('\n', 1) + [''])[:2]
        save_generated_email(item, subject, body, fn, status="generated")
        return redirect(url_for('home', filename=fn, gen_item=item, gen_email=result))
    except Exception as e:
        flash(f'Generation failed for {item}: {e}', 'danger')
        save_generated_email(item, '', '', fn, status="error")
        return redirect(url_for('home', filename=fn))

@app.route('/generate_all', methods=['POST'])
def generate_all():
    fn = request.json.get('filename')
    if not fn:
        return jsonify({"ok": False, "error": "filename missing"}), 400

    fp = os.path.join(UPLOAD_DIR, fn)
    mem = load_generated_emails()

    with open(fp, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    generated = []
    total = len(rows) - 1
    print(f"[GEN-ALL] Starting batch generation for {total} deals from {fn}", flush=True)

    for idx, row in enumerate(rows[1:], start=1):
        dealname = row[0].strip()
        if dealname in mem and mem[dealname]['status'] != 'error':
            print(f"[GEN-ALL] Skipping {dealname} (status: {mem[dealname]['status']})", flush=True)
            continue
        try:
            result = csv_search_generate(dealname, fp)
            subject, body = (result.split('\n', 1) + [''])[:2]
            save_generated_email(dealname, subject, body, fn, status="generated")
            generated.append(dealname)
            print(f"[GEN-ALL] ({idx}/{total}) Generated: {dealname}", flush=True)
        except Exception as e:
            print(f"[GEN-ALL] ERROR on {dealname}: {e}", flush=True)
            save_generated_email(dealname, '', '', fn, status="error")

    print(f"[GEN-ALL] Finished. Newly generated: {len(generated)} deals.", flush=True)
    return jsonify({"ok": True, "generated": generated})

@app.route('/button_action2', methods=['POST'])
def button_action2():
    item      = request.form['item_name']
    fn        = request.form.get('filename')
    to_email  = request.form.get('to_email', '').strip()

    if not fn:
        flash("Missing filename context.", "danger")
        return redirect(request.referrer)
    if not to_email:
        flash('Please enter a recipient email.', 'warning')
        return redirect(request.referrer)

    mem = load_generated_emails().get(item)
    if mem and mem['subject'] and mem['body']:
        subject = mem['subject']
        body    = mem['body']
    else:
        gen_email = request.form.get('gen_email', '')
        if not gen_email:
            flash('Please generate the email first.', 'warning')
            return redirect(request.referrer)
        subject, body = (gen_email.split('\n', 1) + [''])[:2]

    try:
        send_email_via_gmail(to_email, subject, body)
        update_status(item, "sent")
        flash(f'Email sent to {to_email}', 'success')
    except Exception as e:
        update_status(item, "error")
        flash(f'Failed to send email: {e}', 'danger')

    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(debug=True)
