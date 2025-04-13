async function fetchCarCountLastHour() {
    const countSpan = document.getElementById('car-count-last-hour');
    try {
        const response = await fetch('/api/count_last_hour?label=car');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        countSpan.textContent = data.count_last_hour !== undefined ? data.count_last_hour : 'Error';
    } catch (error) {
        console.error('Error fetching car count:', error);
        countSpan.textContent = 'Error';
    }
}

async function fetchAndDisplayLabelChart() {
    const ctx = document.getElementById('labelChart').getContext('2d');
    try {
        const response = await fetch('/api/label_counts');
         if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json(); // Expects {label1: count1, label2: count2, ...}

        const labels = Object.keys(data);
        const counts = Object.values(data);

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: '# of Detections',
                    data: counts,
                    backgroundColor: 'rgba(54, 162, 235, 0.6)', // Example color
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error fetching or displaying label chart:', error);
    }
}


document.addEventListener('DOMContentLoaded', () => {
    fetchCarCountLastHour();
    fetchAndDisplayLabelChart();
});