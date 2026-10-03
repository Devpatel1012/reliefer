// --- Backend Configuration ---
const API_BASE_URL = (window.location.protocol === "file:" || ((window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") && window.location.port !== "8000")) ? "http://127.0.0.1:8000" : "";

// --- State & Authentication ---
let userData = null;
let currentGeneratedResumeId = null;
let activeEditItem = null; // { entity: 'skills'|'projects'|..., id: number }

try {
    const cached = localStorage.getItem("reliefer_user");
    if (cached) {
        userData = JSON.parse(cached);
    }
} catch (e) {
    console.warn("localStorage read error:", e);
}

// Fallback checking URL params
const urlParams = new URLSearchParams(window.location.search);
if (!userData && urlParams.has("email") && urlParams.has("name")) {
    userData = {
        name: urlParams.get("name"),
        email: urlParams.get("email"),
        profession: urlParams.get("profession"),
        interest: urlParams.get("interest"),
        age: urlParams.get("age")
    };
}

// Guard: redirect to login if no valid user/token is present
if (!userData || (!userData.access_token && window.location.protocol !== "file:")) {
    if (!userData || !userData.access_token) {
        redirectToLogin();
    }
}

function redirectToLogin() {
    try {
        localStorage.removeItem("reliefer_user");
    } catch (e) {}
    window.location.href = window.location.protocol === "file:" ? "./index.html" : "/";
}

// --- API Helper ---
async function fetchWithAuth(endpoint, options = {}) {
    const headers = options.headers || {};
    if (userData && userData.access_token) {
        headers["Authorization"] = `Bearer ${userData.access_token}`;
    }
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }

    options.headers = headers;
    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);

    if (response.status === 401) {
        showToast("Session expired. Please log in again.", "error");
        setTimeout(redirectToLogin, 1500);
        throw new Error("Unauthorized");
    }

    return response;
}

// --- Stacking Toast System ---
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) {
        showDashMessage(message, type === "error");
        return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let iconName = "info";
    if (type === "success") iconName = "check-circle";
    if (type === "error") iconName = "alert-circle";

    toast.innerHTML = `
        <div class="toast-icon"><i data-lucide="${iconName}"></i></div>
        <div class="toast-message">${escapeHtml(message)}</div>
        <button class="toast-close" onclick="this.parentElement.remove()"><i data-lucide="x"></i></button>
        <div class="toast-progress"></div>
    `;

    container.appendChild(toast);
    refreshIcons();

    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }
    }, 4000);
}

// Fallback banner compatibility wrapper
function showDashMessage(msg, isError = false) {
    showToast(msg, isError ? "error" : "success");
}

function refreshIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
    }
}

// --- Skeleton Loaders & Empty States ---
function showSkeletons(containerId, count = 2) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = Array(count).fill(0).map(() => `
        <div class="card-item skeleton-card skeleton">
            <div class="skeleton-title skeleton"></div>
            <div class="skeleton-text skeleton"></div>
        </div>
    `).join("");
}

