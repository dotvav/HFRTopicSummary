// ==UserScript==
// @author       MycRub @ HFR
// @name         [HFR] Résumé quotidien par topic
// @description  Utilise une API pour générer le résumé d'une journée pour vos topics préférés.
// @icon         https://forum.hardware.fr/favicon.ico
// @namespace    https://mycrub.net
// @version      0.1
// @match        https://forum.hardware.fr/forum2.php*
// @grant        GM_addStyle
// ==/UserScript==

// Historique
// 0.1      - Première release

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
            /* Add these to enable modal content scrolling */
            overflow-y: auto;
            padding: 20px 0;
        }
        .modal-content {
            background-color: #F7F7F7;
            /* Change margin to be smaller on mobile */
            margin: 20px auto;
            padding: 20px;
            border: 1px solid #DEDFDF;
            width: 80%;
            max-width: 600px;
            /* Ensure modal content doesn't overflow viewport */
            max-height: calc(100vh - 40px);
            display: flex;
            flex-direction: column;
        }
        .modal-header {
            display: flex;
            justify-content: flex-start;
            align-items: center;
            background-color: #001932;
            padding: 5px;
            color: white;
            /* Ensure header stays at top */
            flex-shrink: 0;
        }
        .modal-header h2 {
            margin: 0;
            color: white;
            font-size: 13px;
            font-family: Arial, Helvetica, sans-serif;
            font-weight: bold;
            margin-right: 10px;
        }
        .date-input {
            margin-right: auto;
            background-color: #F7F7F7;
            border: 1px solid #DEDFDF;
            padding: 1px 3px;
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
        .summary-content {
            border: 1px solid #DEDFDF;
            padding: 10px;
            margin-top: 15px;
            background-color: white;
            white-space: pre-wrap;
            font-family: Arial, Helvetica, sans-serif;
            /* Add these for scrolling summary content */
            overflow-y: auto;
            flex-grow: 1;
            /* Set a minimum height to ensure modal isn't too small */
            min-height: 100px;
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

            if (Date.now() - startTime > 180000) {
                summaryContent.innerHTML = 'La génération plend plus de temps que prévu. Revenez un peu plus tard.';
                return;
            }

            if (data.status === 'in_progress') {
                await new Promise(resolve => setTimeout(resolve, 20000));
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

    function sanitizeAndDisplaySummary(summary) {
        const div = document.createElement('div');
        
        const sanitized = summary
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;')
            .replace(/&lt;b&gt;/g, '<b>')
            .replace(/&lt;\/b&gt;/g, '</b>')
            .replace(/&lt;i&gt;/g, '<i>')
            .replace(/&lt;\/i&gt;/g, '</i>')
            .replace(
                /(https?:\/\/[^\s]+)/g, 
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );

        const summaryContent = modal.querySelector('.summary-content');
        summaryContent.innerHTML = sanitized;
    }

    async function fetchSummary(date) {
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

        const cached = SummaryCache.get(topicId, date);
        if (cached && cached.status === 'completed') {
            sanitizeAndDisplaySummary(cached.summary);
            return;
        }

        try {
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

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>Résumé de la journée :</h2>
                <input type="date" 
                    class="date-input" 
                    value="${getYesterday()}"
                    max="${getYesterday()}"
                >
                <span class="close">&times;</span>
            </div>
            <div class="summary-content"></div>
        </div>
    `;
    document.body.appendChild(modal);

    SummaryCache.cleanup();

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
            fetchSummary(modal.querySelector('.date-input').value);
        };
    }

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

    modal.querySelector('.date-input').addEventListener('change', (e) => {
        fetchSummary(e.target.value);
    });
})();
