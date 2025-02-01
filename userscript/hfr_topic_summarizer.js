// ==UserScript==
// @name         HFR Topic Summarizer
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Add summary functionality to HFR topics
// @author       Your name
// @match        https://forum.hardware.fr/forum2.php*
// @match        https://forum.hardware.fr/hfr/*
// @grant        GM_addStyle
// ==/UserScript==

(function() {
    'use strict';

    let currentPollController = null;  // To track and cancel current polling

    GM_addStyle(`
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.4);
        }
        .modal-content {
            background-color: #F7F7F7;
            margin: 15% auto;
            padding: 20px;
            border: 1px solid #DEDFDF;
            width: 80%;
            max-width: 600px;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            background-color: #001932;
            padding: 5px;
            color: white;
        }
        .modal-header h2 {
            margin: 0;
            color: white;
            font-size: 13px;
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
        }
        .close {
            color: white;
            font-weight: bold;
            cursor: pointer;
            font-size: 20px;
        }
        .close:hover {
            color: #DEDFDF;
        }
        .modal-body {
            margin-bottom: 15px;
        }
        .date-input {
            margin-right: 10px;
        }
        .submit-btn {
            border: 1px solid #000080;
            background-color: #F7F7F7;
            color: #000080;
            padding: 1px 3px;
            cursor: pointer;
        }
        .summary-content {
            border: 1px solid #DEDFDF;
            padding: 10px;
            margin-top: 10px;
            background-color: white;
            white-space: pre-wrap;    /* Preserve whitespace and line breaks */
            font-family: Arial, Helvetica, sans-serif;  /* Use forum's font instead of monospace */
        }
    `);
    
    const SummaryCache = {
        KEY_PREFIX: 'hfr_summary_',
        EXPIRY_DAYS: 7,
    
        createKey(topicId, date) {
            return `${this.KEY_PREFIX}${topicId}_${date}`;
        },
    
        set(topicId, date, data) {
            const key = this.createKey(topicId, date);
            const item = {
                data,
                timestamp: Date.now()
            };
            localStorage.setItem(key, JSON.stringify(item));
        },
    
        get(topicId, date) {
            const key = this.createKey(topicId, date);
            const item = localStorage.getItem(key);
            
            if (!item) return null;
            
            try {
                const parsed = JSON.parse(item);
                const age = Date.now() - parsed.timestamp;
                if (age > this.EXPIRY_DAYS * 24 * 60 * 60 * 1000) {
                    localStorage.removeItem(key);
                    return null;
                }
                return parsed.data;
            } catch (e) {
                localStorage.removeItem(key);
                return null;
            }
        },
    
        cleanup() {
            const keys = Object.keys(localStorage);
            const expiry = this.EXPIRY_DAYS * 24 * 60 * 60 * 1000;
            const now = Date.now();
    
            keys.forEach(key => {
                if (key.startsWith(this.KEY_PREFIX)) {
                    try {
                        const item = JSON.parse(localStorage.getItem(key));
                        if (now - item.timestamp > expiry) {
                            localStorage.removeItem(key);
                        }
                    } catch (e) {
                        localStorage.removeItem(key);
                    }
                }
            });
        }
    };    

    function getYesterday() {
        const date = new Date();
        date.setDate(date.getDate() - 1);
        return date.toISOString().split('T')[0];
    }

    function isDateValid(date) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const checkDate = new Date(date);
        return checkDate < today;
    }

    function getTopicId() {
        const cat = document.querySelector('input[name="cat"]')?.value;
        const subcat = document.querySelector('input[name="subcat"]')?.value;
        const post = document.querySelector('input[name="post"]')?.value;
        
        if (!cat || !subcat || !post) {
            console.error('Could not find all required topic identifiers', { cat, subcat, post });
            return null;
        }
        
        return `${cat}#${subcat}#${post}`;
    }

    async function pollSummary(topicId, date, startTime, summaryContent, signal) {
        try {
            const params = new URLSearchParams({
                topic_id: topicId,
                date: date
            });
            
            const url = `https://ivc6ivtvmg.execute-api.eu-west-3.amazonaws.com/devo/summarize?${params.toString()}`;
            const response = await fetch(url);
            const data = await response.json();

            // Check if polling was cancelled
            if (signal.aborted) {
                return;
            }

            if (data.status === 'completed') {
                SummaryCache.set(topicId, date, data);
                sanitizeAndDisplaySummary(data.summary);
                return;
            }

            if (data.status === 'error') {
                summaryContent.textContent = 'Une erreur s\'est produite, réessayez plus tard.';
                return;
            }

            // Check if we've been polling for more than 3 minutes
            if (Date.now() - startTime > 180000) {
                summaryContent.innerHTML = 'La génération plend plus de temps que prévu. Revenez un peu plus tard.';
                return;
            }

            // Continue polling if still in progress
            if (data.status === 'in_progress') {
                await new Promise(resolve => setTimeout(resolve, 20000)); // 20s interval
                if (!signal.aborted) {
                    await pollSummary(topicId, date, startTime, summaryContent, signal);
                }
            }
        } catch (error) {
            if (!signal.aborted) {
                summaryContent.textContent = 'Erreur de communication avec le serveur';
                console.error('Error:', error);
            }
        }
    }

    // Sanitize and display function
    function sanitizeAndDisplaySummary(summary) {
        const div = document.createElement('div');
        
        // Basic HTML sanitization
        const sanitized = summary
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            // Optionally preserve some safe HTML tags
            .replace(/&lt;b&gt;/g, '<b>')
            .replace(/&lt;\/b&gt;/g, '</b>')
            .replace(/&lt;i&gt;/g, '<i>')
            .replace(/&lt;\/i&gt;/g, '</i>')
            // Convert URLs to links
            .replace(
                /(https?:\/\/[^\s]+)/g, 
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );

        const summaryContent = modal.querySelector('.summary-content');
        summaryContent.innerHTML = sanitized;
    }

    async function fetchSummary(date) {
        // Cancel any existing polling
        if (currentPollController) {
            currentPollController.abort();
        }
        
        const summaryContent = modal.querySelector('.summary-content');
        
        if (!isDateValid(date)) {
            summaryContent.textContent = 'Seuls les résumés d\'hier et des jours précédents sont disponibles';
            return;
        }
        
        const topicId = getTopicId();
        
        if (!topicId) {
            summaryContent.textContent = 'Impossible de déterminer l\'identifiant du topic';
            return;
        }

        // Check cache first
        const cached = SummaryCache.get(topicId, date);
        if (cached && cached.status === 'completed') {
            sanitizeAndDisplaySummary(cached.summary);
            return;
        }

        try {
            // Add spinner CSS if not already added
            if (!document.querySelector('#spinner-style')) {
                const style = document.createElement('style');
                style.id = 'spinner-style';
                style.textContent = `
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                    .spinner {
                        display: inline-block;
                        width: 20px;
                        height: 20px;
                        border: 3px solid #f3f3f3;
                        border-top: 3px solid #3498db;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                        margin-right: 10px;
                        vertical-align: middle;
                    }
                `;
                document.head.appendChild(style);
            }

            summaryContent.innerHTML = '<div class="spinner"></div>Résumé en cours de création. Cela peut prendre plusieurs minutes.';
            
            const params = new URLSearchParams({
                topic_id: topicId,
                date: date
            });
            
            const url = `https://ivc6ivtvmg.execute-api.eu-west-3.amazonaws.com/devo/summarize?${params.toString()}`;
            const response = await fetch(url);
            const data = await response.json();

            if (data.status === 'completed') {
                SummaryCache.set(topicId, date, data);
                sanitizeAndDisplaySummary(data.summary);
            } else if (data.status === 'in_progress') {
                currentPollController = new AbortController();
                pollSummary(topicId, date, Date.now(), summaryContent, currentPollController.signal);
            } else if (data.status === 'error') {
                summaryContent.textContent = 'Une erreur s\'est produite, réessayez plus tard.';
            } else {
                summaryContent.textContent = 'Statut inconnu.';
            }
        } catch (error) {
            summaryContent.textContent = 'Erreur de communication avec le serveur';
            console.error('Error:', error);
        }
    }

    // Create and setup modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Résumé</h2>
                <span class="close">&times;</span>
            </div>
            <div class="modal-body">
                <input type="date" class="date-input" value="${getYesterday()}">
                <button class="submit-btn">Obtenir le résumé</button>
            </div>
            <div class="summary-content"></div>
        </div>
    `;
    document.body.appendChild(modal);

    SummaryCache.cleanup();

    // Add summary button next to Go button
    const goButton = document.querySelector('input[type="submit"][value="Go"].boutton');
    if (goButton) {
        const summaryButton = document.createElement('input');
        summaryButton.type = 'button';
        summaryButton.value = 'Afficher le résumé';
        summaryButton.className = 'boutton';
        
        const separator = document.createTextNode(' - ');
        
        goButton.after(separator);
        separator.after(summaryButton);
        
        summaryButton.onclick = () => {
            modal.style.display = 'block';
            fetchSummary(getYesterday());
        };
    }

    // Modal event handlers
    modal.querySelector('.close').onclick = () => {
        if (currentPollController) {
            currentPollController.abort();
            currentPollController = null;
        }
        modal.style.display = 'none';
    };
    
    window.onclick = (event) => {
        if (event.target === modal) {
            if (currentPollController) {
                currentPollController.abort();
                currentPollController = null;
            }
            modal.style.display = 'none';
        }
    };

    modal.querySelector('.submit-btn').onclick = () => {
        const date = modal.querySelector('.date-input').value;
        fetchSummary(date);
    };
})();