function renderEmptyState(containerId, title, subtitle, icon = "folder-open") {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon"><i data-lucide="${icon}"></i></div>
            <h4>${escapeHtml(title)}</h4>
            <p>${escapeHtml(subtitle)}</p>
        </div>
    `;
    refreshIcons();
}

// --- Profile Completeness Calculator ---
function updateCompletenessRing(data) {
    let score = 0;
    if (data.name) score += 20;
    if (data.has_huggingface_key) score += 20;
    if (data.total_skills > 0) score += 20;
    if (data.total_projects > 0) score += 20;
    if (data.total_experience > 0 || data.total_education > 0) score += 20;

    const circle = document.getElementById("completeness-circle");
    const percentLabel = document.getElementById("completeness-percent");
    const subtitleLabel = document.getElementById("completeness-subtitle");

    if (circle) {
        const strokeDash = 251.2;
        const offset = strokeDash * (1 - score / 100);
        circle.style.strokeDashoffset = offset;
    }

    if (percentLabel) {
        percentLabel.textContent = `${score}%`;
    }

    if (subtitleLabel) {
        if (score === 100) {
            subtitleLabel.textContent = "🎉 Excellent! Your profile is 100% complete and ready for AI resume personalization.";
        } else if (score >= 60) {
            subtitleLabel.textContent = "Good progress! Complete remaining items to optimize ATS keyword targeting.";
        } else {
            subtitleLabel.textContent = "Add your skills, projects, work experience, and HF API key to unlock full AI optimization.";
        }
    }
}

// --- Tab Navigation ---
function switchTab(tabId) {
    document.querySelectorAll(".nav-link").forEach(link => {
        link.classList.toggle("active", link.getAttribute("data-tab") === tabId);
    });

    document.querySelectorAll(".bottom-nav-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });

    document.querySelectorAll(".tab-content").forEach(content => {
        content.style.display = content.id === `tab-${tabId}` ? "block" : "none";
    });

    // Refresh tab content when selected
    if (tabId === "overview") loadDashboardSummary();
    if (tabId === "profile") loadProfileSubtab("skills");
    if (tabId === "builder") loadTemplateSelectOptions();
    if (tabId === "history") loadResumeHistory();
    if (tabId === "settings") checkKeyStatus();

    refreshIcons();
}

function loadProfileSubtab(subtabKey) {
    document.querySelectorAll(".subnav-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-subtab") === subtabKey);
    });

    document.querySelectorAll(".subtab-content").forEach(content => {
        content.style.display = content.id === `subtab-${subtabKey}` ? "block" : "none";
    });

    if (subtabKey === "skills") loadSkills();
    if (subtabKey === "projects") loadProjects();
    if (subtabKey === "experience") loadExperience();
    if (subtabKey === "education") loadEducation();
    if (subtabKey === "achievements") loadAchievements();
    if (subtabKey === "templates") loadTemplates();
}

// Attach event listeners for tabs & DOM setup
document.addEventListener("DOMContentLoaded", () => {
    // Top Nav Links
    document.querySelectorAll(".nav-link").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const tab = link.getAttribute("data-tab");
            if (tab) switchTab(tab);
        });
    });

    // Profile Subnav Buttons
    document.querySelectorAll(".subnav-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const subtab = btn.getAttribute("data-subtab");
            if (subtab) loadProfileSubtab(subtab);
        });
    });

    // Logout
    document.getElementById("logout-btn").addEventListener("click", redirectToLogin);

    // Forms Setup
    setupFormListeners();

    // Initial load
    if (userData && userData.name) {
        document.getElementById("user-name").textContent = userData.name;
    }
    loadDashboardSummary();
    refreshIcons();
});

// ─── DATA FETCHING & UI RENDERERS ───

// 1. Dashboard Overview Summary
function setBadgeCount(id, count) {
    const badge = document.getElementById(id);
    if (badge) {
        badge.textContent = count ?? 0;
        badge.style.display = "inline-block";
    }
}

async function loadDashboardSummary() {
    try {
        const res = await fetchWithAuth("/dashboard/summary");
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("user-name").textContent = data.name || userData.name || "User";
        document.getElementById("stat-profession").textContent = data.profession || "—";
        document.getElementById("stat-interest").textContent = data.interest || "—";
        document.getElementById("stat-skills").textContent = data.total_skills ?? 0;
        document.getElementById("stat-projects").textContent = data.total_projects ?? 0;
        document.getElementById("stat-resumes").textContent = data.total_resumes_generated ?? 0;

        setBadgeCount("count-badge-skills", data.total_skills);
        setBadgeCount("count-badge-projects", data.total_projects);
        setBadgeCount("count-badge-experience", data.total_experience);
        setBadgeCount("count-badge-education", data.total_education);
        setBadgeCount("count-badge-achievements", data.total_achievements);
        setBadgeCount("count-badge-history", data.total_resumes_generated);

        const hfBadge = document.getElementById("stat-hf-key");
        if (data.has_huggingface_key) {
            hfBadge.innerHTML = `<span class="badge badge-success">✓ Connected</span>`;
        } else {
            hfBadge.innerHTML = `<span class="badge badge-warning">! Not Configured</span>`;
        }

        updateCompletenessRing(data);
        checkOnboardingNeeded(data);
        refreshIcons();
    } catch (err) {
        console.error("Failed to load dashboard summary:", err);
    }
}

// 2. Skills Management
async function loadSkills() {
    showSkeletons("skills-list");
    try {
        const res = await fetchWithAuth("/skills/");
        const skills = await res.json();
        const listDiv = document.getElementById("skills-list");
        if (!skills || skills.length === 0) {
            renderEmptyState("skills-list", "No skills added yet", "Add your core technical and soft skills to improve ATS matches.", "zap");
            return;
        }
        listDiv.innerHTML = skills.map(s => `
            <div class="card-item">
                <div class="card-header">
                    <h4>${escapeHtml(s.name)}</h4>
                    <div class="card-header-actions">
                        <button class="card-edit-btn" onclick='openEditModal("skill", ${JSON.stringify(s).replace(/'/g, "&apos;")})'><i data-lucide="pencil"></i> Edit</button>
                        <button class="card-delete-btn" onclick="deleteSkill(${s.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                <p>Category: ${escapeHtml(s.category || 'General')} | Proficiency: ${escapeHtml(s.proficiency || 'Intermediate')}</p>
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("skills-list", "Error loading skills", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteSkill(id) {
    if (!confirm("Are you sure you want to delete this skill?")) return;
    try {
        const res = await fetchWithAuth(`/skills/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Skill deleted successfully", "success");
            loadSkills();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete skill", "error");
    }
}

function evaluateProjectQuality(project) {
    const desc = (project.description || '').trim();
    const tech = (project.technologies || project.tech_stack || '').trim();
    const descLower = desc.toLowerCase();

    const genericPhrases = [
        "public github repository",
        "0 stars",
        "open source project",
        "solved leetcode problems",
        "this repo contains",
        "practice set",
        "practice repository"
    ];

    const isGeneric = genericPhrases.some(p => descLower.includes(p));

    if (!desc) {
        return {
            level: "weak",
            score: 20,
            badge: '<span class="badge badge-weak">🔴 Needs Description</span>',
            tip: '💡 Add 2-3 sentences explaining what you built, architecture, and key results so AI can write strong resume bullets.'
        };
    }

    if (isGeneric || desc.length < 35) {
        return {
            level: "weak",
            score: 35,
            badge: '<span class="badge badge-weak">🔴 Weak Explanation</span>',
            tip: '💡 Description is short or generic. Click Edit to detail your role, architecture, and measurable results.'
        };
    }

    if (desc.length < 90 || !tech) {
        return {
            level: "medium",
            score: 65,
            badge: '<span class="badge badge-medium">🟡 Moderate Detail</span>',
            tip: '💡 Good start! Adding tech stack & measurable outcomes will improve AI tailoring for resumes.'
        };
    }

    return {
        level: "strong",
        score: 95,
        badge: '<span class="badge badge-strong">🟢 AI Ready</span>',
        tip: ''
    };
}

// 3. Projects Management
async function loadProjects() {
    showSkeletons("projects-list");
    try {
        const res = await fetchWithAuth("/projects/");
        const rawProjects = await res.json();
        const listDiv = document.getElementById("projects-list");

        if (!rawProjects || rawProjects.length === 0) {
            renderEmptyState("projects-list", "No projects added yet", "Showcase your portfolio and open-source projects.", "folder-open");
            return;
        }

        // Deduplicate projects by title
        const seen = new Set();
        const projects = [];
        for (const p of rawProjects) {
            const cleanTitle = (p.title || '').trim().toLowerCase();
            if (cleanTitle && !seen.has(cleanTitle)) {
                seen.add(cleanTitle);
                projects.push(p);
            }
        }

        let weakCount = 0;
        const cardsHtml = projects.map(p => {
            const qual = evaluateProjectQuality(p);
            if (qual.level === 'weak') weakCount++;
            return `
                <div class="card-item ${qual.level === 'weak' ? 'card-border-weak' : ''}">
                    <div class="card-header">
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <h4>${escapeHtml(p.title)}</h4>
                            ${qual.badge}
                        </div>
                        <div class="card-header-actions">
                            <button class="card-edit-btn" onclick='openEditModal("project", ${JSON.stringify(p).replace(/'/g, "&apos;")})'><i data-lucide="pencil"></i> Edit</button>
                            <button class="card-delete-btn" onclick="deleteProject(${p.id})"><i data-lucide="trash-2"></i> Delete</button>
                        </div>
                    </div>
                    ${p.technologies ? `<p><strong>Tech:</strong> ${escapeHtml(p.technologies)}</p>` : ''}
                    ${p.start_date || p.end_date ? `<p class="date-text">${escapeHtml(p.start_date || '')} - ${escapeHtml(p.end_date || '')}</p>` : ''}
                    ${p.description ? `<p>${escapeHtml(p.description)}</p>` : ''}
                    ${qual.tip ? `<p class="quality-tip-text">${qual.tip}</p>` : ''}
                    ${p.link ? `<p><a href="${escapeHtml(p.link)}" target="_blank" class="card-link">View Project ↗</a></p>` : ''}
                </div>
            `;
        }).join("");

        const bannerHtml = weakCount > 0 ? `
            <div class="quality-alert-banner">
                <i data-lucide="alert-triangle"></i>
                <div>
                    <strong>AI Optimization Rating Notice (${weakCount} project${weakCount > 1 ? 's' : ''} need more detail):</strong>
                    <p style="margin: 3px 0 0 0; font-size: 13px; color: #e2e8f0;">
                        Projects with short or generic descriptions prevent the AI from generating high-impact resume bullet points.
                        Click <strong>Edit</strong> on weak projects to describe key features and technologies!
                    </p>
                </div>
            </div>
        ` : '';

        listDiv.innerHTML = bannerHtml + cardsHtml;
        refreshIcons();
    } catch (err) {
        renderEmptyState("projects-list", "Error loading projects", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteProject(id) {
    if (!confirm("Delete project?")) return;
    try {
        const res = await fetchWithAuth(`/projects/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Project deleted successfully", "success");
            loadProjects();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete project", "error");
    }
}

