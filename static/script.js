async function updateDashboard() {
    try {
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

    } catch (error) {
        console.error("Dashboard update failed:", error);
        document.getElementById('bot-status').innerText = "Connection Error";
        document.getElementById('bot-status').style.background = "rgba(218, 54, 51, 0.2)";
        document.getElementById('bot-status').style.color = "#f85149";
    }
}

// Update every 30 seconds
setInterval(updateDashboard, 30000);
updateDashboard();
