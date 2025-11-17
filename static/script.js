/*
    Frontend interactions for Movie Recommender AI.

    Sections:
    - Ratings: star click/hover and POST /rate
    - Watchlist: add/remove with event delegation and UI sync
    - Trailers/Details: track clicks and show modal with fetched details
    - Autocomplete: movie/actor modes with keyboard navigation
    - Theme: light/dark toggle, color customization panel, contrast-safe neon
    - Notifications/Loading: lightweight toasts and loading skeleton
*/
// Movie rating functionality
document.addEventListener('DOMContentLoaded', function() {
    // Rating stars interaction
    const ratingContainers = document.querySelectorAll('.rating-stars');
    
    ratingContainers.forEach(container => {
        const stars = container.querySelectorAll('.star');
        const movieId = container.dataset.movieId;
        
        stars.forEach(star => {
            star.addEventListener('click', function() {
                const rating = parseInt(this.dataset.rating);
                rateMovie(movieId, rating, container);
            });
            
            star.addEventListener('mouseenter', function() {
                const rating = parseInt(this.dataset.rating);
                highlightStars(container, rating);
            });
        });
        
        container.addEventListener('mouseleave', function() {
            const currentRating = container.dataset.currentRating || 0;
            highlightStars(container, currentRating);
        });
    });
    
    // Watchlist button interaction (event delegation)
    document.addEventListener('click', function(e) {
        const watchlistBtn = e.target.closest('.watchlist-btn');
        if (watchlistBtn) {
            e.preventDefault();
            const movieId = watchlistBtn.dataset.movieId;
            toggleWatchlist(movieId, watchlistBtn);
        }
    });
    
    // Trailer link tracking (event delegation)
    document.addEventListener('click', function(e) {
        const trailerLink = e.target.closest('.trailer-btn');
        if (trailerLink) {
            const movieId = trailerLink.dataset.movieId;
            trackTrailerClick(movieId);
        }
    });
    
    // Movie details button (event delegation)
    document.addEventListener('click', function(e) {
        const detailsBtn = e.target.closest('.details-btn');
        if (detailsBtn) {
            e.preventDefault();
            const movieId = detailsBtn.dataset.movieId;
            showMovieDetails(movieId);
        }
    });

    // Explain button (event delegation)
    document.addEventListener('click', function(e) {
        const explainBtn = e.target.closest('.explain-btn');
        if (explainBtn) {
            e.preventDefault();
            const movieId = explainBtn.dataset.movieId;
            const aiMatch = explainBtn.dataset.aiMatch || '';
            const personalization = explainBtn.dataset.personalization || '';
            fetch(`/explain/${movieId}?ai_match=${encodeURIComponent(aiMatch)}&personalization=${encodeURIComponent(personalization)}`)
              .then(r => r.json())
              .then(data => {
                  if (data.error) {
                      showNotification(`Explain failed: ${data.error}`, 'error');
                      return;
                  }
                  const msg = data.reason || 'Recommended based on similarity.';
                  showNotification(msg, 'info');
              })
              .catch(err => showNotification('Explain failed', 'error'));
        }
    });

    // Feedback buttons (event delegation)
    document.addEventListener('click', function(e) {
        const notBtn = e.target.closest('.not-interested-btn');
        const moreBtn = e.target.closest('.more-like-btn');
        if (notBtn) {
            e.preventDefault();
            const movieId = notBtn.dataset.movieId;
            fetch('/feedback/not_interested', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRF-Token': getCsrfToken(),
                },
                body: `movie_id=${movieId}`
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    const card = notBtn.closest('.movie');
                    if (card) card.remove();
                    showNotification('We\'ll show fewer like this', 'info');
                }
            });
        } else if (moreBtn) {
            e.preventDefault();
            const movieId = moreBtn.dataset.movieId;
            fetch('/feedback/more_like', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRF-Token': getCsrfToken(),
                },
                body: `movie_id=${movieId}`
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    showNotification('Got it! We\'ll recommend more like this', 'success');
                }
            });
        }
    });
    
    // Autocomplete functionality
    setupAutocomplete();
    
    // Modal close functionality
    setupModal();
    
    // Show loading on form submit
    const searchForm = document.getElementById('search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function() {
            showAiOverlay();
            showLoading();
        });
    }

    // Theme panel wiring
    initThemePanel();

    // Ensure neon contrast on initial load (after any saved colors applied)
    try { ensureNeonContrast(); } catch (e) { /* no-op */ }

    // Register service worker (PWA)
    try {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/service-worker.js');
        }
    } catch (e) { /* no-op */ }

    // Auth modal wiring
    setupAuthModal();
});