// 4. Experience Management
async function loadExperience() {
    showSkeletons("experience-list");
    try {
        const res = await fetchWithAuth("/experience/");
        const exps = await res.json();
        const listDiv = document.getElementById("experience-list");
        if (!exps || exps.length === 0) {
            renderEmptyState("experience-list", "No work experience added yet", "Add your past roles, internships, and work contributions.", "briefcase");
            return;
        }
        listDiv.innerHTML = exps.map(e => `
            <div class="card-item">
                <div class="card-header">
                    <h4>${escapeHtml(e.role)} @ ${escapeHtml(e.company)}</h4>
                    <div class="card-header-actions">
                        <button class="card-edit-btn" onclick='openEditModal("experience", ${JSON.stringify(e).replace(/'/g, "&apos;")})'><i data-lucide="pencil"></i> Edit</button>
                        <button class="card-delete-btn" onclick="deleteExperience(${e.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                <p class="date-text">${escapeHtml(e.start_date || '')} - ${e.is_current ? 'Present' : escapeHtml(e.end_date || '')}</p>
                ${e.description ? `<p>${escapeHtml(e.description)}</p>` : ''}
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("experience-list", "Error loading experience", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteExperience(id) {
    if (!confirm("Delete experience entry?")) return;
    try {
        const res = await fetchWithAuth(`/experience/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Experience entry deleted", "success");
            loadExperience();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete experience", "error");
    }
}

// 5. Education Management
async function loadEducation() {
    showSkeletons("education-list");
    try {
        const res = await fetchWithAuth("/education/");
        const edus = await res.json();
        const listDiv = document.getElementById("education-list");
        if (!edus || edus.length === 0) {
            renderEmptyState("education-list", "No education history added", "Add your academic degrees and background.", "graduation-cap");
            return;
        }
        listDiv.innerHTML = edus.map(e => `
            <div class="card-item">
                <div class="card-header">
                    <h4>${escapeHtml(e.degree)} in ${escapeHtml(e.field_of_study || '')}</h4>
                    <div class="card-header-actions">
                        <button class="card-edit-btn" onclick='openEditModal("education", ${JSON.stringify(e).replace(/'/g, "&apos;")})'><i data-lucide="pencil"></i> Edit</button>
                        <button class="card-delete-btn" onclick="deleteEducation(${e.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                <p><strong>${escapeHtml(e.institution)}</strong></p>
                <p class="date-text">${escapeHtml(e.start_year || '')} - ${escapeHtml(e.end_year || '')} ${e.gpa ? `| GPA: ${escapeHtml(e.gpa)}` : ''}</p>
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("education-list", "Error loading education", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteEducation(id) {
    if (!confirm("Delete education entry?")) return;
    try {
        const res = await fetchWithAuth(`/education/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Education entry deleted", "success");
            loadEducation();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete education", "error");
    }
}

// 6. Achievements Management
async function loadAchievements() {
    showSkeletons("achievements-list");
    try {
        const res = await fetchWithAuth("/achievements/");
        const achs = await res.json();
        const listDiv = document.getElementById("achievements-list");
        if (!achs || achs.length === 0) {
            renderEmptyState("achievements-list", "No achievements added yet", "List certifications, hackathons, or awards.", "award");
            return;
        }
        listDiv.innerHTML = achs.map(a => `
            <div class="card-item">
                <div class="card-header">
                    <h4><i data-lucide="award" style="color: var(--accent-amber); vertical-align: middle;"></i> ${escapeHtml(a.title)}</h4>
                    <div class="card-header-actions">
                        <button class="card-edit-btn" onclick='openEditModal("achievement", ${JSON.stringify(a).replace(/'/g, "&apos;")})'><i data-lucide="pencil"></i> Edit</button>
                        <button class="card-delete-btn" onclick="deleteAchievement(${a.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                ${a.date ? `<p class="date-text">${escapeHtml(a.date)}</p>` : ''}
                ${a.description ? `<p>${escapeHtml(a.description)}</p>` : ''}
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("achievements-list", "Error loading achievements", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteAchievement(id) {
    if (!confirm("Delete achievement?")) return;
    try {
        const res = await fetchWithAuth(`/achievements/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Achievement deleted", "success");
            loadAchievements();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete achievement", "error");
    }
}

// 7. Resume Templates Management
async function loadTemplates() {
    showSkeletons("templates-list");
    try {
        const res = await fetchWithAuth("/templates/");
        const tpls = await res.json();
        const listDiv = document.getElementById("templates-list");
        if (!tpls || tpls.length === 0) {
            renderEmptyState("templates-list", "No custom templates created", "Standard ATS template is used by default.", "layout");
            return;
        }
        listDiv.innerHTML = tpls.map(t => `
            <div class="card-item">
                <div class="card-header">
                    <h4>${escapeHtml(t.name)} ${t.is_default ? '<span class="badge badge-success">Default</span>' : ''}</h4>
                    <div class="card-header-actions">
                        <button class="card-delete-btn" onclick="deleteTemplate(${t.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                <pre class="code-preview">${escapeHtml(t.content)}</pre>
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("templates-list", "Error loading templates", "Could not connect to backend server.", "alert-triangle");
    }
}

async function deleteTemplate(id) {
    if (!confirm("Delete template?")) return;
    try {
        const res = await fetchWithAuth(`/templates/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Template deleted", "success");
            loadTemplates();
        }
    } catch (err) {
        showToast("Failed to delete template", "error");
    }
}

async function loadTemplateSelectOptions() {
    const select = document.getElementById("gen-template-select");
    try {
        const res = await fetchWithAuth("/templates/");
        const tpls = await res.json();
        select.innerHTML = '<option value="">Use Standard ATS Layout</option>';
        if (tpls && tpls.length > 0) {
            tpls.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.textContent = `${t.name} ${t.is_default ? '(Default)' : ''}`;
                select.appendChild(opt);
            });
        }
    } catch (err) {
        console.warn("Could not fetch templates for builder select");
    }
}

// ─── REUSABLE INLINE EDIT MODAL ───
function openEditModal(type, item) {
    activeEditItem = { type, id: item.id };
    const titleLabel = document.getElementById("edit-modal-title");
    const fieldsDiv = document.getElementById("edit-modal-fields");

    titleLabel.textContent = `Edit ${type.charAt(0).toUpperCase() + type.slice(1)}`;

    let html = "";
    if (type === "skill") {
        html = `
            <input type="text" id="edit-skill-name" value="${escapeHtml(item.name || '')}" placeholder="Skill Name" required>
            <input type="text" id="edit-skill-cat" value="${escapeHtml(item.category || '')}" placeholder="Category">
            <select id="edit-skill-prof">
                <option value="Beginner" ${item.proficiency === 'Beginner' ? 'selected' : ''}>Beginner</option>
                <option value="Intermediate" ${item.proficiency === 'Intermediate' ? 'selected' : ''}>Intermediate</option>
                <option value="Advanced" ${item.proficiency === 'Advanced' ? 'selected' : ''}>Advanced</option>
                <option value="Expert" ${item.proficiency === 'Expert' ? 'selected' : ''}>Expert</option>
            </select>
        `;
    } else if (type === "project") {
        html = `
            <input type="text" id="edit-proj-title" value="${escapeHtml(item.title || '')}" placeholder="Project Title" required>
            <input type="text" id="edit-proj-tech" value="${escapeHtml(item.technologies || '')}" placeholder="Technologies">
            <input type="url" id="edit-proj-link" value="${escapeHtml(item.link || '')}" placeholder="URL">
            <div class="form-row">
                <input type="text" id="edit-proj-start" value="${escapeHtml(item.start_date || '')}" placeholder="Start Date">
                <input type="text" id="edit-proj-end" value="${escapeHtml(item.end_date || '')}" placeholder="End Date">
            </div>
            <textarea id="edit-proj-desc" rows="3" placeholder="Description">${escapeHtml(item.description || '')}</textarea>
        `;
    } else if (type === "experience") {
        html = `
            <div class="form-row">
                <input type="text" id="edit-exp-company" value="${escapeHtml(item.company || '')}" placeholder="Company" required>
                <input type="text" id="edit-exp-role" value="${escapeHtml(item.role || '')}" placeholder="Role" required>
            </div>
            <div class="form-row">
                <input type="text" id="edit-exp-start" value="${escapeHtml(item.start_date || '')}" placeholder="Start Date">
                <input type="text" id="edit-exp-end" value="${escapeHtml(item.end_date || '')}" placeholder="End Date">
            </div>
            <label class="checkbox-label">
                <input type="checkbox" id="edit-exp-current" ${item.is_current ? 'checked' : ''}> Currently Working Here
            </label>
            <textarea id="edit-exp-desc" rows="3" placeholder="Description">${escapeHtml(item.description || '')}</textarea>
        `;
    } else if (type === "education") {
        html = `
            <div class="form-row">
                <input type="text" id="edit-edu-inst" value="${escapeHtml(item.institution || '')}" placeholder="Institution" required>
                <input type="text" id="edit-edu-degree" value="${escapeHtml(item.degree || '')}" placeholder="Degree" required>
            </div>
            <div class="form-row">
                <input type="text" id="edit-edu-field" value="${escapeHtml(item.field_of_study || '')}" placeholder="Field of Study">
                <input type="text" id="edit-edu-gpa" value="${escapeHtml(item.gpa || '')}" placeholder="GPA">
            </div>
            <div class="form-row">
                <input type="text" id="edit-edu-start" value="${escapeHtml(item.start_year || '')}" placeholder="Start Year">
                <input type="text" id="edit-edu-end" value="${escapeHtml(item.end_year || '')}" placeholder="End Year">
            </div>
        `;
    } else if (type === "achievement") {
        html = `
            <input type="text" id="edit-ach-title" value="${escapeHtml(item.title || '')}" placeholder="Title" required>
            <input type="text" id="edit-ach-date" value="${escapeHtml(item.date || '')}" placeholder="Date">
            <textarea id="edit-ach-desc" rows="2" placeholder="Description">${escapeHtml(item.description || '')}</textarea>
        `;
    }

    fieldsDiv.innerHTML = html;
    document.getElementById("modal-edit-item").style.display = "flex";
}

function closeEditModal() {
    document.getElementById("modal-edit-item").style.display = "none";
    activeEditItem = null;
}

// Save Edit Form Handler
document.addEventListener("DOMContentLoaded", () => {
    const editForm = document.getElementById("form-edit-item");
    if (editForm) {
        editForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (!activeEditItem) return;

            const { type, id } = activeEditItem;
            let body = {};
            let endpoint = `/${type}s/${id}`;
            if (type === "experience") endpoint = `/experience/${id}`;

            if (type === "skill") {
                body = {
                    name: document.getElementById("edit-skill-name").value.trim(),
                    category: document.getElementById("edit-skill-cat").value.trim(),
                    proficiency: document.getElementById("edit-skill-prof").value
                };
            } else if (type === "project") {
                body = {
                    title: document.getElementById("edit-proj-title").value.trim(),
                    technologies: document.getElementById("edit-proj-tech").value.trim(),
                    link: document.getElementById("edit-proj-link").value.trim(),
                    start_date: document.getElementById("edit-proj-start").value.trim(),
                    end_date: document.getElementById("edit-proj-end").value.trim(),
                    description: document.getElementById("edit-proj-desc").value.trim()
                };
            } else if (type === "experience") {
                body = {
                    company: document.getElementById("edit-exp-company").value.trim(),
                    role: document.getElementById("edit-exp-role").value.trim(),
                    start_date: document.getElementById("edit-exp-start").value.trim(),
                    end_date: document.getElementById("edit-exp-end").value.trim(),
                    is_current: document.getElementById("edit-exp-current").checked,
                    description: document.getElementById("edit-exp-desc").value.trim()
                };
            } else if (type === "education") {
                body = {
                    institution: document.getElementById("edit-edu-inst").value.trim(),
                    degree: document.getElementById("edit-edu-degree").value.trim(),
                    field_of_study: document.getElementById("edit-edu-field").value.trim(),
                    gpa: document.getElementById("edit-edu-gpa").value.trim(),
                    start_year: document.getElementById("edit-edu-start").value.trim(),
                    end_year: document.getElementById("edit-edu-end").value.trim()
                };
            } else if (type === "achievement") {
                body = {
                    title: document.getElementById("edit-ach-title").value.trim(),
                    date: document.getElementById("edit-ach-date").value.trim(),
                    description: document.getElementById("edit-ach-desc").value.trim()
                };
            }

            try {
                const res = await fetchWithAuth(endpoint, { method: "PUT", body });
                if (res.ok) {
                    showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} updated!`, "success");
                    closeEditModal();
                    if (type === "skill") loadSkills();
                    if (type === "project") loadProjects();
                    if (type === "experience") loadExperience();
                    if (type === "education") loadEducation();
                    if (type === "achievement") loadAchievements();
                    loadDashboardSummary();
                } else {
                    showToast("Failed to update item", "error");
                }
            } catch (err) {
                showToast("Network error updating item", "error");
            }
        });
    }
});

// 8. Resume Generation & Job Analysis
async function analyzeJobDescription() {
    const job_description = document.getElementById("gen-job-desc").value.trim();
    const job_url = document.getElementById("gen-job-url").value.trim();

    if (!job_description && !job_url) {
        return showToast("Please enter either a Job Description or a Job URL", "error");
    }

    const tagsContainer = document.getElementById("keywords-tags");
    const box = document.getElementById("keywords-container");
    box.style.display = "block";
    tagsContainer.innerHTML = "<em>Analyzing keywords...</em>";

    try {
        const res = await fetchWithAuth("/resume/analyze-jd", {
            method: "POST",
            body: { job_description, job_url }
        });

        const data = await res.json();
        if (res.ok) {
            if (data.keywords && data.keywords.length > 0) {
                tagsContainer.innerHTML = data.keywords.map(k => `<span class="tag-chip">${escapeHtml(k)}</span>`).join("");
            } else {
                tagsContainer.innerHTML = "<span>No specific keywords extracted.</span>";
            }
        } else {
            tagsContainer.innerHTML = `<span class="error-text">${escapeHtml(data.detail || 'Analysis failed')}</span>`;
        }
    } catch (err) {
        tagsContainer.innerHTML = `<span class="error-text">Failed to analyze Job Description</span>`;
    }
}

function renderFormattedResume(content, targetId = "formatted-resume-preview") {
    const container = document.getElementById(targetId);
    if (!container) return;
    if (!content || !content.trim()) {
        container.innerHTML = `<p style="color: var(--text-muted); font-style: italic;">Submit job details on the left to generate your personalized resume preview here.</p>`;
        return;
    }

    let html = escapeHtml(content);

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h4 class="resume-preview-h4">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 class="resume-preview-h3">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 class="resume-preview-h2">$1</h2>');

    // Bold & Italic
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // Horizontal rule
    html = html.replace(/^---$/gim, '<hr class="resume-preview-hr">');

    // Lists & paragraphs
    const lines = html.split("\n");
    let inList = false;
    const result = [];

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        if (line.match(/^[\-\*•]\s+/)) {
            const itemText = line.replace(/^[\-\*•]\s+/, "");
            if (!inList) {
                inList = true;
                result.push('<ul class="resume-preview-ul">');
            }
            result.push(`<li>${itemText}</li>`);
        } else {
            if (inList) {
                inList = false;
                result.push('</ul>');
            }
            if (line.length > 0) {
                if (line.startsWith("<h") || line.startsWith("<hr")) {
                    result.push(line);
                } else {
                    result.push(`<p class="resume-preview-p">${line}</p>`);
                }
            }
        }
    }
    if (inList) result.push('</ul>');

    container.innerHTML = result.join("\n");
}

let isRawViewMode = false;
function toggleResumeViewMode() {
    const formattedCard = document.getElementById("formatted-resume-preview");
    const rawBox = document.getElementById("resume-output-text");
    const toggleBtn = document.getElementById("btn-toggle-view");

    if (!formattedCard || !rawBox || !toggleBtn) return;

    if (isRawViewMode) {
        formattedCard.style.display = "block";
        rawBox.style.display = "none";
        toggleBtn.innerHTML = `<i data-lucide="code"></i> Raw Code`;
        isRawViewMode = false;
    } else {
        formattedCard.style.display = "none";
        rawBox.style.display = "block";
        toggleBtn.innerHTML = `<i data-lucide="eye"></i> Formatted View`;
        isRawViewMode = true;
    }
    refreshIcons();
}

async function generatePersonalizedResume(e) {
    e.preventDefault();

    const job_title = document.getElementById("gen-job-title").value.trim();
    const job_description = document.getElementById("gen-job-desc").value.trim();
    const job_url = document.getElementById("gen-job-url").value.trim();
    const template_id_val = document.getElementById("gen-template-select").value;
    const template_id = template_id_val ? parseInt(template_id_val) : null;

    if (!job_description && !job_url) {
        return showToast("Please enter a Job Description or Job Posting URL", "error");
    }

    const loader = document.getElementById("builder-loader");
    const formattedCard = document.getElementById("formatted-resume-preview");
    const outputBox = document.getElementById("resume-output-text");
    const exportPdfBtn = document.getElementById("btn-export-pdf");
    const copyResumeBtn = document.getElementById("btn-copy-resume");
    const regenerateBtn = document.getElementById("btn-regenerate-resume");
    const shareBtn = document.getElementById("btn-share-resume");
    const txtBtn = document.getElementById("btn-export-txt");
    const mdBtn = document.getElementById("btn-export-md");
    const toggleViewBtn = document.getElementById("btn-toggle-view");
    const statsBar = document.getElementById("resume-stats-bar");

    loader.style.display = "block";
    outputBox.style.display = "none";
    if (formattedCard) formattedCard.style.display = "none";
    if (exportPdfBtn) exportPdfBtn.style.display = "none";
    if (copyResumeBtn) copyResumeBtn.style.display = "none";
    if (regenerateBtn) regenerateBtn.style.display = "none";
    if (shareBtn) shareBtn.style.display = "none";
    if (txtBtn) txtBtn.style.display = "none";
    if (mdBtn) mdBtn.style.display = "none";
    if (toggleViewBtn) toggleViewBtn.style.display = "none";
    if (statsBar) statsBar.style.display = "none";

    try {
        const res = await fetchWithAuth("/resume/generate", {
            method: "POST",
            body: {
                job_title,
                job_description,
                job_url,
                template_id
            }
        });

        const data = await res.json();
        loader.style.display = "none";

        if (res.ok) {
            showToast("Resume tailored successfully!", "success");
            outputBox.textContent = data.content;
            renderFormattedResume(data.content, "formatted-resume-preview");
            
            if (formattedCard) formattedCard.style.display = "block";
            currentGeneratedResumeId = data.id;
            
            // Calculate stats
            const text = data.content || "";
            const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
            const charCount = text.length;

            if (statsBar) {
                statsBar.style.display = "flex";
                document.getElementById("stat-word-count").textContent = `${wordCount} words`;
                document.getElementById("stat-char-count").textContent = `${charCount} chars`;
            }

            if (exportPdfBtn) {
                exportPdfBtn.style.display = "inline-block";
                exportPdfBtn.onclick = () => exportResumePDF(data.id);
            }
            if (copyResumeBtn) {
                copyResumeBtn.style.display = "inline-block";
                copyResumeBtn.onclick = () => copyTextToClipboard(data.content);
            }
            if (regenerateBtn) regenerateBtn.style.display = "inline-block";
            if (shareBtn) shareBtn.style.display = "inline-block";
            if (txtBtn) txtBtn.style.display = "inline-block";
            if (mdBtn) mdBtn.style.display = "inline-block";
            if (toggleViewBtn) toggleViewBtn.style.display = "inline-block";

            loadDashboardSummary();
            refreshIcons();
        } else {
            outputBox.style.display = "block";
            outputBox.textContent = "Error: " + (data.detail || "Resume generation failed");
            if (data.detail && data.detail.includes("Hugging Face API key")) {
                showToast("Hugging Face API key missing. Go to HF API Key settings to configure.", "error");
            }
        }
    } catch (err) {
        loader.style.display = "none";
        outputBox.style.display = "block";
        outputBox.textContent = "Network error. Make sure the backend server is running.";
    }
}

async function shareResumeLink() {
    if (!currentGeneratedResumeId) return showToast("No resume selected to share", "error");
    try {
        const res = await fetchWithAuth(`/resume/${currentGeneratedResumeId}/share`, { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            const fullUrl = `${window.location.origin}${data.share_url}`;
            await navigator.clipboard.writeText(fullUrl);
            showToast("Public share link copied to clipboard!", "success");
        } else {
            showToast("Failed to generate share link", "error");
        }
    } catch (err) {
        showToast("Error generating share link", "error");
    }
}

function exportResumeTXT() {
    if (!currentGeneratedResumeId) return showToast("No resume selected", "error");
    const a = document.createElement("a");
    const text = document.getElementById("resume-output-text").textContent;
    const blob = new Blob([text], { type: "text/plain" });
    a.href = URL.createObjectURL(blob);
    a.download = `Reliefer_Resume_${currentGeneratedResumeId}.txt`;
    a.click();
    showToast("Downloaded TXT resume!", "success");
}

function exportResumeMD() {
    if (!currentGeneratedResumeId) return showToast("No resume selected", "error");
    const a = document.createElement("a");
    const text = document.getElementById("resume-output-text").textContent;
    const blob = new Blob([text], { type: "text/markdown" });
    a.href = URL.createObjectURL(blob);
    a.download = `Reliefer_Resume_${currentGeneratedResumeId}.md`;
    a.click();
    showToast("Downloaded Markdown resume!", "success");
}

function exportResumePDF(resumeId) {
    if (!resumeId) return showToast("No resume selected for PDF export", "error");
    
    fetchWithAuth(`/resume/${resumeId}/export-pdf`)
        .then(res => {
            if (!res.ok) throw new Error("Export failed");
            return res.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `Reliefer_Resume_${resumeId}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            showToast("PDF exported successfully!", "success");
        })
        .catch(err => {
            showToast("Failed to download PDF", "error");
        });
}

// 9. Resume History
async function loadResumeHistory() {
    showSkeletons("history-list");

    try {
        const res = await fetchWithAuth("/resume/history");
        const list = await res.json();
        const historyList = document.getElementById("history-list");

        if (!list || list.length === 0) {
            renderEmptyState("history-list", "No resume history available", "Tailor your first resume using the AI Resume Builder!", "file-text");
            return;
        }

        historyList.innerHTML = list.map(item => `
            <div class="card-item">
                <div class="card-header">
                    <h4>${escapeHtml(item.job_title || 'Tailored Resume')} (v${item.version})</h4>
                    <div class="btn-group-sm">
                        <button class="secondary-btn-sm" onclick="previewResumeHistory(${item.id})"><i data-lucide="eye"></i> Preview</button>
                        <button class="primary-btn-sm" onclick="exportResumePDF(${item.id})"><i data-lucide="download"></i> PDF</button>
                        <button class="delete-btn" onclick="deleteResumeHistory(${item.id})"><i data-lucide="trash-2"></i> Delete</button>
                    </div>
                </div>
                <p class="date-text">Created: ${new Date(item.created_at).toLocaleString()}</p>
                ${item.extracted_keywords ? `<p><strong>Keywords:</strong> ${escapeHtml(item.extracted_keywords)}</p>` : ''}
            </div>
        `).join("");
        refreshIcons();
    } catch (err) {
        renderEmptyState("history-list", "Error loading resume history", "Could not connect to backend server.", "alert-triangle");
    }
}

async function previewResumeHistory(id) {
    try {
        const res = await fetchWithAuth(`/resume/${id}`);
        const data = await res.json();
        if (res.ok) {
            document.getElementById("modal-resume-title").textContent = `${data.job_title || 'Tailored Resume'} (v${data.version})`;
            renderFormattedResume(data.content, "modal-resume-body");
            document.getElementById("modal-download-pdf-btn").onclick = () => exportResumePDF(id);
            document.getElementById("modal-resume-view").style.display = "flex";
            refreshIcons();
        }
    } catch (err) {
        showToast("Failed to fetch resume details", "error");
    }
}

function closeModal() {
    document.getElementById("modal-resume-view").style.display = "none";
}

async function deleteResumeHistory(id) {
    if (!confirm("Delete this generated resume?")) return;
    try {
        const res = await fetchWithAuth(`/resume/${id}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Resume record deleted", "success");
            loadResumeHistory();
            loadDashboardSummary();
        }
    } catch (err) {
        showToast("Failed to delete resume history", "error");
    }
}

// 10. Hugging Face API Key Setup
async function checkKeyStatus() {
    const statusLabel = document.getElementById("settings-key-status");
    try {
        const res = await fetchWithAuth("/me");
        if (res.ok) {
            const data = await res.json();
            if (data.huggingface_api_key) {
                statusLabel.className = "badge badge-success";
                statusLabel.textContent = "✓ Configured & Active";
            } else {
                statusLabel.className = "badge badge-warning";
                statusLabel.textContent = "! Not Configured";
            }
        }
    } catch (err) {}
}

async function saveHuggingFaceKey(e) {
    e.preventDefault();
    const apiKey = document.getElementById("hf-api-key").value.trim();
    if (!apiKey) return showToast("Please enter an API key", "error");

    try {
        const res = await fetchWithAuth("/me/huggingface-key", {
            method: "PUT",
            body: { huggingface_api_key: apiKey }
        });

        if (res.ok) {
            showToast("Hugging Face API key saved successfully!", "success");
            document.getElementById("hf-api-key").value = "";
            checkKeyStatus();
            loadDashboardSummary();
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to save key", "error");
        }
    } catch (err) {
        showToast("Failed to save API key", "error");
    }
}

// ─── FORM LISTENERS SETUP ───
function setupFormListeners() {
    // Add Skill
    const formSkill = document.getElementById("form-add-skill");
    if (formSkill) {
        formSkill.addEventListener("submit", async (e) => {
            e.preventDefault();
            const name = document.getElementById("skill-name").value.trim();
            const category = document.getElementById("skill-category").value.trim();
            const proficiency = document.getElementById("skill-proficiency").value;
            const res = await fetchWithAuth("/skills/", { method: "POST", body: { name, category, proficiency } });
            if (res.ok) {
                showToast("Skill added!", "success");
                formSkill.reset();
                loadSkills();
                loadDashboardSummary();
            }
        });
    }

    // Add Project
    const formProj = document.getElementById("form-add-project");
    if (formProj) {
        formProj.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                title: document.getElementById("proj-title").value.trim(),
                technologies: document.getElementById("proj-tech").value.trim(),
                link: document.getElementById("proj-link").value.trim(),
                start_date: document.getElementById("proj-start").value.trim(),
                end_date: document.getElementById("proj-end").value.trim(),
                description: document.getElementById("proj-desc").value.trim()
            };
            const res = await fetchWithAuth("/projects/", { method: "POST", body });
            if (res.ok) {
                showToast("Project added!", "success");
                formProj.reset();
                loadProjects();
                loadDashboardSummary();
            }
        });
    }

    // Add Experience
    const formExp = document.getElementById("form-add-exp");
    if (formExp) {
        formExp.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                company: document.getElementById("exp-company").value.trim(),
                role: document.getElementById("exp-role").value.trim(),
                start_date: document.getElementById("exp-start").value.trim(),
                end_date: document.getElementById("exp-end").value.trim(),
                is_current: document.getElementById("exp-current").checked,
                description: document.getElementById("exp-desc").value.trim()
            };
            const res = await fetchWithAuth("/experience/", { method: "POST", body });
            if (res.ok) {
                showToast("Experience entry added!", "success");
                formExp.reset();
                loadExperience();
                loadDashboardSummary();
            }
        });
    }

    // Add Education
    const formEdu = document.getElementById("form-add-edu");
    if (formEdu) {
        formEdu.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                institution: document.getElementById("edu-institution").value.trim(),
                degree: document.getElementById("edu-degree").value.trim(),
                field_of_study: document.getElementById("edu-field").value.trim(),
                gpa: document.getElementById("edu-gpa").value.trim(),
                start_year: document.getElementById("edu-start").value.trim(),
                end_year: document.getElementById("edu-end").value.trim()
            };
            const res = await fetchWithAuth("/education/", { method: "POST", body });
            if (res.ok) {
                showToast("Education entry added!", "success");
                formEdu.reset();
                loadEducation();
                loadDashboardSummary();
            }
        });
    }

    // Add Achievement
    const formAch = document.getElementById("form-add-achievement");
    if (formAch) {
        formAch.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                title: document.getElementById("ach-title").value.trim(),
                date: document.getElementById("ach-date").value.trim(),
                description: document.getElementById("ach-desc").value.trim()
            };
            const res = await fetchWithAuth("/achievements/", { method: "POST", body });
            if (res.ok) {
                showToast("Achievement added!", "success");
                formAch.reset();
                loadAchievements();
                loadDashboardSummary();
            }
        });
    }

    // Add Template
    const formTpl = document.getElementById("form-add-template");
    if (formTpl) {
        formTpl.addEventListener("submit", async (e) => {
            e.preventDefault();
            const body = {
                name: document.getElementById("tpl-name").value.trim(),
                content: document.getElementById("tpl-content").value.trim(),
                is_default: document.getElementById("tpl-default").checked
            };
            const res = await fetchWithAuth("/templates/", { method: "POST", body });
            if (res.ok) {
                showToast("Template added!", "success");
                formTpl.reset();
                loadTemplates();
            }
        });
    }

    // Job Analysis Button
    const btnAnalyze = document.getElementById("btn-analyze-jd");
    if (btnAnalyze) {
        btnAnalyze.addEventListener("click", analyzeJobDescription);
    }

    // Resume Generator Form
    const formGen = document.getElementById("form-generate-resume");
    if (formGen) {
        formGen.addEventListener("submit", generatePersonalizedResume);
    }

    // Save HF API Key Form
    const formHfKey = document.getElementById("form-save-hf-key");
    if (formHfKey) {
        formHfKey.addEventListener("submit", saveHuggingFaceKey);
    }

    // Mobile Toggle
    const mobileToggle = document.getElementById("mobile-toggle");
    const navLinks = document.getElementById("nav-links");
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener("click", () => {
            navLinks.classList.toggle("show");
        });
    }
}

function copyTextToClipboard(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        showToast("Resume content copied to clipboard!", "success");
    }).catch(() => {
        showToast("Failed to copy text", "error");
    });
}

// Utility: HTML Escaping
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ─── RESUME PARSING & UPLOAD (PHASE 2) ───
let currentParsedResumeData = null;

function focusResumeUpload() {
    const dropzone = document.getElementById("dropzone-container");
    if (dropzone) {
        dropzone.scrollIntoView({ behavior: 'smooth' });
    }
}

function triggerFileInput() {
    const input = document.getElementById("resume-file-input");
    if (input) input.click();
}

function triggerObFileInput() {
    const input = document.getElementById("ob-resume-file-input");
    if (input) input.click();
}

function togglePasteResumeBox() {
    const box = document.getElementById("paste-resume-container");
    if (box) {
        box.style.display = box.style.display === "none" ? "block" : "none";
    }
}

async function handleFileUpload(files) {
    if (!files || files.length === 0) return;
    const file = files[0];

    // Validate file size (max 10 MB)
    if (file.size > 10 * 1024 * 1024) {
        showToast("File too large. Max 10 MB allowed.", "error");
        return;
    }

    // Validate file type
    const allowed = [".pdf", ".docx", ".doc", ".txt"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!allowed.includes(ext)) {
        showToast("Unsupported file type. Use PDF, DOCX, DOC, or TXT.", "error");
        return;
    }

    // Check token before attempting
    if (!userData || !userData.access_token) {
        showToast("You must be logged in to upload a resume.", "error");
        setTimeout(redirectToLogin, 1500);
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    showToast(`Uploading & parsing ${file.name}...`, "info");

    let response;
    try {
        response = await fetch(`${API_BASE_URL}/resume/upload`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${userData.access_token}`
            },
            body: formData
        });
    } catch (networkErr) {
        console.error("Resume upload network error:", networkErr);
        showToast(`Upload failed — could not reach server: ${networkErr.message}`, "error");
        return;
    }

    if (response.status === 401) {
        showToast("Session expired. Please log in again.", "error");
        setTimeout(redirectToLogin, 1500);
        return;
    }

    if (!response.ok) {
        let errMsg = `Server error (${response.status})`;
        try {
            const errJson = await response.json();
            errMsg = errJson.detail || errMsg;
        } catch (_) {
            try { errMsg = await response.text() || errMsg; } catch (_) {}
        }
        console.error("Resume upload server error:", response.status, errMsg);
        showToast(errMsg, "error");
        return;
    }

    try {
        const data = await response.json();
        showToast("Resume uploaded and parsed successfully!", "success");
        openResumeReviewModal(data);
    } catch (parseErr) {
        console.error("Failed to parse server response:", parseErr);
        showToast("Upload succeeded but could not read response. Please try again.", "error");
    }
}

