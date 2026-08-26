const axios = require('axios');

async function deployToGithubPages(githubToken, repoName, files) {
    const headers = {
        "Authorization": `token ${githubToken}`,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    };

    try {
        // Step 1: Create repository
        try {
            await axios.post("https://api.github.com/user/repos", {
                name: repoName,
                description: "Hosted by Manual+AI Agency",
                private: false,
                auto_init: true
            }, { headers });
            console.log(`Created repository: ${repoName}`);
        } catch (err) {
            if (err.response && err.response.status === 422) {
                console.log(`Repository ${repoName} already exists. Continuing...`);
            } else {
                throw new Error(`Failed to create repository: ${err.response ? JSON.stringify(err.response.data) : err.message}`);
            }
        }

        // Get username
        const userRes = await axios.get("https://api.github.com/user", { headers });
        const username = userRes.data.login;

        // Step 2: Upload files
        for (const [filePath, content] of Object.entries(files)) {
            const fileUrl = `https://api.github.com/repos/${username}/${repoName}/contents/${filePath}`;
            let sha = null;

            try {
                const getRes = await axios.get(fileUrl, { headers });
                sha = getRes.data.sha;
            } catch (err) {
                // Ignore 404 (file doesn't exist yet)
            }

            const base64Content = Buffer.from(content).toString('base64');
            const body = {
                message: `Deploy ${filePath} via Agency Platform`,
                content: base64Content
            };
            if (sha) {
                body.sha = sha;
            }

            await axios.put(fileUrl, body, { headers });
        }

        // Step 3: Enable Pages
        const pagesUrl = `https://api.github.com/repos/${username}/${repoName}/pages`;
        try {
            await axios.post(pagesUrl, {
                source: {
                    branch: "main",
                    path: "/"
                }
            }, { headers });
            return [true, `https://${username}.github.io/${repoName}/` ];
        } catch (err) {
            if (err.response && err.response.status === 409) {
                return [true, `https://${username}.github.io/${repoName}/` ];
            }
            // Try fetching existing config
            try {
                const getPages = await axios.get(pagesUrl, { headers });
                return [true, getPages.data.html_url || `https://${username}.github.io/${repoName}/` ];
            } catch (pageErr) {
                return [false, `Files uploaded but pages configuration failed: ${err.message}`];
            }
        }

    } catch (err) {
        return [false, err.message];
    }
}

module.exports = { deployToGithubPages };
