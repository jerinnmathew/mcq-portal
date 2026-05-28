/**
 * SEA-1 MCQ Battle Platform - Central JavaScript Controller
 * Handles Session management, API fetch wrappers, Navbar rendering, and UI themes.
 */

const API_BASE = '/api';

// --- UI Theme (Light / Dark Mode) Management ---
const Theme = {
    init() {
        const currentTheme = localStorage.getItem('mcq_theme') || 'dark';
        this.apply(currentTheme);
    },
    
    apply(theme) {
        const html = document.documentElement;
        if (theme === 'light') {
            html.classList.remove('dark');
            localStorage.setItem('mcq_theme', 'light');
        } else {
            html.classList.add('dark');
            localStorage.setItem('mcq_theme', 'dark');
        }
        this.updateToggles();
    },
    
    toggle() {
        const isDark = document.documentElement.classList.contains('dark');
        this.apply(isDark ? 'light' : 'dark');
    },
    
    updateToggles() {
        const isDark = document.documentElement.classList.contains('dark');
        
        // Desktop Toggle
        const desktopToggle = document.getElementById('theme-toggle-desktop');
        if (desktopToggle) {
            desktopToggle.innerHTML = isDark 
                ? '<i class="fas fa-sun text-yellow-400 text-sm"></i>' 
                : '<i class="fas fa-moon text-indigo-400 text-sm"></i>';
        }
        
        // Mobile Toggle
        const mobileToggle = document.getElementById('theme-toggle-mobile');
        if (mobileToggle) {
            mobileToggle.innerHTML = isDark 
                ? '<i class="fas fa-sun text-yellow-400 text-sm"></i> Light Mode' 
                : '<i class="fas fa-moon text-indigo-400 text-sm"></i> Dark Mode';
        }
    }
};

// Initialize theme immediately to prevent visual flash
Theme.init();

// --- Session & Storage Management ---
const Auth = {
    clearSession() {
        localStorage.removeItem('mcq_user');
        localStorage.removeItem('current_quiz_questions');
        localStorage.removeItem('last_quiz_results');
    },
    
    saveUser(user) {
        localStorage.setItem('mcq_user', JSON.stringify(user));
    },
    
    getUser() {
        const user = localStorage.getItem('mcq_user');
        return user ? JSON.parse(user) : null;
    },
    
    isAuthenticated() {
        return !!this.getUser();
    },

    logout() {
        // Fetch CSRF double-submit token for secure state-changing POST requests
        const csrfToken = getCookie('csrf_access_token');
        fetch(`${API_BASE}/auth/logout`, { 
            method: 'POST', 
            headers: {
                'X-CSRF-Token': csrfToken
            }
        }).finally(() => {
            this.clearSession();
            window.location.href = 'login.html';
        });
    }
};

// --- Cookie Extraction Helper ---
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// --- Secure API Fetch Wrapper ---
async function fetchAPI(endpoint, options = {}) {
    // Set headers
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };
    
    // Auto-inject double-submit CSRF token for state-changing operations
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
        const csrfToken = getCookie('csrf_access_token');
        if (csrfToken) {
            headers['X-CSRF-Token'] = csrfToken;
        }
    }
    
    const config = {
        credentials: 'same-origin', // Ensure secure cookies are sent with requests
        ...options,
        headers
    };

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);
        
        // Auto handle session expiration
        if (response.status === 401) {
            console.warn("Session expired or unauthorized. Redirecting to login.");
            Auth.clearSession();
            if (!window.location.pathname.endsWith('login.html') && !window.location.pathname.endsWith('register.html')) {
                window.location.href = 'login.html';
            }
            return { error: true, msg: "Session expired. Please log in again." };
        }
        
        const data = await response.json();
        if (!response.ok) {
            return { error: true, msg: data.msg || "Request failed" };
        }
        
        return data;
    } catch (err) {
        console.error(`API Error on ${endpoint}:`, err);
        return { error: true, msg: "Network error. Make sure the server is running." };
    }
}

// --- Page Guards ---
function protectPage() {
    if (!Auth.isAuthenticated()) {
        window.location.href = 'login.html';
    }
}

function redirectIfLoggedIn() {
    if (Auth.isAuthenticated()) {
        window.location.href = 'dashboard.html';
    }
}