async function handlePasteResume(event) {
    event.preventDefault();
    const textInput = document.getElementById("paste-resume-text");
    if (!textInput || !textInput.value.trim()) return;

    showToast("Parsing pasted resume text...", "info");

    try {
        const res = await fetchWithAuth("/resume/parse-text", {
            method: "POST",
            body: { text: textInput.value.trim() }
        });

        if (res.ok) {
            const data = await res.json();
            showToast("Resume text parsed!", "success");
            togglePasteResumeBox();
            textInput.value = "";
            openResumeReviewModal(data);
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to parse resume text.", "error");
        }
    } catch (err) {
        showToast("Network error parsing resume text.", "error");
    }
}

function openResumeReviewModal(data) {
    currentParsedResumeData = data;

    // 1. Skills
    const skillsList = document.getElementById("rev-skills-list");
    const skillsCount = document.getElementById("rev-skills-count");
    if (skillsList) {
        skillsCount.textContent = (data.skills || []).length;
        skillsList.innerHTML = (data.skills || []).map((s, idx) => `
            <span class="tag-chip">
                ${escapeHtml(s)}
                <i data-lucide="x" style="width: 12px; height: 12px; margin-left: 4px; cursor: pointer;" onclick="removeParsedSkill(${idx})"></i>
            </span>
        `).join("") || '<p class="placeholder-text">No skills detected.</p>';
    }

    // 2. Experience
    const expList = document.getElementById("rev-exp-list");
    const expCount = document.getElementById("rev-exp-count");
    if (expList) {
        expCount.textContent = (data.experience || []).length;
        expList.innerHTML = (data.experience || []).map(e => `
            <div class="review-item">
                <div class="review-item-title">${escapeHtml(e.role || 'Role')} @ ${escapeHtml(e.company || 'Company')}</div>
                <div class="review-item-sub">${escapeHtml(e.dates || '')}</div>
                <div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">${escapeHtml(e.description || '')}</div>
            </div>
        `).join("") || '<p class="placeholder-text">No work experience entries detected.</p>';
    }

    // 3. Education
    const eduList = document.getElementById("rev-edu-list");
    const eduCount = document.getElementById("rev-edu-count");
    if (eduList) {
        eduCount.textContent = (data.education || []).length;
        eduList.innerHTML = (data.education || []).map(ed => `
            <div class="review-item">
                <div class="review-item-title">${escapeHtml(ed.degree || 'Degree')}</div>
                <div class="review-item-sub">
                    ${escapeHtml(ed.institution || 'University')} 
                    (${escapeHtml(ed.year || '')}) 
                    ${ed.marks ? ` | Marks/GPA: ${escapeHtml(ed.marks)}` : ''}
                </div>
            </div>
        `).join("") || '<p class="placeholder-text">No education entries detected.</p>';
    }

    // 4. Projects
    const projList = document.getElementById("rev-proj-list");
    const projCount = document.getElementById("rev-proj-count");
    if (projList) {
        const rawProjs = data.projects || [];
        const seenP = new Set();
        const dedupedProjs = [];
        for (const p of rawProjs) {
            const nameKey = (p.title || p.name || '').trim().toLowerCase();
            if (nameKey && !seenP.has(nameKey)) {
                seenP.add(nameKey);
                dedupedProjs.push(p);
            }
        }
        data.projects = dedupedProjs;
        projCount.textContent = dedupedProjs.length;
        projList.innerHTML = dedupedProjs.map(p => {
            const qual = evaluateProjectQuality(p);
            return `
                <div class="review-item">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                        <div class="review-item-title">${escapeHtml(p.title || p.name || 'Project')}</div>
                        ${qual.badge}
                    </div>
                    <div class="review-item-sub">${escapeHtml(p.tech_stack || p.technologies || '')}</div>
                    <div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">${escapeHtml(p.description || '')}</div>
                </div>
            `;
        }).join("") || '<p class="placeholder-text">No project entries detected.</p>';
    }

    // 5. Achievements
    const achList = document.getElementById("rev-ach-list");
    const achCount = document.getElementById("rev-ach-count");
    if (achList) {
        achCount.textContent = (data.achievements || []).length;
        achList.innerHTML = (data.achievements || []).map(a => `
            <div class="review-item">
                <div class="review-item-title">${escapeHtml(a.title || 'Achievement')}</div>
                <div class="review-item-sub">${escapeHtml(a.date || '')}</div>
                <div style="font-size: 13px; color: #cbd5e1; margin-top: 4px;">${escapeHtml(a.description || '')}</div>
            </div>
        `).join("") || '<p class="placeholder-text">No achievements detected.</p>';
    }

    // 6. Other / Uncategorized Info
    const otherList = document.getElementById("rev-other-list");
    const otherCount = document.getElementById("rev-other-count");
    if (otherList) {
        otherCount.textContent = (data.other_info || []).length;
        otherList.innerHTML = (data.other_info || []).map(info => `
            <div class="review-item">
                <div style="font-size: 13px; color: #cbd5e1;">${escapeHtml(info)}</div>
            </div>
        `).join("") || '<p class="placeholder-text">No additional uncategorized information.</p>';
    }

    if (window.lucide) window.lucide.createIcons();
    document.getElementById("modal-resume-review").style.display = "flex";
}