// Autocomplete search
let autocompleteTimeout;
function setupAutocomplete() {
    const searchInput = document.getElementById('search-input');
    const dropdown = document.getElementById('autocomplete-dropdown');
    const searchForm = document.getElementById('search-form');
    let mode = 'movie';
    if (searchForm) {
        searchForm.addEventListener('change', (e) => {
            if (e.target.name === 'search_type') {
                mode = e.target.value;
                dropdown.innerHTML='';
                dropdown.classList.remove('show');
            }
        });
        const checked = searchForm.querySelector('input[name="search_type"]:checked');
        if (checked) mode = checked.value;
    }
    
    if (!searchInput || !dropdown) return;
    
    searchInput.addEventListener('input', function() {
        clearTimeout(autocompleteTimeout);
        const query = this.value.trim();
        
        if (query.length < 2) {
            dropdown.innerHTML = '';
            dropdown.classList.remove('show');
            return;
        }
        
        // Debounce the search
        autocompleteTimeout = setTimeout(() => {
            fetchAutocompleteSuggestions(query, dropdown, mode);
        }, 300);
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });
    
    // Handle keyboard navigation
    searchInput.addEventListener('keydown', function(e) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        const activeItem = dropdown.querySelector('.autocomplete-item.active');
        let index = Array.from(items).indexOf(activeItem);
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            index = Math.min(index + 1, items.length - 1);
            setActiveItem(items, index);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            index = Math.max(index - 1, 0);
            setActiveItem(items, index);
        } else if (e.key === 'Enter' && activeItem) {
            e.preventDefault();
            activeItem.click();
        }
    });
}

function fetchAutocompleteSuggestions(query, dropdown, mode='movie') {
    const url = `/autocomplete?q=${encodeURIComponent(query)}&type=${mode}`;
    fetch(url)
        .then(response => response.json())
        .then(suggestions => {
            if (suggestions.length === 0) {
                dropdown.innerHTML = '<div class="autocomplete-item no-results">No suggestions found</div>';
                dropdown.classList.add('show');
                return;
            }
            if (mode === 'actor') {
                dropdown.innerHTML = suggestions.map(p => `
                  <div class="autocomplete-item person" data-person-id="${p.id}">
                    <img src="${p.profile}" alt="${p.name}">
                    <div class="autocomplete-info">
                      <div class="autocomplete-title">${p.name}</div>
                      <div class="autocomplete-year">${p.known_for_department || ''}</div>
                    </div>
                  </div>
                `).join('');
            } else {
                dropdown.innerHTML = suggestions.map(movie => `
                  <div class="autocomplete-item" data-title="${movie.title}">
                    <img src="${movie.poster}" alt="${movie.title}">
                    <div class="autocomplete-info">
                      <div class="autocomplete-title">${movie.title}</div>
                      <div class="autocomplete-year">${movie.year}</div>
                    </div>
                  </div>
                `).join('');
            }
            
            dropdown.classList.add('show');
            
            // Add click handlers to items
            if (mode === 'actor') {
                dropdown.querySelectorAll('.autocomplete-item.person').forEach(item => {
                    item.addEventListener('click', function() {
                        const pid = this.dataset.personId;
                        if (pid) {
                            window.location.href = `/actor/${pid}`;
                        }
                    });
                });
            } else {
                dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
                    item.addEventListener('click', function() {
                        const title = this.dataset.title;
                        if (title) {
                            document.getElementById('search-input').value = title;
                            document.getElementById('search-form').submit();
                        }
                    });
                });
            }
        })
        .catch(error => {
            console.error('Autocomplete error:', error);
        });
}

function setActiveItem(items, index) {
    items.forEach(item => item.classList.remove('active'));
    if (items[index]) {
        items[index].classList.add('active');
        items[index].scrollIntoView({ block: 'nearest' });
    }
}

