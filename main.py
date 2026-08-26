import os
import json
import random
import string
import io
import zipfile
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, get_db_connection
import ai_helper
import deployer

app = FastAPI(title="CraftedAI - Web Agency Platform")

# Add Session Middleware
app.add_middleware(SessionMiddleware, secret_key="supersecretkeyagency")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Initialize database on startup
@app.on_event("startup")
def startup():
    if not os.path.exists("templates"):
        os.makedirs("templates")
    init_db()

# Helper to get current user
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

# --- Client Facing Routes ---

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("about.html", {"request": request, "user": user})

@app.get("/team", response_class=HTMLResponse)
def team(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("team.html", {"request": request, "user": user})

@app.get("/contact", response_class=HTMLResponse)
def contact_get(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("contact.html", {"request": request, "user": user, "success": False})

@app.post("/contact", response_class=HTMLResponse)
def contact_post(request: Request, name: str = Form(...), email: str = Form(...), project_type: str = Form(...), message: str = Form(...)):
    user = get_current_user(request)
    return templates.TemplateResponse("contact.html", {"request": request, "user": user, "success": True})

@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    if user:
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        request.session["role"] = user["role"]
        if user["role"] == "admin":
            return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    if user["role"] == "admin":
        return RedirectResponse(url="/admin")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    
    tickets = []
    invoices = []
    if project:
        tickets = conn.execute("SELECT * FROM tickets WHERE project_id = ? ORDER BY id DESC", (project["id"],)).fetchall()
        invoices = conn.execute("SELECT * FROM invoices WHERE project_id = ? ORDER BY id DESC", (project["id"],)).fetchall()
        
    conn.close()
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user": user, 
        "project": project, 
        "tickets": tickets,
        "invoices": invoices
    })