function removeParsedSkill(index) {
    if (!currentParsedResumeData || !currentParsedResumeData.skills) return;
    currentParsedResumeData.skills.splice(index, 1);
    openResumeReviewModal(currentParsedResumeData);
}

function closeResumeReviewModal() {
    document.getElementById("modal-resume-review").style.display = "none";
    currentParsedResumeData = null;
}

async function confirmImportParsedResume() {
    if (!currentParsedResumeData) return;

    const btn = document.getElementById("btn-confirm-import");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = 'Importing...';
    }

    try {
        const res = await fetchWithAuth("/resume/import-parsed", {
            method: "POST",
            body: currentParsedResumeData
        });

        if (res.ok) {
            const resData = await res.json();
            const counts = resData.imported_counts || {};
            showToast(`Imported ${counts.skills || 0} skills, ${counts.experience || 0} work entries, ${counts.projects || 0} projects, and ${counts.achievements || 0} achievements!`, "success");
            closeResumeReviewModal();
            loadDashboardSummary();
            loadSkills();
            loadExperience();
            loadEducation();
            loadProjects();
            if (typeof loadAchievements === "function") loadAchievements();
        } else {
            showToast("Failed to import resume sections.", "error");
        }
    } catch (err) {
        console.error("Import error:", err);
        showToast("Error importing resume data.", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="check-circle"></i> Import to Master Profile';
            if (window.lucide) window.lucide.createIcons();
        }
    }
}

