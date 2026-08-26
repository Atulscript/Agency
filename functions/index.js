const functions = require('firebase-functions');
const admin = require('firebase-admin');
const express = require('express');
const cors = require('cors');
const archiver = require('archiver');
const { GoogleGenAI } = require('@google/generative-ai');
const { deployToGithubPages } = require('./deployer');

admin.initializeApp();
const db = admin.firestore();

// Fetch Gemini API key from Firebase Environment Config or OS Env
const getGeminiKey = () => {
    return process.env.GEMINI_API_KEY || "";
};

const app = express();
app.use(cors({ origin: true }));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Token Verification Middleware
async function authenticateUser(req, res, next) {
    if (req.path === '/api/purchase' || req.path === '/purchase') {
        return next(); // Webhook is public
    }
    
    let idToken;
    if (req.headers.authorization && req.headers.authorization.startsWith('Bearer ')) {
        idToken = req.headers.authorization.split('Bearer ')[1];
    } else if (req.query && req.query.token) {
        idToken = req.query.token;
    } else if (req.body && req.body.token) {
        idToken = req.body.token;
    }

    if (!idToken) {
        return res.status(403).json({ error: 'Unauthorized: No token provided' });
    }

    try {
        const decodedToken = await admin.auth().verifyIdToken(idToken);
        req.user = decodedToken;
        next();
    } catch (error) {
        return res.status(403).json({ error: 'Unauthorized: Invalid token' });
    }
}

app.use(authenticateUser);

// Helper to get active project for user
async function getActiveProject(userId) {
    const query = await db.collection('projects')
        .where('userId', '==', userId)
        .where('active', '==', true)
        .limit(1)
        .get();
    
    if (query.empty) return null;
    return { id: query.docs[0].id, ...query.docs[0].data() };
}