// No filters UI; simplified experience

function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Show scroll to top button when scrolling down
window.addEventListener('scroll', function() {
    const scrollBtn = document.querySelector('.scroll-to-top');
    if (scrollBtn) {
        if (window.pageYOffset > 300) {
            scrollBtn.classList.add('show');
        } else {
            scrollBtn.classList.remove('show');
        }
    }
});

function highlightStars(container, rating) {
    const stars = container.querySelectorAll('.star');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}

function rateMovie(movieId, rating, container) {
    fetch('/rate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRF-Token': getCsrfToken(),
        },
        body: `movie_id=${movieId}&rating=${rating}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            container.dataset.currentRating = rating;
            highlightStars(container, rating);
            showNotification(`Rated ${rating} stars!`, 'success');
        }
    })
    .catch(error => {
        console.error('Error rating movie:', error);
        showNotification('Failed to rate movie', 'error');
    });
}

function toggleWatchlist(movieId, buttonEl) {
    const endpointDecide = () => {
        // If caller provided element, trust its current state; else detect from any button
        let currentText = null;
        if (buttonEl) {
            const t = buttonEl.querySelector('.watchlist-text');
            currentText = t ? t.textContent : null;
        }
        if (currentText == null) {
            const anyBtn = document.querySelector(`.watchlist-btn[data-movie-id="${movieId}"] .watchlist-text`);
            currentText = anyBtn ? anyBtn.textContent : 'Watchlist';
        }
        const isIn = currentText === 'Remove';
        return { endpoint: isIn ? '/watchlist/remove' : '/watchlist/add' };
    };

    const { endpoint } = endpointDecide();

    const slot = computeSlotPosition(buttonEl);
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRF-Token': getCsrfToken(),
        },
        body: `movie_id=${movieId}&slot=${encodeURIComponent(slot ?? '')}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const nowIn = Array.isArray(data.watchlist) && data.watchlist.includes(Number(movieId));
            // Update all matching buttons on page
            document.querySelectorAll(`.watchlist-btn[data-movie-id="${movieId}"]`).forEach(btn => {
                const txt = btn.querySelector('.watchlist-text');
                if (txt) txt.textContent = nowIn ? 'Remove' : 'Watchlist';
            });
            const action = nowIn ? 'Added to' : 'Removed from';
            showNotification(`${action} watchlist!`, 'success');
            
            // Update watchlist count in header if it exists
            const watchlistLink = document.querySelector('a[href*="watchlist"]');
            if (watchlistLink) {
                const count = data.watchlist.length;
                watchlistLink.textContent = watchlistLink.textContent.replace(/\d+/, count);
            }
        }
    })
    .catch(error => {
        console.error('Error updating watchlist:', error);
        showNotification('Failed to update watchlist', 'error');
    });
}

function trackTrailerClick(movieId) {
    const anyBtn = document.querySelector(`.trailer-btn[data-movie-id="${movieId}"]`);
    const slot = computeSlotPosition(anyBtn);
    fetch('/trailer/click', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRF-Token': getCsrfToken(),
        },
        body: `movie_id=${movieId}&slot=${encodeURIComponent(slot ?? '')}`
    }).catch(error => console.error('Error tracking trailer click:', error));
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => notification.classList.add('show'), 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Loading skeleton functions
function showLoading() {
    const skeleton = document.getElementById('loading-skeleton');
    const moviesContainer = document.getElementById('movies');
    if (skeleton) {
        skeleton.style.display = 'flex';
    }
    if (moviesContainer) {
        moviesContainer.style.display = 'none';
    }
}

function hideLoading() {
    const skeleton = document.getElementById('loading-skeleton');
    const moviesContainer = document.getElementById('movies');
    if (skeleton) {
        skeleton.style.display = 'none';
    }
    if (moviesContainer) {
        moviesContainer.style.display = 'grid';
    }
}

// AI overlay helpers
function showAiOverlay() {
    const overlay = document.getElementById('ai-overlay');
    if (overlay) overlay.style.display = 'flex';
}