// Drag & drop event setup
document.addEventListener("DOMContentLoaded", () => {
    const dropzone = document.getElementById("dropzone-container");
    if (dropzone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('drag-over'), false);
        });

        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFileUpload(files);
        }, false);
    }
});

// ─── EXTERNAL PROFILE SCRAPING HANDLERS (PHASE 3) ───
async function importFromGitHub() {
    const input = document.getElementById("github-username-input");
    if (!input || !input.value.trim()) {
        showToast("Please enter a GitHub username.", "warning");
        return;
    }

    const username = input.value.trim();
    showToast(`Scraping public GitHub profile & repositories for @${username}...`, "info");

    try {
        const res = await fetchWithAuth("/import/github", {
            method: "POST",
            body: { github_username: username }
        });

        if (res.ok) {
            const data = await res.json();
            showToast(`Fetched ${data.projects?.length || 0} repositories and ${data.skills?.length || 0} skills from GitHub!`, "success");
            openResumeReviewModal(data);
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to fetch GitHub profile.", "error");
        }
    } catch (err) {
        console.error("GitHub import error:", err);
        showToast("Network error fetching GitHub profile.", "error");
    }
}

async function importFromLinkedIn() {
    const input = document.getElementById("linkedin-url-input");
    if (!input || !input.value.trim()) {
        showToast("Please enter a LinkedIn profile URL or paste text.", "warning");
        return;
    }

    const val = input.value.trim();
    showToast("Extracting LinkedIn profile data...", "info");

    try {
        const res = await fetchWithAuth("/import/linkedin", {
            method: "POST",
            body: { linkedin_url: val }
        });

        if (res.ok) {
            const data = await res.json();
            if (data.can_paste || (data.warning && (data.skills || []).length === 0)) {
                showToast(data.warning || "LinkedIn restricted direct web access. You can paste profile text below.", "warning");
                const pasteContainer = document.getElementById("linkedin-paste-container");
                if (pasteContainer) pasteContainer.style.display = "block";
            } else {
                showToast("LinkedIn profile data extracted!", "success");
            }
            openResumeReviewModal(data);
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to fetch LinkedIn profile.", "error");
        }
    } catch (err) {
        console.error("LinkedIn import error:", err);
        showToast("Network error fetching LinkedIn profile.", "error");
    }
}

