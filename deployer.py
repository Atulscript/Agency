import requests
import json
import base64

def deploy_to_github_pages(github_token, repo_name, files):
    """
    Deploys a dict of files to a new GitHub repository and enables GitHub Pages.
    github_token: Personal Access Token (classic or fine-grained with repo access)
    repo_name: Name of the repository to create (e.g., 'my-dental-clinic')
    files: Dict mapping filepath (e.g., 'index.html') to string content
    """
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }

    # Step 1: Create repository
    create_repo_url = "https://api.github.com/user/repos"
    repo_data = {
        "name": repo_name,
        "description": "Hosted by Manual+AI Agency",
        "private": False, # Must be public for free GitHub Pages
        "auto_init": True  # Initializes with a README so there's a main branch
    }

    try:
        response = requests.post(create_repo_url, headers=headers, json=repo_data)
        if response.status_code == 201:
            print(f"Created repository: {repo_name}")
        elif response.status_code == 422:
            # Repo already exists
            print(f"Repository {repo_name} already exists. Continuing upload...")
        else:
            return False, f"Failed to create repo: {response.text}"

        # Get authenticated username
        user_url = "https://api.github.com/user"
        user_response = requests.get(user_url, headers=headers)
        user_data = user_response.json()
        username = user_data['login']

        # Step 2: Upload files
        for path, content in files.items():
            file_url = f"https://api.github.com/repos/{username}/{repo_name}/contents/{path}"
            
            # Check if file exists to get its SHA (required for updates)
            sha = None
            check_response = requests.get(file_url, headers=headers)
            if check_response.status_code == 200:
                sha = check_response.json()['sha']

            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            upload_data = {
                "message": f"Deploy {path} via Agency Platform",
                "content": encoded_content
            }
            if sha:
                upload_data["sha"] = sha

            upload_response = requests.put(file_url, headers=headers, json=upload_data)
            if upload_response.status_code not in [200, 201]:
                return False, f"Failed to upload {path}: {upload_response.text}"

        # Step 3: Enable GitHub Pages
        pages_url = f"https://api.github.com/repos/{username}/{repo_name}/pages"
        pages_data = {
            "source": {
                "branch": "main",
                "path": "/"
            }
        }
        
        # GitHub pages config endpoint can sometimes return 201 or 409 (if already enabled)
        pages_response = requests.post(pages_url, headers=headers, json=pages_data)
        if pages_response.status_code in [201, 204]:
            pages_info = pages_response.json()
            return True, pages_info.get("html_url", f"https://{username}.github.io/{repo_name}/")
        elif pages_response.status_code == 409:
            # Already enabled
            return True, f"https://{username}.github.io/{repo_name}/"
        else:
            # Try getting pages configuration
            get_pages = requests.get(pages_url, headers=headers)
            if get_pages.status_code == 200:
                return True, get_pages.json().get("html_url", f"https://{username}.github.io/{repo_name}/")
            return False, f"Files uploaded but Pages configuration failed: {pages_response.text}"

    except Exception as e:
        return False, f"Error in GitHub Pages deployer: {str(e)}"