function hideAiOverlay() {
    const overlay = document.getElementById('ai-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Movie details modal functions
function setupModal() {
    const modal = document.getElementById('movie-modal');
    const closeBtn = document.querySelector('.modal-close');
    let lastFocused = null;
    let focusables = [];

    function updateFocusables() {
        focusables = Array.from(modal.querySelectorAll('a[href], button, textarea, input, select, [tabindex]:not([tabindex="-1"])'))
            .filter(el => !el.hasAttribute('disabled') && el.offsetParent !== null);
    }

    function openModal() {
        lastFocused = document.activeElement;
        modal.style.display = 'block';
        updateFocusables();
        if (focusables.length) {
            focusables[0].focus();
        } else if (closeBtn) {
            closeBtn.focus();
        }
    }

    function closeModal() {
        modal.style.display = 'none';
        if (lastFocused && typeof lastFocused.focus === 'function') {
            lastFocused.focus();
        }
    }
    
    if (closeBtn) {
        closeBtn.onclick = function() { closeModal(); };
    }

    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            closeModal();
        }
    });

    // Keyboard: Esc close, Tab trap
    window.addEventListener('keydown', function(e) {
        if (modal.style.display === 'block') {
            if (e.key === 'Escape') {
                e.preventDefault();
                closeModal();
            } else if (e.key === 'Tab') {
                updateFocusables();
                if (!focusables.length) return;
                const first = focusables[0];
                const last = focusables[focusables.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
    });
}

// Auth modal (login/register) logic
function setupAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (!modal) return;
    const closeBtn = modal.querySelector('.modal-close');
    const loginTab = modal.querySelector('#tab-login');
    const registerTab = modal.querySelector('#tab-register');
    const loginSection = modal.querySelector('#section-login');
    const registerSection = modal.querySelector('#section-register');
    const openLogin = document.getElementById('open-login');
    const openRegister = document.getElementById('open-register');

    const showModal = (mode='login') => {
        modal.style.display = 'block';
        setActive(mode);
    };
    const hideModal = () => { modal.style.display = 'none'; };
    const setActive = (mode) => {
        const isLogin = mode === 'login';
        loginTab.classList.toggle('active', isLogin);
        registerTab.classList.toggle('active', !isLogin);
        loginSection.style.display = isLogin ? 'block' : 'none';
        registerSection.style.display = isLogin ? 'none' : 'block';
    };

    if (openLogin) openLogin.addEventListener('click', (e) => { e.preventDefault(); showModal('login'); });
    if (openRegister) openRegister.addEventListener('click', (e) => { e.preventDefault(); showModal('register'); });
    if (closeBtn) closeBtn.addEventListener('click', hideModal);
    window.addEventListener('click', (e) => { if (e.target === modal) hideModal(); });

    loginTab.addEventListener('click', () => setActive('login'));
    registerTab.addEventListener('click', () => setActive('register'));

    // Submit handlers
    const loginForm = modal.querySelector('#form-login');
    const registerForm = modal.querySelector('#form-register');
    const loginError = modal.querySelector('#login-error');
    const loginSuccess = modal.querySelector('#login-success');
    const regError = modal.querySelector('#register-error');
    const regSuccess = modal.querySelector('#register-success');

    function postForm(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRF-Token': getCsrfToken(),
            },
            body: new URLSearchParams(data).toString()
        }).then(async (r) => {
            const contentType = r.headers.get('content-type') || '';
            const body = contentType.includes('application/json') ? await r.json() : {};
            if (!r.ok || body.success === false) {
                const msg = (body && body.message) ? body.message : `Request failed (${r.status})`;
                throw new Error(msg);
            }
            return body;
        });
    }

    if (loginForm) loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        loginError.style.display = 'none';
        loginSuccess.style.display = 'none';
        const email = loginForm.querySelector('input[name="email"]').value.trim();
        const password = loginForm.querySelector('input[name="password"]').value;
        postForm('/login', { email, password })
            .then((data) => {
                loginSuccess.textContent = data.message || 'Logged in successfully';
                loginSuccess.style.display = 'block';
                showNotification('Logged in successfully', 'success');
                setTimeout(() => { window.location.reload(); }, 800);
            })
            .catch((err) => {
                loginError.textContent = err.message || 'Login failed';
                loginError.style.display = 'block';
            });
    });

    if (registerForm) registerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        regError.style.display = 'none';
        regSuccess.style.display = 'none';
        const email = registerForm.querySelector('input[name="email"]').value.trim();
        const password = registerForm.querySelector('input[name="password"]').value;
        const confirm = registerForm.querySelector('input[name="confirm"]').value;
        postForm('/register', { email, password, confirm })
            .then((data) => {
                regSuccess.textContent = data.message || 'Registration successful';
                regSuccess.style.display = 'block';
                showNotification('Welcome! Account created', 'success');
                setTimeout(() => { window.location.reload(); }, 900);
            })
            .catch((err) => {
                regError.textContent = err.message || 'Registration failed';
                regError.style.display = 'block';
            });
    });
}