// --- Dynamic Common UI Builders ---
function renderNavbar() {
    const navbarContainer = document.getElementById('navbar-container');
    if (!navbarContainer) return;

    const isLoggedIn = Auth.isAuthenticated();
    const user = Auth.getUser();

    let navLinks = '';
    let mobileLinks = '';
    if (isLoggedIn) {
        const isAdmin = user && user.username === 'admin';
        const linksHtml = `
            <a href="dashboard.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Dashboard</a>
            <a href="quiz.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Quiz Arena</a>
            <a href="leaderboard.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Leaderboard</a>
            <a href="profile.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Profile</a>
            ${isAdmin ? `<a href="admin.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-purple-400 transition-colors text-purple-300 border border-purple-500/20 bg-purple-500/5">Admin</a>` : ''}
        `;
        navLinks = linksHtml;
        
        mobileLinks = `
            <a href="dashboard.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-chart-pie text-blue-500 text-base"></i> Dashboard</a>
            <a href="quiz.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-gamepad text-indigo-500 text-base"></i> Quiz Arena</a>
            <a href="leaderboard.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-trophy text-yellow-500 text-base"></i> Leaderboard</a>
            <a href="profile.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-user-circle text-emerald-500 text-base"></i> Profile</a>
            ${isAdmin ? `<a href="admin.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold text-purple-300 hover:text-purple-400 hover:bg-purple-500/5 border border-purple-500/10 bg-purple-500/5 transition-all flex items-center gap-3"><i class="fas fa-user-shield text-base"></i> Admin Control</a>` : ''}
        `;
    } else {
        const linksHtml = `
            <a href="index.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Home</a>
            <a href="leaderboard.html" class="px-3 py-2 rounded-lg text-sm font-medium hover:text-blue-400 transition-colors">Leaderboard</a>
        `;
        navLinks = linksHtml;

        mobileLinks = `
            <a href="index.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-home text-blue-500 text-base"></i> Home</a>
            <a href="leaderboard.html" class="px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3"><i class="fas fa-trophy text-yellow-500 text-base"></i> Leaderboard</a>
        `;
    }

    const authSection = isLoggedIn && user
        ? `
            <div class="flex items-center gap-4">
                <div class="hidden md:flex flex-col text-right">
                    <span class="text-xs text-gray-400">Streak: 🔥 ${user.streak || 0}</span>
                    <span class="text-sm font-semibold text-blue-400">${user.username}</span>
                </div>
                <div class="h-8 w-8 rounded-full ${getBadgeClass(user.badge)} flex items-center justify-center font-bold text-white text-xs ring-2 ring-white/10">
                    ${user.username[0].toUpperCase()}
                </div>
                <button onclick="Auth.logout()" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 transition-all cursor-pointer">
                    <i class="fas fa-sign-out-alt"></i> Logout
                </button>
            </div>
          `
        : `
            <div class="flex items-center gap-2">
                <a href="login.html" class="px-3 py-1.5 rounded-lg text-sm font-semibold hover:text-white text-gray-300 transition-all">Login</a>
                <a href="register.html" class="px-4 py-2 rounded-lg text-sm font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20 transition-all">Register</a>
            </div>
          `;

    const mobileAuthSection = isLoggedIn && user
        ? `
            <div class="flex flex-col gap-4">
                <div class="flex items-center gap-3 px-2">
                    <div class="h-10 w-10 rounded-full ${getBadgeClass(user.badge)} flex items-center justify-center font-bold text-white text-sm ring-2 ring-white/10">
                        ${user.username[0].toUpperCase()}
                    </div>
                    <div>
                        <span class="text-sm font-bold text-blue-400 block">${user.username}</span>
                        <span class="text-xs text-gray-400">Streak: 🔥 ${user.streak || 0} Days</span>
                    </div>
                </div>
                <button onclick="Auth.logout()" class="w-full py-2.5 rounded-xl font-bold bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 transition-all cursor-pointer text-center text-sm flex items-center justify-center gap-2">
                    <i class="fas fa-sign-out-alt text-xs"></i> Logout
                </button>
            </div>
          `
        : `
            <div class="grid grid-cols-2 gap-3">
                <a href="login.html" class="py-2.5 rounded-xl font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-slate-200 transition-all text-center text-sm cursor-pointer">
                    Login
                </a>
                <a href="register.html" class="py-2.5 rounded-xl font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/20 transition-all text-center text-sm cursor-pointer">
                    Register
                </a>
            </div>
          `;

    navbarContainer.innerHTML = `
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <!-- Logo -->
                <div class="flex items-center">
                    <a href="index.html" class="flex items-center gap-2">
                        <div class="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                            <i class="fas fa-graduation-cap text-white text-lg"></i>
                        </div>
                        <span class="text-lg font-extrabold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent font-display">
                            SEA-1 MCQ Battle
                        </span>
                    </a>
                </div>
                <!-- Links (Desktop) -->
                <nav class="hidden md:flex space-x-2 text-gray-300">
                    ${navLinks}
                </nav>
                <!-- Auth / Actions (Desktop) -->
                <div class="hidden md:flex items-center gap-3">
                    <button id="theme-toggle-desktop" onclick="Theme.toggle()" class="p-2 rounded-lg hover:bg-white/5 border border-white/10 text-gray-400 hover:text-white transition-all cursor-pointer flex items-center justify-center h-9 w-9 focus:outline-none">
                        <i class="fas fa-sun text-yellow-400"></i>
                    </button>
                    ${authSection}
                </div>
                <!-- Mobile Menu Button -->
                <div class="flex items-center md:hidden">
                    <button id="mobile-menu-btn" onclick="toggleMobileMenu()" class="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 border border-white/10 transition-all cursor-pointer focus:outline-none">
                        <i class="fas fa-bars text-lg" id="mobile-menu-icon"></i>
                    </button>
                </div>
            </div>
        </div>
        <!-- Mobile Dropdown Panel -->
        <div id="mobile-nav-panel" class="hidden md:hidden border-t border-white/5 bg-slate-950/90 backdrop-blur-xl px-4 py-4 space-y-4 shadow-lg">
            <nav class="flex flex-col space-y-1.5 text-gray-300">
                ${mobileLinks}
                <!-- Theme Toggle (Mobile) -->
                <button id="theme-toggle-mobile" onclick="Theme.toggle()" class="w-full text-left px-4 py-2.5 rounded-xl text-sm font-semibold hover:text-blue-400 hover:bg-white/5 transition-all flex items-center gap-3 focus:outline-none cursor-pointer">
                    <i class="fas fa-sun text-yellow-400"></i> Light Mode
                </button>
            </nav>
            <div class="pt-4 border-t border-white/5">
                ${mobileAuthSection}
            </div>
        </div>
    `;

    Theme.updateToggles();
}

