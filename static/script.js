let nextScanTime = null;

async function updateDashboard() {
    try {
        // Fetch Status for Countdown & Metrics
        const statResp = await fetch('/status');
        const statData = await statResp.json();
        if (statData.last_scan_time) {
            nextScanTime = (statData.last_scan_time * 1000) + (statData.scan_interval * 60 * 1000);
        }
        if (statData.total_scans !== undefined) {
            const el = document.getElementById('total-scans-count');
            if (el) el.innerText = statData.total_scans.toLocaleString();
        }

        // Fetch Balance
        const balResp = await fetch('/balance');
        const balData = await balResp.json();
        document.getElementById('wallet-balance').innerText = `$${balData.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}`;

        // Fetch Stats (Open positions and History)
        const response = await fetch('/stats');
        const data = await response.json();

        // 1. Update Cards
        const openPositions = data.open_positions || {};
        const history = data.history || [];
        
        document.getElementById('open-positions-count').innerText = Object.keys(openPositions).length;
        document.getElementById('total-trades').innerText = data.total_completed_trades || 0;

        // 2. Render Active Positions
        const posTable = document.getElementById('positions-table-body');
        if (Object.keys(openPositions).length === 0) {
            posTable.innerHTML = '<tr><td colspan="5" class="empty-state">No open positions. Searching for entries...</td></tr>';
        } else {
            posTable.innerHTML = '';
            for (const [symbol, pos] of Object.entries(openPositions)) {
                posTable.innerHTML += `
                    <tr>
                        <td class="symbol">${symbol}</td>
                        <td>$${pos.entry_price.toLocaleString()}</td>
                        <td>${pos.amount.toFixed(4)}</td>
                        <td class="positive">$${pos.tp_price.toLocaleString()}</td>
                        <td class="negative">$${pos.sl_price.toLocaleString()}</td>
                    </tr>
                `;
            }
        }

        // 3. Render History
        const histTable = document.getElementById('history-table-body');
        if (history.length === 0) {
            histTable.innerHTML = '<tr><td colspan="5" class="empty-state">No historical data yet. Waiting for exits...</td></tr>';
        } else {
            histTable.innerHTML = '';
            // We want the most recent trades at the top
            const reversedHistory = [...history].reverse();
            reversedHistory.forEach(trade => {
                histTable.innerHTML += `
                    <tr>
                        <td class="symbol">${trade.symbol}</td>
                        <td>$${trade.entry_price.toLocaleString()}</td>
                        <td>$${trade.exit_price.toLocaleString()}</td>
                        <td><span class="badge" style="background: rgba(88, 166, 255, 0.1); color: #58a6ff; border: none;">${trade.exit_reason}</span></td>
                        <td style="color: var(--text-secondary); font-size: 0.875rem;">${trade.closed_at}</td>
                    </tr>
                `;
            });
        }

        // 4. Update AI Analysis Feed and Sentiment
        const analysisResponse = await fetch('/analysis');
        const analysisData = await analysisResponse.json();
        
        let avgSentiment = 0;
        let count = 0;
        if (Object.keys(analysisData).length > 0) {
            for (const data of Object.values(analysisData)) {
                avgSentiment += data.sentiment;
                count++;
            }
            if (count > 0) {
                document.getElementById('latest-sentiment').innerText = (avgSentiment / count).toFixed(2);
            }
        }

        const historyResponse = await fetch('/analysis_history');
        const feedHistory = await historyResponse.json();
        const feed = document.getElementById('analysis-feed');
        
        if (feedHistory.length > 0) {
            feed.innerHTML = '';
            // Display newest at the top
            const reversedFeed = [...feedHistory].reverse();
            reversedFeed.forEach(data => {
                const signalClass = data.signal === "BUY" ? "positive" : "text-secondary";
                feed.innerHTML += `
                    <div style="margin-bottom: 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 0.5rem;">
                        <span class="symbol" style="color: var(--accent-color)">[${data.timestamp}]</span> 
                        <span style="font-weight: 800">${data.symbol}:</span> 
                        Price <span style="color:white">$${data.price.toLocaleString()}</span> | 
                        Sentiment <span class="positive">${data.sentiment.toFixed(2)}</span> | 
                        Fib <span style="color:#e1e1e1">${data.fib_level || 'None'}</span> | 
                        Signal: <span class="${signalClass}" style="font-weight:bold">${data.signal}</span>
                    </div>
                `;
            });
        }

    } catch (error) {
        console.error("Dashboard update failed:", error);
        document.getElementById('bot-status').innerText = "Connection Error";
        document.getElementById('bot-status').style.background = "rgba(218, 54, 51, 0.2)";
        document.getElementById('bot-status').style.color = "#f85149";
    }
}

// Global Countdown Loop
setInterval(() => {
    if (!nextScanTime) return;
    const now = Date.now();
    const diff = Math.max(0, nextScanTime - now);
    
    if (diff === 0) {
        document.getElementById('scan-info').innerHTML = 'Scanning now... <span style="animation: pulse 1s infinite;">📡</span>';
    } else {
        const mins = Math.floor(diff / 60000);
        const secs = Math.floor((diff % 60000) / 1000);
        document.getElementById('scan-info').innerText = `Next scan in: ${mins}m ${secs.toString().padStart(2, '0')}s`;
    }
}, 1000);

// Update every 30 seconds
setInterval(updateDashboard, 30000);
updateDashboard();