function showMovieDetails(movieId) {
    const modal = document.getElementById('movie-modal');
    const modalBody = document.getElementById('modal-body');
    
    // Show modal with loader
    modal.style.display = 'block';
    modalBody.innerHTML = '<div class="modal-loader"><i class="fas fa-spinner fa-spin"></i> Loading details...</div>';
    
    // Fetch movie details
    fetch(`/movie/${movieId}`)
        .then(response => response.json())
        .then(movie => {
            modalBody.innerHTML = `
                <div class="modal-header" style="background-image: url('${movie.backdrop}');">
                    <div class="modal-header-overlay">
                        <h2 id="modal-title">${movie.title}</h2>
                        ${movie.tagline ? `<p class="tagline">"${movie.tagline}"</p>` : ''}
                    </div>
                </div>
                
                <div class="modal-body-content">
                    <div class="modal-main-info">
                        <img src="${movie.poster}" alt="${movie.title}" class="modal-poster" loading="lazy" decoding="async">
                        
                        <div class="modal-info">
                            <div class="modal-meta">
                                <span class="modal-rating">⭐ ${movie.rating}/10</span>
                                <span class="modal-runtime">${movie.runtime ? movie.runtime + ' min' : 'N/A'}</span>
                                <span class="modal-year">${movie.release_date ? movie.release_date.substring(0, 4) : 'N/A'}</span>
                            </div>
                            
                            <div class="modal-genres">
                                ${movie.genres.map(g => `<span class="genre-tag">${g}</span>`).join('')}
                            </div>
                            
                            <p class="modal-overview">${movie.overview}</p>
                            
                            <div class="modal-crew">
                                <p><strong>Director:</strong> ${movie.director}</p>
                                ${movie.writers && movie.writers.length ? `<p><strong>Writers:</strong> ${movie.writers.join(', ')}</p>` : ''}
                            </div>
                            
                            ${movie.budget || movie.revenue ? `
                            <div class="modal-financials">
                                ${movie.budget ? `<p><strong>Budget:</strong> $${(movie.budget / 1000000).toFixed(1)}M</p>` : ''}
                                ${movie.revenue ? `<p><strong>Revenue:</strong> $${(movie.revenue / 1000000).toFixed(1)}M</p>` : ''}
                            </div>
                            ` : ''}
                            
                            <div class="modal-actions">
                                ${movie.trailer ? `
                                <a href="${movie.trailer}" target="_blank" class="modal-btn trailer-btn">
                                    <i class="fas fa-play"></i> Watch Trailer
                                </a>
                                ` : ''}
                                ${movie.watch_link ? `
                                <a href="${movie.watch_link}" target="_blank" rel="noopener" class="modal-btn trailer-btn" style="background: linear-gradient(135deg, #38ef7d, #11998e);">
                                    <i class="fas fa-tv"></i> Watch Now
                                </a>
                                ` : ''}
                                <button class="modal-btn watchlist-btn" data-movie-id="${movie.id}">
                                    <i class="fas fa-bookmark"></i> Add to Watchlist
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    ${movie.cast && movie.cast.length ? `
                    <div class="modal-cast">
                        <h3>Top Cast</h3>
                        <div class="cast-grid">
                            ${movie.cast.map(person => `
                                <div class="cast-member">
                                    <img src="${person.profile}" alt="${person.name}">
                                    <p class="cast-name">${person.name}</p>
                                    <p class="cast-character">${person.character}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}
                </div>
            `;
            // After injecting content, refresh focusables and set initial focus
            (function ensureFocus() {
                try {
                    const closeBtn = document.querySelector('.modal-close');
                    if (closeBtn) closeBtn.focus();
                } catch (_) {}
            })();
        })
        .catch(error => {
            console.error('Error fetching movie details:', error);
            modalBody.innerHTML = '<div class="modal-error">Failed to load movie details. Please try again.</div>';
        });
}

// Theme toggling
// Theme toggle removed; only color customization is supported.

// Theme color customization
function initThemePanel() {
    const toggleBtn = document.getElementById('theme-panel-toggle');
    const panel = document.getElementById('theme-panel');
    const accentInput = document.getElementById('accent-color');
    const neonInput = document.getElementById('neon-color');
    const applyBtn = document.getElementById('apply-colors');
    const resetBtn = document.getElementById('reset-colors');
    const closeBtn = document.getElementById('close-panel');

    if (!toggleBtn || !panel) return;

    // Accessibility wiring
    toggleBtn.setAttribute('aria-controls', 'theme-panel');
    toggleBtn.setAttribute('aria-expanded', 'false');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'false');

    // Load saved colors
    const savedAccent = localStorage.getItem('accentColor');
    const savedNeon = localStorage.getItem('neonColor');
    if (savedAccent) {
        setCssVar('--accent', savedAccent);
        if (accentInput) accentInput.value = toColorInput(savedAccent);
    }
    if (savedNeon) {
        setCssVar('--neon', savedNeon);
        if (neonInput) neonInput.value = toColorInput(savedNeon);
    }

    // Establish initial contrast-safe neon
    ensureNeonContrast();

    const setPanelVisible = (visible) => {
        panel.classList.toggle('show', visible);
        toggleBtn.classList.toggle('active', visible);
        toggleBtn.setAttribute('aria-expanded', visible ? 'true' : 'false');
    };

    toggleBtn.addEventListener('click', () => {
        const nowVisible = !panel.classList.contains('show');
        setPanelVisible(nowVisible);
    });
    if (closeBtn) closeBtn.addEventListener('click', () => setPanelVisible(false));

    // Close when clicking outside
    document.addEventListener('click', (e) => {
        if (!panel.classList.contains('show')) return;
        const withinPanel = panel.contains(e.target);
        const clickedToggle = toggleBtn.contains(e.target);
        if (!withinPanel && !clickedToggle) setPanelVisible(false);
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && panel.classList.contains('show')) setPanelVisible(false);
    });

    if (applyBtn) applyBtn.addEventListener('click', () => {
        if (accentInput && accentInput.value) {
            setCssVar('--accent', accentInput.value);
            localStorage.setItem('accentColor', accentInput.value);
        }
        if (neonInput && neonInput.value) {
            setCssVar('--neon', neonInput.value);
            localStorage.setItem('neonColor', neonInput.value);
        }
        // Adjust neon-safe after applying
        ensureNeonContrast();
        setPanelVisible(false);
        showNotification('Theme colors applied', 'success');
    });

    if (resetBtn) resetBtn.addEventListener('click', () => {
        const defaultAccent = '#FFD700';
        const defaultNeon = '#FFA500';
        setCssVar('--accent', defaultAccent);
        setCssVar('--neon', defaultNeon);
        ensureNeonContrast();
        localStorage.removeItem('accentColor');
        localStorage.removeItem('neonColor');
        if (accentInput) accentInput.value = defaultAccent;
        if (neonInput) neonInput.value = defaultNeon;
        showNotification('Theme colors reset', 'info');
    });
}