// Global mobile menu toggler helper
window.toggleMobileMenu = function() {
    const mobilePanel = document.getElementById('mobile-nav-panel');
    const menuIcon = document.getElementById('mobile-menu-icon');
    if (!mobilePanel || !menuIcon) return;

    const isHidden = mobilePanel.classList.contains('hidden');
    if (isHidden) {
        mobilePanel.classList.remove('hidden');
        menuIcon.className = 'fas fa-xmark text-lg';
    } else {
        mobilePanel.classList.add('hidden');
        menuIcon.className = 'fas fa-bars text-lg';
    }
};

// --- Dynamic helper utilities ---
function getBadgeClass(badge) {
    const b = (badge || 'Bronze').toLowerCase();
    if (b === 'platinum') return 'badge-platinum';
    if (b === 'gold') return 'badge-gold';
    if (b === 'silver') return 'badge-silver';
    return 'badge-bronze';
}

function formatDate(isoString) {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// --- Landing Page Dynamic Profile Controller ---
async function initLandingProfile() {
    const loggedInEl = document.getElementById('profile-logged-in');
    const loggedOutEl = document.getElementById('profile-logged-out');
    if (!loggedInEl || !loggedOutEl) return;

    if (!Auth.isAuthenticated()) {
        loggedInEl.classList.add('hidden');
        loggedOutEl.classList.remove('hidden');
        return;
    }

    // Is logged in: Show the profile panel
    loggedInEl.classList.remove('hidden');
    loggedOutEl.classList.add('hidden');

    const cachedUser = Auth.getUser();
    if (cachedUser) {
        // First-pass instant render using cached data
        updateProfileFields(cachedUser, { win_ratio: 0.0 });
    }

    // Asynchronously fetch fresh stats and user details from backend
    const data = await fetchAPI('/stats/dashboard');
    if (!data.error && data.user && data.stats) {
        Auth.saveUser(data.user); // update storage cache
        updateProfileFields(data.user, data.stats);
    }
}

function updateProfileFields(user, stats) {
    // 1. Avatar letter & colors
    const avatar = document.getElementById('student-avatar');
    if (avatar) {
        avatar.innerText = user.username ? user.username[0].toUpperCase() : 'S';
        // Dynamically match badge style class
        const badge = user.badge || 'Bronze';
        const badgeClass = getBadgeClass(badge);
        const b = badge.toLowerCase();
        const textClass = (b === 'platinum' || b === 'gold' || b === 'silver') ? 'text-slate-900' : 'text-slate-100';
        avatar.className = `h-12 w-12 rounded-xl flex items-center justify-center font-bold ${textClass} text-lg shadow-lg ring-1 ring-white/10 ${badgeClass}`;
    }

    // 2. Username & Streak
    const nameEl = document.getElementById('student-name');
    if (nameEl) nameEl.innerText = user.username || 'Student';

    const streakEl = document.getElementById('student-streak');
    if (streakEl) streakEl.innerText = `Current Streak: ${user.streak || 0} Days`;

    // 3. Badge Rank Label
    const badgeEl = document.getElementById('student-badge');
    if (badgeEl) {
        const badge = user.badge || 'Bronze';
        badgeEl.innerText = `🔥 ${badge.toUpperCase()} BADGE`;
        
        // Remove existing class properties
        badgeEl.className = 'px-2 py-0.5 rounded text-[10px] font-bold border';
        if (badge.toLowerCase() === 'platinum') {
            badgeEl.classList.add('bg-slate-300/20', 'text-slate-200', 'border-slate-300/30');
        } else if (badge.toLowerCase() === 'gold') {
            badgeEl.classList.add('bg-yellow-500/20', 'text-yellow-400', 'border-yellow-500/30');
        } else if (badge.toLowerCase() === 'silver') {
            badgeEl.classList.add('bg-slate-400/20', 'text-slate-300', 'border-slate-400/30');
        } else {
            badgeEl.classList.add('bg-amber-700/20', 'text-amber-500', 'border-amber-700/30'); // Bronze
        }
    }

    // 4. Quick stats (XP & Accuracy)
    const scoreEl = document.getElementById('student-score');
    if (scoreEl) scoreEl.innerText = `${user.xp_points || 0} XP`;

    const accuracyEl = document.getElementById('student-accuracy');
    if (accuracyEl) {
        const winRatio = stats && stats.win_ratio !== undefined ? stats.win_ratio : 0.0;
        accuracyEl.innerText = `${winRatio.toFixed(1)}%`;
    }

    // 5. Progress to next milestone
    const nextLevelEl = document.getElementById('student-next-level');
    const xpProgressEl = document.getElementById('student-xp-progress');
    const progressBar = document.getElementById('student-progress-bar');
    
    if (nextLevelEl && xpProgressEl && progressBar) {
        const badge = user.badge || 'Bronze';
        let nextBadge = 'Silver';
        let nextMilestone = 100;
        let currentBase = 0;

        if (badge.toLowerCase() === 'bronze') {
            nextBadge = 'Silver';
            nextMilestone = 100;
            currentBase = 0;
        } else if (badge.toLowerCase() === 'silver') {
            nextBadge = 'Gold';
            nextMilestone = 500;
            currentBase = 100;
        } else if (badge.toLowerCase() === 'gold') {
            nextBadge = 'Platinum';
            nextMilestone = 1500;
            currentBase = 500;
        } else if (badge.toLowerCase() === 'platinum') {
            nextBadge = 'Grandmaster';
            nextMilestone = 5000;
            currentBase = 1500;
        }

        const progressRange = nextMilestone - currentBase;
        const userProgressVal = (user.xp_points || 0) - currentBase;
        const progressPct = Math.min(100, Math.max(0, (userProgressVal / progressRange) * 100));

        nextLevelEl.innerText = `Next Level (${nextBadge})`;
        xpProgressEl.innerText = `${user.xp_points || 0} / ${nextMilestone} XP`;
        progressBar.style.width = `${progressPct}%`;
    }
}

// Automatically init navbar and landing page elements if script loaded
document.addEventListener('DOMContentLoaded', () => {
    renderNavbar();
    initLandingProfile();
});