async function importFromLinkedInText() {
    const textEl = document.getElementById("linkedin-paste-text");
    if (!textEl || !textEl.value.trim()) {
        showToast("Please paste your LinkedIn profile text.", "warning");
        return;
    }

    const textVal = textEl.value.trim();
    showToast("Extracting profile sections from text...", "info");

    try {
        const res = await fetchWithAuth("/import/linkedin", {
            method: "POST",
            body: { linkedin_url: textVal }
        });

        if (res.ok) {
            const data = await res.json();
            showToast("Profile data extracted from text!", "success");
            openResumeReviewModal(data);
        } else {
            const err = await res.json();
            showToast(err.detail || "Failed to parse text.", "error");
        }
    } catch (err) {
        console.error("LinkedIn text import error:", err);
        showToast("Failed to process text.", "error");
    }
}

// ─── ONBOARDING WIZARD LOGIC (PHASE 4) ───
let currentOnboardingStep = 1;

function checkOnboardingNeeded(summary) {
    const completed = localStorage.getItem("reliefer_onboarding_completed");
    if (completed === "true") return;

    if (summary && summary.total_skills === 0 && summary.total_experience === 0 && summary.total_projects === 0) {
        showOnboardingWizard();
    }
}

function showOnboardingWizard() {
    currentOnboardingStep = 1;
    updateOnboardingUI();
    const overlay = document.getElementById("onboarding-overlay");
    if (overlay) overlay.style.display = "flex";
    refreshIcons();
}