function setCssVar(name, value) {
    document.documentElement.style.setProperty(name, value);
}

function toColorInput(value) {
    // Accept values like rgb(), hsl(), or already hex; try to convert to hex if needed
    if (/^#/.test(value)) return value;
    // Best-effort parse for rgb(r,g,b)
    const m = value.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);
    if (m) {
        const r = (+m[1]).toString(16).padStart(2,'0');
        const g = (+m[2]).toString(16).padStart(2,'0');
        const b = (+m[3]).toString(16).padStart(2,'0');
        return `#${r}${g}${b}`;
    }
    return value;
}

// --- Theme color helpers for professional contrast ---
function ensureNeonContrast() {
    // Determine background reference by theme (gradients -> use base color)
    const isLight = document.body.classList.contains('light');
    const bg = isLight ? '#ffffff' : '#0a0a0a';

    // Get current neon
    let neonVal = getComputedStyle(document.documentElement).getPropertyValue('--neon').trim();
    if (!neonVal) neonVal = '#FFA500';
    const neonHex = toColorInput(neonVal);

    const minRatio = 4.5; // WCAG AA for normal text
    let safe = neonHex;
    try {
        const ratio = contrastRatio(neonHex, bg);
        if (ratio < minRatio) {
            // Adjust lightness towards better contrast depending on bg
            safe = adjustForContrast(neonHex, bg, minRatio);
        }
    } catch (e) {
        // Fallbacks
        safe = isLight ? '#cc7a00' : '#ffd24d';
    }
    setCssVar('--neon-safe', safe);
}

