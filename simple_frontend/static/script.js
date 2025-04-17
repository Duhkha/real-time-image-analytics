let labelBarChart = null;
let timelineLineChart = null;
const API_BASE_URL = '';

async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            let errorMsg = `HTTP error ${response.status}`;
            try { const errorData = await response.json(); errorMsg += `: ${errorData.error || 'Unknown API error'}`; } catch (e) { /* Ignore */ }
            throw new Error(errorMsg);
        }
        return await response.json();
    } catch (error) { console.error(`Error fetching ${url}:`, error); throw error; }
}

async function updateTotalCountForSelectedLabel(selectedLabel) {
    console.log(`Updating total count text for: ${selectedLabel}`);
    const countStrong = document.getElementById('selected-label-count');
    const labelTextSpan = document.getElementById('selected-label-text');
    if (!countStrong || !labelTextSpan) { console.error("Count display elements not found."); return; }

    countStrong.textContent = 'Loading...';
    labelTextSpan.textContent = selectedLabel.charAt(0).toUpperCase() + selectedLabel.slice(1);

    try {
        const countApiUrl = `${API_BASE_URL}/api/count_specific?label=${encodeURIComponent(selectedLabel)}`;
        const countData = await fetchData(countApiUrl);
        countStrong.textContent = countData.count_in_range !== undefined ? countData.count_in_range : 'N/A';
    } catch (error) {
        countStrong.textContent = 'Error';
    }
}

async function fetchAndDisplayLabelChart() {
    const canvas = document.getElementById('labelChart');
    if (!canvas) { console.error("Canvas ID 'labelChart' not found."); return []; } 
    const ctx = canvas.getContext('2d');
    try {
        const data = await fetchData(`${API_BASE_URL}/api/label_counts`); 
        const labels = data.labels || [];
        const counts = data.counts || [];

        if (labelBarChart) { labelBarChart.destroy(); }
        labelBarChart = new Chart(ctx, {
            type: 'bar', data: { labels: labels, datasets: [{ label: '# of Detections (Fixed Range)', data: counts, backgroundColor: 'rgba(75, 192, 192, 0.6)', borderColor: 'rgba(75, 192, 192, 1)', borderWidth: 1 }] },
            options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
        });
        return labels; 
    } catch (error) {
        console.error('Error fetching/displaying label chart:', error);
        if (ctx) ctx.fillText('Error loading chart data.', 10, 50);
        return [];
    }
}

async function fetchAndDisplayTimelineChart(labelsToPlot) {
    const canvas = document.getElementById('timelineChart');
    if (!canvas) { console.error("Canvas ID 'timelineChart' not found."); return; }
    if (!labelsToPlot || labelsToPlot.length === 0) {
         console.log("No labels provided to timeline chart.");
         if (timelineLineChart) { timelineLineChart.destroy(); timelineLineChart = null;}
         const ctx = canvas.getContext('2d');
         if(ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = '#6c757d'; ctx.font = '16px sans-serif'; ctx.textAlign = 'center'; ctx.fillText('No labels to display timeline for.', canvas.width / 2, 50); }
         return;
    }

    console.log(`Workspaceing timeline data for labels: ${labelsToPlot.join(', ')}`);
    const ctx = canvas.getContext('2d');
    const lineColors = [ 'rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)', 'rgba(255, 206, 86, 0.8)', 'rgba(75, 192, 192, 0.8)', 'rgba(153, 102, 255, 0.8)', 'rgba(255, 159, 64, 0.8)' ];
    const fixedTimeLabels = ["19:00", "20:00", "21:00", "22:00"];
    try {
        const params = new URLSearchParams();
        labelsToPlot.forEach(label => params.append('label', label));
        const apiUrl = `${API_BASE_URL}/api/timeline?${params.toString()}`;

        const data = await fetchData(apiUrl); 

        const datasets = [];
        let colorIndex = 0;

        for (const label of labelsToPlot) {
            const hourToCount = {};
            if (data.hasOwnProperty(label) && Array.isArray(data[label])) {
                data[label].forEach(point => {
                    const d = new Date(point.t);
                    const hourStr = d.toLocaleTimeString([], { hour: '2-digit', minute:'2-digit', hour12: false });
                    hourToCount[hourStr] = point.y;
                });
            }
            const counts = fixedTimeLabels.map(hour => hourToCount[hour] || 0);

            datasets.push({
                label: label, data: counts,
                borderColor: lineColors[colorIndex % lineColors.length],
                tension: 0.1, fill: false
            });
            colorIndex++;
        }

        if (timelineLineChart) { timelineLineChart.destroy(); }

        timelineLineChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: { labels: fixedTimeLabels, datasets: datasets },
            options: {
                responsive: true,
                scales: {
                    x: { type: 'category', title: { display: true, text: 'Hour (UTC)' } },
                    y: { beginAtZero: true, title: { display: true, text: 'Count' } }
                },
                plugins: {
                    legend: { position: 'top' },
                    tooltip: { mode: 'index', intersect: false }
                }
            }
        });
        console.log("Timeline chart created/updated for:", labelsToPlot.join(', '));

    } catch (error) {
        console.error('Error fetching or displaying timeline chart:', error);
        if(ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = 'red'; ctx.font = '16px sans-serif'; ctx.fillText('Error loading timeline data.', 10, 50); }
    }
}

document.addEventListener('DOMContentLoaded', async () => { 
    console.log("DOM Loaded. Initializing dashboard...");
    const labelSelectorTotal = document.getElementById('labelSelectorTotal');

    if (labelSelectorTotal) {
        labelSelectorTotal.addEventListener('change', (event) => {
            updateTotalCountForSelectedLabel(event.target.value);
        });
        updateTotalCountForSelectedLabel(labelSelectorTotal.value);
    } else {
         console.error("Total count selector dropdown not found!");
    }

    const topLabels = await fetchAndDisplayLabelChart(); 

    if (topLabels && topLabels.length > 0) {
        fetchAndDisplayTimelineChart(topLabels); 
    } else {
         console.warn("No top labels found to populate timeline chart initially.");
         fetchAndDisplayTimelineChart([]); 
    }
});