function updateOnboardingUI() {
    for (let i = 1; i <= 4; i++) {
        const stepBody = document.getElementById(`ob-step-${i}`);
        const indicator = document.getElementById(`ob-step-indicator-${i}`);
        if (stepBody) stepBody.style.display = (i === currentOnboardingStep) ? "block" : "none";
        if (indicator) {
            indicator.classList.remove("active", "completed");
            if (i === currentOnboardingStep) indicator.classList.add("active");
            else if (i < currentOnboardingStep) indicator.classList.add("completed");
        }
    }

    const progressBar = document.getElementById("ob-progress-bar");
    if (progressBar) {
        const pct = ((currentOnboardingStep - 1) / 3) * 100;
        progressBar.style.width = `${pct}%`;
    }

    const btnBack = document.getElementById("ob-btn-back");
    const btnNext = document.getElementById("ob-btn-next");
    const btnSkip = document.getElementById("ob-btn-skip");

    if (btnBack) btnBack.style.display = (currentOnboardingStep > 1) ? "inline-block" : "none";

    if (currentOnboardingStep === 4) {
        if (btnNext) btnNext.innerHTML = '<i data-lucide="rocket"></i> Go to Dashboard';
        if (btnSkip) btnSkip.style.display = "none";
    } else {
        if (btnNext) btnNext.innerHTML = 'Next Step <i data-lucide="arrow-right"></i>';
        if (btnSkip) btnSkip.style.display = "inline-block";
    }

    refreshIcons();
}

function nextOnboardingStep() {
    if (currentOnboardingStep < 4) {
        currentOnboardingStep++;
        updateOnboardingUI();
    } else {
        finishOnboarding();
    }
}

function prevOnboardingStep() {
    if (currentOnboardingStep > 1) {
        currentOnboardingStep--;
        updateOnboardingUI();
    }
}

function skipOnboarding() {
    localStorage.setItem("reliefer_onboarding_completed", "true");
    const overlay = document.getElementById("onboarding-overlay");
    if (overlay) overlay.style.display = "none";
    showToast("Onboarding skipped. You can update your profile anytime!", "info");
}

function finishOnboarding() {
    localStorage.setItem("reliefer_onboarding_completed", "true");
    const overlay = document.getElementById("onboarding-overlay");
    if (overlay) overlay.style.display = "none";
    showToast("Welcome aboard! Your profile is ready.", "success");
}

async function importFromGitHubOnboarding() {
    const val = document.getElementById("ob-github-input")?.value.trim();
    if (val) {
        document.getElementById("github-username-input").value = val;
        await importFromGitHub();
    }
}

async function importFromLinkedInOnboarding() {
    const val = document.getElementById("ob-linkedin-input")?.value.trim();
    if (val) {
        document.getElementById("linkedin-url-input").value = val;
        await importFromLinkedIn();
    }
}

async function saveHuggingFaceKeyFromOnboarding() {
    const input = document.getElementById("ob-hf-key-input");
    if (!input || !input.value.trim()) {
        showToast("Please enter an API key.", "warning");
        return;
    }
    const res = await fetchWithAuth("/me/huggingface-key", {
        method: "PUT",
        body: { huggingface_api_key: input.value.trim() }
    });
    if (res.ok) {
        showToast("Hugging Face API key saved!", "success");
        nextOnboardingStep();
    } else {
        showToast("Failed to save API key.", "error");
    }
}