function parseColorToRGB(str) {
    if (!str) return { r: 0, g: 0, b: 0 };
    if (str.startsWith('#')) {
        const hex = str.replace('#','');
        const full = hex.length === 3 ? hex.split('').map(c=>c+c).join('') : hex;
        const num = parseInt(full, 16);
        return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }
    const m = str.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);
    if (m) return { r: +m[1], g: +m[2], b: +m[3] };
    return { r: 0, g: 0, b: 0 };
}

function relativeLuminance(hexOrRgb) {
    const { r, g, b } = parseColorToRGB(hexOrRgb);
    const srgb = [r, g, b].map(v => v / 255).map(v => v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
    return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}

function contrastRatio(c1, c2) {
    const L1 = relativeLuminance(c1);
    const L2 = relativeLuminance(c2);
    const lighter = Math.max(L1, L2);
    const darker = Math.min(L1, L2);
    return (lighter + 0.05) / (darker + 0.05);
}

function rgbToHex(r, g, b) {
    return '#' + [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
}

function rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h /= 6;
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
}

function hslToRgb(h, s, l) {
    h /= 360; s /= 100; l /= 100;
    if (s === 0) {
        const v = Math.round(l * 255);
        return { r: v, g: v, b: v };
    }
    const hue2rgb = (p, q, t) => {
        if (t < 0) t += 1;
        if (t > 1) t -= 1;
        if (t < 1/6) return p + (q - p) * 6 * t;
        if (t < 1/2) return q;
        if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
        return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    const r = Math.round(hue2rgb(p, q, h + 1/3) * 255);
    const g = Math.round(hue2rgb(p, q, h) * 255);
    const b = Math.round(hue2rgb(p, q, h - 1/3) * 255);
    return { r, g, b };
}

function adjustForContrast(color, bg, minRatio) {
    // Move lightness away from bg: darken if bg is light; lighten if bg is dark
    const bgLum = relativeLuminance(bg);
    const isBgLight = bgLum > 0.5;
    const { r, g, b } = parseColorToRGB(color);
    let { h, s, l } = rgbToHsl(r, g, b);
    // Try up to 12 steps
    for (let step = 0; step < 12; step++) {
        const delta = 6; // percent per step
        l = Math.max(0, Math.min(100, l + (isBgLight ? -delta : delta)));
        const rgb = hslToRgb(h, s, l);
        const next = rgbToHex(rgb.r, rgb.g, rgb.b);
        if (contrastRatio(next, bg) >= minRatio) return next;
    }
    // Fallback
    return isBgLight ? '#8c5a00' : '#ffdd66';
}

// CSRF helper
function getCsrfToken() {
    const tag = document.querySelector('meta[name="csrf-token"]');
    return tag ? tag.getAttribute('content') : '';
}

// Determine the slot index of the movie card within its grid
function computeSlotPosition(el) {
    try {
        const card = el ? el.closest('.movie') : null;
        if (!card) return null;
        const grid = card.parentElement;
        if (!grid) return null;
        const siblings = Array.from(grid.children).filter(n => n.classList && n.classList.contains('movie'));
        const idx = siblings.indexOf(card);
        return idx >= 0 ? idx : null;
    } catch (_) {
        return null;
    }
}