@app.post("/simulate-payment")
def simulate_payment(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if project:
        conn.execute("UPDATE projects SET status = 'Requirements Gathering' WHERE id = ?", (project["id"],))
        conn.execute("INSERT INTO invoices (project_id, amount, currency) VALUES (?, '99', 'USD')", (project["id"],))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/onboarding", response_class=HTMLResponse)
def onboarding(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    
    if not project or project["status"] == "Payment Pending":
        conn.close()
        return RedirectResponse(url="/dashboard")
        
    # Get chat history
    chat_history = conn.execute("SELECT * FROM chat_messages WHERE project_id = ? ORDER BY id ASC", (project["id"],)).fetchall()
    conn.close()
    
    # Parse existing JSON fields if they exist
    homepage_data = json.loads(project["homepage_details"]) if project["homepage_details"] else {}
    styling_data = json.loads(project["styling_references"]) if project["styling_references"] else {}
    content_data = json.loads(project["content_data"]) if project["content_data"] else {}
    custom_data = json.loads(project["custom_features"]) if project["custom_features"] else {}
    
    return templates.TemplateResponse("onboarding.html", {
        "request": request,
        "user": user,
        "project": project,
        "chat_history": chat_history,
        "homepage": homepage_data,
        "styling": styling_data,
        "content": content_data,
        "custom": custom_data
    })

@app.post("/onboarding-submit")
def onboarding_submit(
    request: Request,
    website_name: str = Form(...),
    menu_items: str = Form(""),
    hero_headline: str = Form(""),
    hero_cta: str = Form(""),
    middle_content: str = Form(""),
    footer_text: str = Form(""),
    styling_theme: str = Form(""),
    reference_website: str = Form(""),
    home_content: str = Form(""),
    about_content: str = Form(""),
    team_content: str = Form("")
):
    user = get_current_user(request)
    if not user:
         return RedirectResponse(url="/login")
         
    homepage_details = json.dumps({
        "menu_items": [i.strip() for i in menu_items.split(",") if i.strip()],
        "hero_headline": hero_headline,
        "hero_cta": hero_cta,
        "middle_content": middle_content,
        "footer_text": footer_text
    })
    
    styling_references = json.dumps({
        "theme": styling_theme,
        "reference_website": reference_website
    })
    
    content_data = json.dumps({
        "home": home_content,
        "about": about_content,
        "team": team_content
    })
    
    conn = get_db_connection()
    conn.execute(
        """UPDATE projects SET 
            name = ?, 
            homepage_details = ?, 
            styling_references = ?, 
            content_data = ?, 
            status = 'In Progress' 
           WHERE user_id = ? AND active = 1""",
        (website_name, homepage_details, styling_references, content_data, user["id"])
    )
    
    # Trigger Developer Prompt Generation in background using current details
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    chat_history_rows = conn.execute("SELECT sender, message FROM chat_messages WHERE project_id = ?", (project["id"],)).fetchall()
    chat_history = [{"sender": r["sender"], "message": r["message"]} for r in chat_history_rows]
    
    form_data = {
        "website_name": website_name,
        "homepage": json.loads(homepage_details),
        "styling": json.loads(styling_references),
        "content": json.loads(content_data)
    }
    
    dev_prompt = ai_helper.generate_developer_prompt(form_data, chat_history)
    conn.execute("UPDATE projects SET developer_prompt = ? WHERE id = ?", (dev_prompt, project["id"]))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/chat")
def chat_with_ai(request: Request, message: str = Form(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Save User message
    conn.execute("INSERT INTO chat_messages (project_id, sender, message) VALUES (?, 'user', ?)", (project["id"], message))
    conn.commit()
    
    # Fetch full history
    chat_history_rows = conn.execute("SELECT sender, message FROM chat_messages WHERE project_id = ? ORDER BY id ASC", (project["id"],)).fetchall()
    chat_history = [{"sender": r["sender"], "message": r["message"]} for r in chat_history_rows]
    
    # Parse form data
    form_data = {
        "homepage": json.loads(project["homepage_details"]) if project["homepage_details"] else {},
        "styling": json.loads(project["styling_references"]) if project["styling_references"] else {},
        "content": json.loads(project["content_data"]) if project["content_data"] else {}
    }
    
    # Get response from AI
    ai_response = ai_helper.generate_ai_chat_response(form_data, chat_history, message)
    
    # Save AI Response
    conn.execute("INSERT INTO chat_messages (project_id, sender, message) VALUES (?, 'ai', ?)", (project["id"], ai_response))
    conn.commit()
    conn.close()
    
    return JSONResponse({"reply": ai_response})

@app.post("/api/suggest")
def api_suggest(request: Request, field: str = Form(...), name: str = Form(...), theme: str = Form("")):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    prompt = f"Field: {field}. Business/Brand Name: {name}. Style/Theme: {theme}."
    system_instruction = (
        "You are an expert copywriter for a web design agency. "
        "Your task is to generate 3 short, high-quality, professional copywriting suggestions for a client's website field. "
        "Return a JSON array of 3 strings, e.g. ['Suggestion 1', 'Suggestion 2', 'Suggestion 3']. "
        "Do not include any other text, markdown block wraps (like ```json), or explanation. Just raw JSON list."
    )
    
    raw_response = ai_helper.call_gemini(system_instruction, prompt)
    
    try:
        cleaned = raw_response.replace("```json", "").replace("```", "").strip()
        suggestions = json.loads(cleaned)
    except Exception:
        # Fallback split
        lines = [line.strip().lstrip("-").lstrip("123.").strip().strip('"').strip("'") for line in raw_response.split("\n") if line.strip()]
        suggestions = [line for line in lines if line][:3]
        if not suggestions:
            suggestions = ["Professional Design Setup", "Premium Customer Experience", "Empowering Digital Futures"]
            
    return JSONResponse({"suggestions": suggestions})

@app.post("/tickets/create")
def create_ticket(request: Request, title: str = Form(...), description: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT id FROM projects WHERE user_id = ?", (user["id"],)).fetchone()
    if project:
        conn.execute("INSERT INTO tickets (project_id, title, description) VALUES (?, ?, ?)", (project["id"], title, description))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

# --- Admin / Developer Facing Routes ---

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    projects = conn.execute("""
        SELECT p.*, u.username, u.email 
        FROM projects p 
        JOIN users u ON p.user_id = u.id
    """).fetchall()
    
    tickets = conn.execute("""
        SELECT t.*, p.name as project_name 
        FROM tickets t 
        JOIN projects p ON t.project_id = p.id 
        ORDER BY t.status DESC, t.id DESC
    """).fetchall()
    conn.close()
    
    return templates.TemplateResponse("admin.html", {"request": request, "user": user, "projects": projects, "tickets": tickets})

@app.post("/admin/update-status")
def admin_update_status(request: Request, project_id: int = Form(...), status: str = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
         return RedirectResponse(url="/login")
         
    conn = get_db_connection()
    conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/tickets/resolve")
def admin_resolve_ticket(request: Request, ticket_id: int = Form(...)):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
         return RedirectResponse(url="/login")
         
    conn = get_db_connection()
    conn.execute("UPDATE tickets SET status = 'Closed' WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/deploy")
def admin_deploy_project(
    request: Request,
    project_id: int = Form(...),
    github_token: str = Form(...),
    repo_name: str = Form(...),
    html_content: str = Form(...)
):
    user = get_current_user(request)
    if not user or user["role"] != "admin":
         return RedirectResponse(url="/login")
         
    # Package files dict
    files = {
        "index.html": html_content,
        "README.md": f"# {repo_name}\nHosted automatically by Manual+AI Agency platform."
    }
    
    success, result = deployer.deploy_to_github_pages(github_token, repo_name, files)
    
    conn = get_db_connection()
    if success:
        custom_features = json.dumps({"deployed_html": html_content})
        conn.execute("UPDATE projects SET github_repo_url = ?, custom_features = ?, status = 'Completed' WHERE id = ?", (result, custom_features, project_id))
        conn.commit()
    conn.close()
    
    # Store dynamic outcome in session to alert admin
    request.session["deploy_success"] = success
    request.session["deploy_message"] = result
    
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/project/revision")
def request_revision(request: Request, feedback: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if project:
        rev_left = project["revisions_left"]
        if rev_left > 0 and project["status"] in ["Review", "Completed"]:
            new_rev_left = rev_left - 1
            conn.execute("UPDATE projects SET status = 'In Progress', revisions_left = ? WHERE id = ?", (new_rev_left, project["id"]))
            conn.execute("INSERT INTO tickets (project_id, title, description) VALUES (?, ?, ?)", (project["id"], f"Revision Request (Remaining: {new_rev_left})", feedback))
            conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/project/accept")
def accept_project(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if project:
        conn.execute("UPDATE projects SET status = 'Completed' WHERE id = ?", (project["id"],))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/project/request-change")
def request_change(request: Request, change_description: str = Form(...)):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if project and project["status"] == "Completed":
        conn.execute("UPDATE projects SET status = 'In Progress' WHERE id = ?", (project["id"],))
        conn.execute("INSERT INTO tickets (project_id, title, description) VALUES (?, 'Post-Launch Change Request', ?)", (project["id"], change_description))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/project/new")
def start_new_project(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    if project and project["status"] == "Completed":
        # Mark current project as inactive
        conn.execute("UPDATE projects SET active = 0 WHERE id = ?", (project["id"],))
        # Insert a new active project
        conn.execute("INSERT INTO projects (user_id, status, active) VALUES (?, 'Payment Pending', 1)", (user["id"],))
        conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/api/purchase")
def api_purchase(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    amount: str = Form("99"),
    currency: str = Form("USD")
):
    conn = get_db_connection()
    
    # Check if user already exists
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        # Generate random username and password
        email_prefix = email.split("@")[0].lower()
        clean_prefix = "".join(c for c in email_prefix if c.isalnum())
        username = f"client_{clean_prefix}_{random.randint(10, 99)}"
        password = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        
        # Insert user
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, 'client')", (username, password, email))
        user_id = cursor.lastrowid
    else:
        username = user["username"]
        password = user["password"]
        user_id = user["id"]
        
        # Mark any other project of this user as inactive
        conn.execute("UPDATE projects SET active = 0 WHERE user_id = ?", (user_id,))
    
    # Create new project
    cursor = conn.cursor()
    cursor.execute("INSERT INTO projects (user_id, status, active) VALUES (?, 'Requirements Gathering', 1)", (user_id,))
    project_id = cursor.lastrowid
    
    # Generate paid invoice
    conn.execute("INSERT INTO invoices (project_id, amount, currency) VALUES (?, ?, ?)", (project_id, amount, currency))
    conn.commit()
    conn.close()
    
    # Simulate Whatsapp & Email notifications
    print(f"\n======================================")
    print(f"[BILLING EMAIL SENT]")
    print(f"To: {email}")
    print(f"Subject: Bill Generated - CentaurWeb Invoice #{project_id + 1000}")
    print(f"Amount: {currency} {amount} (Paid via Gateway)")
    print(f"--------------------------------------")
    print(f"[WHATSAPP CREDS SENT]")
    print(f"To: {phone}")
    print(f"Message: Welcome to CentaurWeb! Your website setup is paid. Login to onboarding here: http://localhost:8000/login")
    print(f"Credentials -> Username: {username} | Password: {password}")
    print(f"======================================\n")
    
    return JSONResponse({
        "success": True,
        "username": username,
        "password": password,
        "email": email,
        "phone": phone,
        "invoice_id": project_id + 1000,
        "message": "Billing generated. Login credentials dispatched to email and whatsapp."
    })

@app.get("/project/download-zip")
def download_project_zip(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
        
    conn = get_db_connection()
    project = conn.execute("SELECT * FROM projects WHERE user_id = ? AND active = 1", (user["id"],)).fetchone()
    conn.close()
    
    if not project or project["status"] != "Completed":
        raise HTTPException(status_code=400, detail="Project not completed yet.")
        
    custom_data = json.loads(project["custom_features"]) if project["custom_features"] else {}
    html_code = custom_data.get("deployed_html", "<h1>Custom Website Under Development</h1>")
    
    # Create zip file in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("index.html", html_code)
        zip_file.writestr("README.md", f"# {project['name']}\nDelivered by CentaurWeb.\n\nDeploy this folder to Firebase Hosting, Vercel, or Netlify for free.")
        
    zip_buffer.seek(0)
    
    headers = {
        'Content-Disposition': f'attachment; filename="{project["name"].lower().replace(" ", "_")}_website.zip"'
    }
    return StreamingResponse(zip_buffer, media_type="application/x-zip-compressed", headers=headers)
