# CentaurWeb - Manual + AI Web Development Agency Portal

A working prototype of a Web Development Agency platform designed to combine **Manual development** and **AI-powered workflows**. The platform allows clients to pay, fill out their landing page specifications, chat with an AI onboarding assistant, submit tickets for revisions, and allows developers/admins to review generated prompts, manage status, and automatically deploy static sites to **GitHub Pages**.

## Features Implemented
1. **Client Landing Page & Packages**: Pricing detail presenting static sites with free hosting (up to 100k traffic/month) and dynamic custom apps.
2. **Client Portal Dashboard**: Login panel with progress tracking, ticket management, and invoice history.
3. **AI Onboarding Assistant**: A conversational chatbot that queries Google Gemini to help clients clarify homepage contents and menus.
4. **Developer Prompt Compiler**: Automatically aggregates questionnaire details and chat logs into a structured Markdown Developer Prompt.
5. **Support Ticketing System**: Allows users to log tickets and lets developers close them when resolved.
6. **GitHub Pages Deployer**: Admin script that calls the GitHub REST API to automatically create repositories and publish static sites to `https://<username>.github.io/<repo>/`.

---

## How to Set Up and Run

### 1. Install Dependencies
Make sure Python 3.8+ is installed on your system. Navigate to the project directory and install:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
To enable the AI onboarding chat and Developer prompt compiler, set your Gemini API key:

* **Windows PowerShell**:
  ```powershell
  $env:GEMINI_API_KEY = "your-google-gemini-api-key"
  ```
* **Command Prompt / Git Bash**:
  ```bash
  export GEMINI_API_KEY="your-google-gemini-api-key"
  ```

*Note: If the key is not set, the chat will display a friendly reminder instruction.*

### 3. Run the Platform
Start the FastAPI server:
```bash
uvicorn main:app --reload
```

The application will start at `http://127.0.0.1:8000`.

---

## Demo Walkthrough Guide

1. **Sign In**: Go to `http://127.0.0.1:8000/login`.
   * To sign in as **Client**: use `client` / `client123`
   * To sign in as **Admin/Developer**: use `admin` / `admin123`
2. **Payment Simulation (Client)**: On your first login as client, click **Simulate Payment ($299)** to unlock requirements gathering.
3. **Requirement Gathering & AI Chat (Client)**: Click **Start Onboarding**. Enter your page details (menus, color scheme, content) on the left. Interact with the onboarding chatbot on the right to refine details.
4. **Submit Requirements (Client)**: Click **Submit Specifications**. The system will save your entries and trigger Gemini to compile your Developer Prompt.
5. **Verify Admin Dashboard (Admin)**: Logout and sign in as `admin`. You will see the active project, the compiled **AI Developer Prompt**, and the chat transcript.
6. **Simulate Github Pages Deployment (Admin)**:
   * Provide a GitHub Personal Access Token (PAT) with repo scopes.
   * Provide a repository name.
   * Review or modify the custom static HTML code.
   * Click **Deploy & Enable GitHub Pages** to run the deployment script. The website goes live automatically, and updates the client's dashboard with the URL!