// 1. Webhook - purchase and create account
app.post('/api/purchase', async (req, res) => {
    const { name, email, phone, amount = "99", currency = "USD" } = req.body;
    
    if (!email || !name) {
        return res.status(400).json({ error: "Missing required fields" });
    }

    try {
        let userRecord;
        let password = Math.random().toString(36).slice(-6); // Random 6-char pass
        
        try {
            userRecord = await admin.auth().getUserByEmail(email);
        } catch (err) {
            // User does not exist, create them
            userRecord = await admin.auth().createUser({
                email,
                password,
                displayName: name,
                phoneNumber: phone || undefined
            });
            
            // Write user details
            await db.collection('users').doc(userRecord.uid).set({
                email,
                name,
                role: 'client',
                createdAt: admin.firestore.FieldValue.serverTimestamp()
            });
        }

        const userId = userRecord.uid;

        // Archive any older active projects for this user
        const oldProjects = await db.collection('projects')
            .where('userId', '==', userId)
            .where('active', '==', true)
            .get();
            
        const batch = db.batch();
        oldProjects.forEach(doc => {
            batch.update(doc.ref, { active: false });
        });
        await batch.commit();

        // Create new active project
        const projectRef = await db.collection('projects').add({
            userId,
            name: "My New Website",
            status: "Requirements Gathering",
            active: true,
            revisions_left: 2,
            homepage_details: null,
            styling_references: null,
            content_data: null,
            custom_features: null,
            developer_prompt: null,
            github_repo_url: null,
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        // Generate paid invoice
        await projectRef.collection('invoices').add({
            amount,
            currency,
            status: "Paid",
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        console.log(`\n======================================`);
        console.log(`[BILLING EMAIL SENT] To: ${email}`);
        console.log(`[WHATSAPP CREDS SENT] To: ${phone}`);
        console.log(`Credentials -> Username: ${email} | Password: ${password}`);
        console.log(`======================================\n`);

        return res.json({
            success: true,
            uid: userId,
            email,
            password,
            projectId: projectRef.id,
            message: "Purchase logged. Account created and credentials dispatched."
        });

    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 2. Simulate Payment
app.post('/simulate-payment', async (req, res) => {
    try {
        const project = await getActiveProject(req.user.uid);
        if (!project) {
            return res.status(404).json({ error: "No active project found" });
        }

        await db.collection('projects').doc(project.id).update({
            status: "Requirements Gathering"
        });

        await db.collection('projects').doc(project.id).collection('invoices').add({
            amount: "99",
            currency: "USD",
            status: "Paid",
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 3. Onboarding Submit
app.post('/onboarding-submit', async (req, res) => {
    const { 
        website_name, menu_items, hero_headline, hero_cta, 
        middle_content, footer_text, styling_theme, reference_website,
        home_content, about_content, team_content 
    } = req.body;

    try {
        const project = await getActiveProject(req.user.uid);
        if (!project) {
            return res.status(404).json({ error: "No active project found" });
        }

        const homepage_details = {
            menu_items: menu_items ? menu_items.split(",").map(i => i.strip()) : [],
            hero_headline,
            hero_cta,
            middle_content,
            footer_text
        };

        const styling_references = {
            theme: styling_theme,
            reference_website
        };

        const content_data = {
            home: home_content,
            about: about_content,
            team: team_content
        };

        // Fetch chat messages
        const chatSnapshot = await db.collection('projects').doc(project.id).collection('chat_messages').orderBy('timestamp', 'asc').get();
        const chat_history = [];
        chatSnapshot.forEach(doc => {
            const data = doc.data();
            chat_history.push({ sender: data.sender, message: data.message });
        });

        // Build dev prompt
        let dev_prompt = "Compiling Developer Prompt...";
        const apiKey = getGeminiKey();
        if (apiKey) {
            const ai = new GoogleGenAI({ apiKey });
            const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });
            const prompt = `Client Form Data:\n${JSON.stringify({ website_name, homepage_details, styling_references, content_data }, null, 2)}\n\nChat History:\n${JSON.stringify(chat_history)}\n\nCompile a comprehensive Developer Prompt in markdown format.`;
            const result = await model.generateContent(prompt);
            dev_prompt = result.response.text();
        }

        await db.collection('projects').doc(project.id).update({
            name: website_name || project.name,
            homepage_details: JSON.stringify(homepage_details),
            styling_references: JSON.stringify(styling_references),
            content_data: JSON.stringify(content_data),
            developer_prompt: dev_prompt,
            status: "In Progress"
        });

        return res.json({ success: true });

    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 4. Onboarding Chat Assistant
app.post('/chat', async (req, res) => {
    const { message } = req.body;
    try {
        const project = await getActiveProject(req.user.uid);
        if (!project) {
            return res.status(404).json({ error: "No active project found" });
        }

        // Save user message
        const chatCol = db.collection('projects').doc(project.id).collection('chat_messages');
        await chatCol.add({
            sender: 'user',
            message: message,
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });

        // Get full history
        const snapshot = await chatCol.orderBy('timestamp', 'asc').get();
        const chat_history = [];
        snapshot.forEach(doc => {
            chat_history.push(doc.data());
        });

        const homepage = project.homepage_details ? JSON.loads(project.homepage_details) : {};
        const styling = project.styling_references ? JSON.loads(project.styling_references) : {};
        const content = project.content_data ? JSON.loads(project.content_data) : {};

        let aiResponse = "AI Onboarding Assistant is not initialized. Key is missing.";
        const apiKey = getGeminiKey();
        if (apiKey) {
            const ai = new GoogleGenAI({ apiKey });
            const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });
            const prompt = `Client Form Data:\n${JSON.stringify({ homepage, styling, content }, null, 2)}\n\nChat History:\n${JSON.stringify(chat_history)}\n\nClient: ${message}\nGenerate next onboarding assistance questions.`;
            const result = await model.generateContent(prompt);
            aiResponse = result.response.text();
        }

        // Save AI message
        await chatCol.add({
            sender: 'ai',
            message: aiResponse,
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        });

        return res.json({ reply: aiResponse });

    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 5. suggestions copywriting
app.post('/api/suggest', async (req, res) => {
    const { field, name, theme } = req.body;
    try {
        const apiKey = getGeminiKey();
        let suggestions = ["Professional Design Setup", "Premium Customer Experience", "Empowering Digital Futures"];
        
        if (apiKey) {
            const ai = new GoogleGenAI({ apiKey });
            const model = ai.getGenerativeModel({ model: "gemini-1.5-flash" });
            const prompt = `Field: ${field}. Brand: ${name}. Theme: ${theme}. Return 3 suggestions as a JSON array of strings.`;
            const result = await model.generateContent(prompt);
            const text = result.response.text().replace("```json", "").replace("```", "").trim();
            suggestions = JSON.parse(text);
        }
        return res.json({ suggestions });
    } catch (error) {
        return res.json({ suggestions: ["Default Copy Option 1", "Default Copy Option 2", "Default Copy Option 3"] });
    }
});

// 6. Create Support Ticket
app.post('/tickets/create', async (req, res) => {
    const { title, description } = req.body;
    try {
        const project = await getActiveProject(req.user.uid);
        if (!project) {
            return res.status(404).json({ error: "No active project found" });
        }

        await db.collection('projects').doc(project.id).collection('tickets').add({
            title,
            description,
            status: "Open",
            createdAt: admin.firestore.FieldValue.serverTimestamp()
        });

        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 7. Download ZIP file
app.get('/project/download-zip', async (req, res) => {
    try {
        const project = await getActiveProject(req.user.uid);
        if (!project || project.status !== 'Completed') {
            return res.status(400).send("Project is not completed.");
        }

        const customData = project.custom_features ? JSON.parse(project.custom_features) : {};
        const htmlCode = customData.deployed_html || "<h1>Custom Website Under Development</h1>";

        res.setHeader('Content-Type', 'application/zip');
        res.setHeader('Content-Disposition', `attachment; filename="${project.name.toLowerCase().replace(/ /g, '_')}_website.zip"`);

        const archive = archiver('zip', { zlib: { level: 9 } });
        archive.pipe(res);
        archive.append(htmlCode, { name: 'index.html' });
        archive.append(`# ${project.name}\nDelivered by CentaurWeb.\n\nDeploy to Firebase Hosting for free!`, { name: 'README.md' });
        await archive.finalize();

    } catch (error) {
        return res.status(500).send(error.message);
    }
});

// 8. Revisions Request
app.post('/project/revision', async (req, res) => {
    const { feedback } = req.body;
    try {
        const project = await getActiveProject(req.user.uid);
        if (project && project.revisions_left > 0) {
            const newRevLeft = project.revisions_left - 1;
            await db.collection('projects').doc(project.id).update({
                status: 'In Progress',
                revisions_left: newRevLeft
            });
            await db.collection('projects').doc(project.id).collection('tickets').add({
                title: `Revision Request (Remaining: ${newRevLeft})`,
                description: feedback,
                status: "Open",
                createdAt: admin.firestore.FieldValue.serverTimestamp()
            });
        }
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 9. Accept Project Completion
app.post('/project/accept', async (req, res) => {
    try {
        const project = await getActiveProject(req.user.uid);
        if (project) {
            await db.collection('projects').doc(project.id).update({
                status: 'Completed'
            });
        }
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 10. Request Post-Launch Changes
app.post('/project/request-change', async (req, res) => {
    const { change_description } = req.body;
    try {
        const project = await getActiveProject(req.user.uid);
        if (project && project.status === 'Completed') {
            await db.collection('projects').doc(project.id).update({
                status: 'In Progress'
            });
            await db.collection('projects').doc(project.id).collection('tickets').add({
                title: 'Post-Launch Change Request',
                description: change_description,
                status: 'Open',
                createdAt: admin.firestore.FieldValue.serverTimestamp()
            });
        }
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 11. Start New Project
app.post('/project/new', async (req, res) => {
    try {
        const project = await getActiveProject(req.user.uid);
        if (project && project.status === 'Completed') {
            await db.collection('projects').doc(project.id).update({
                active: false
            });
            await db.collection('projects').add({
                userId: req.user.uid,
                name: "My New Website",
                status: 'Payment Pending',
                active: true,
                revisions_left: 2,
                createdAt: admin.firestore.FieldValue.serverTimestamp()
            });
        }
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// --- Admin Endpoints ---

// Middleware to verify admin role
async function requireAdmin(req, res, next) {
    const userDoc = await db.collection('users').doc(req.user.uid).get();
    if (userDoc.exists && userDoc.data().role === 'admin') {
        return next();
    }
    return res.status(403).json({ error: "Access denied. Admin role required." });
}

// 12. Admin Deploy
app.post('/admin/deploy', requireAdmin, async (req, res) => {
    const { project_id, github_token, repo_name, html_content } = req.body;
    try {
        const files = {
            "index.html": html_content,
            "README.md": `# ${repo_name}\nHosted by Web Agency platform.`
        };

        const [success, result] = await deployToGithubPages(github_token, repo_name, files);
        if (success) {
            await db.collection('projects').doc(project_id).update({
                github_repo_url: result,
                custom_features: JSON.stringify({ deployed_html: html_content }),
                status: 'Completed'
            });
            return res.json({ success: true, url: result });
        } else {
            return res.status(500).json({ error: result });
        }
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 13. Admin update status
app.post('/admin/update-status', requireAdmin, async (req, res) => {
    const { project_id, status } = req.body;
    try {
        await db.collection('projects').doc(project_id).update({ status });
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

// 14. Admin resolve ticket
app.post('/admin/tickets/resolve', requireAdmin, async (req, res) => {
    const { project_id, ticket_id } = req.body;
    try {
        await db.collection('projects').doc(project_id).collection('tickets').doc(ticket_id).update({
            status: 'Closed'
        });
        return res.json({ success: true });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
});

exports.api = functions.https.onRequest(app);
