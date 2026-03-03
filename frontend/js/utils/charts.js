/**
 * Charts Utility — Chart.js wrapper for insight visualizations
 * Accepts flexible argument signatures matching all caller patterns.
 */
const Charts = {
    instances: {},

    /**
     * Destroy existing chart instance to prevent memory leaks
     */
    destroy(id) {
        if (this.instances[id]) {
            this.instances[id].destroy();
            delete this.instances[id];
        }
    },

    /**
     * Sentiment Trend Line Chart
     * Supports: sentimentTrend(canvasId, labels, {positive:[...], neutral:[...], negative:[...]})
     *       or: sentimentTrend(canvasId, trendDataObj)  where trendDataObj = {feature: [{date, sentiment}]}
     */
    sentimentTrend(canvasId, labelsOrData, seriesDataOpt) {
        this.destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        let labels, datasets;

        const chartColors = {
            positive: '#22c55e', neutral: '#eab308', negative: '#ef4444',
            'Checkout': '#ef4444', 'Onboarding': '#f97316', 'Performance': '#eab308',
            'UI/UX': '#22c55e', 'Payment': '#8b5cf6'
        };

        if (seriesDataOpt && typeof seriesDataOpt === 'object') {
            // Called as (canvasId, labels, {positive, neutral, negative})
            labels = labelsOrData;
            datasets = Object.entries(seriesDataOpt).map(([name, values]) => ({
                label: name.charAt(0).toUpperCase() + name.slice(1),
                data: values,
                borderColor: chartColors[name] || '#6366f1',
                backgroundColor: (chartColors[name] || '#6366f1') + '20',
                fill: true,
                tension: 0.4, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2,
            }));
        } else {
            // Called as (canvasId, trendDataObj) where values are [{date, sentiment}]
            const trendData = labelsOrData;
            const entries = Object.entries(trendData);
            labels = entries[0]?.[1]?.map(p => p.date) || [];
            datasets = entries.map(([feature, points]) => ({
                label: feature,
                data: points.map(p => p.sentiment),
                borderColor: chartColors[feature] || '#6366f1',
                backgroundColor: (chartColors[feature] || '#6366f1') + '20',
                fill: false, tension: 0.4, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2,
            }));
        }

        this.instances[canvasId] = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'bottom', labels: { usePointStyle: true, padding: 16, font: { size: 11 } } },
                    tooltip: { backgroundColor: '#1f2937', titleFont: { size: 12 }, bodyFont: { size: 11 }, padding: 12, cornerRadius: 8 }
                },
                scales: {
                    x: { ticks: { maxTicksLimit: 10, font: { size: 10 } }, grid: { display: false } },
                    y: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 10 } } }
                }
            }
        });
    },

    /**
     * Sentiment Distribution Doughnut Chart
     * Supports: sentimentDoughnut(id, {positive: N, neutral: N, negative: N})
     *       or: sentimentDoughnut(id, [{sentiment:'positive', count:N}, ...])
     */
    sentimentDoughnut(canvasId, distribution) {
        this.destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const colorMap = { positive: '#22c55e', negative: '#ef4444', neutral: '#eab308', mixed: '#f97316' };
        let labels, values, bgColors;

        if (Array.isArray(distribution)) {
            labels = distribution.map(d => d.sentiment || d.label);
            values = distribution.map(d => d.count || d.value);
        } else {
            // Object like {positive: 65, neutral: 25, negative: 10}
            labels = Object.keys(distribution);
            values = Object.values(distribution);
        }
        bgColors = labels.map(l => colorMap[l] || '#6366f1');

        this.instances[canvasId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels.map(l => l.charAt(0).toUpperCase() + l.slice(1)),
                datasets: [{ data: values, backgroundColor: bgColors, borderWidth: 0, hoverOffset: 8 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '70%',
                plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } } }
            }
        });
    },

    /**
     * Theme Frequency Bar Chart
     * Supports: themeBar(id, labels, values)
     *       or: themeBar(id, themesArray)
     */
    themeBar(canvasId, labelsOrThemes, valuesOpt) {
        this.destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        let labels, data, colors;
        if (valuesOpt !== undefined) {
            labels = labelsOrThemes;
            data = valuesOpt;
            colors = data.map(() => '#6366f1cc');
        } else {
            labels = labelsOrThemes.map(t => t.name);
            data = labelsOrThemes.map(t => t.frequency || t.value || t.mention_count || 0);
            colors = labelsOrThemes.map(t => (Helpers.sentimentColor(t.sentiment_avg || t.sentiment || 0)) + 'cc');
        }

        this.instances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ label: 'Mentions', data, backgroundColor: colors, borderRadius: 6, borderSkipped: false }] },
            options: {
                responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 10 } } },
                    y: { grid: { display: false }, ticks: { font: { size: 11 } } }
                }
            }
        });
    },

    /**
     * Engagement Metrics Bar Chart
     * Supports: engagementBar(id, labels, responseData, completionData)
     *       or: engagementBar(id, metricsArray)
     */
    engagementBar(canvasId, labelsOrMetrics, responseDataOpt, completionDataOpt) {
        this.destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        let labels, d1, d2;
        if (responseDataOpt !== undefined) {
            labels = labelsOrMetrics;
            d1 = responseDataOpt;
            d2 = completionDataOpt || d1.map(() => 0);
        } else {
            const metrics = labelsOrMetrics;
            labels = metrics.map(m => m.channel || m.label);
            d1 = metrics.map(m => m.total_sessions || m.total || 0);
            d2 = metrics.map(m => m.completed_sessions || m.completed || 0);
        }

        this.instances[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { label: 'Responses', data: d1, backgroundColor: '#6366f1cc', borderRadius: 6 },
                    { label: 'Completion %', data: d2, backgroundColor: '#22c55ecc', borderRadius: 6 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } } },
                scales: { x: { grid: { display: false } }, y: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 10 } } } }
            }
        });
    },

    /**
     * Priority Score Radar Chart
     */
    priorityRadar(canvasId, recommendations) {
        this.destroy(canvasId);
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;

        const top5 = recommendations.slice(0, 5);
        this.instances[canvasId] = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Impact', 'Urgency', 'Confidence', 'Frequency', 'Effort (inv)'],
                datasets: top5.map((r, i) => ({
                    label: r.title.substring(0, 20),
                    data: [
                        r.impact_score * 100,
                        r.urgency_score * 100,
                        r.confidence * 100,
                        Math.min(r.supporting_count, 100),
                        (1 - r.effort_score) * 100
                    ],
                    borderColor: ['#6366f1', '#ef4444', '#22c55e', '#f97316', '#8b5cf6'][i],
                    backgroundColor: ['#6366f1', '#ef4444', '#22c55e', '#f97316', '#8b5cf6'][i] + '15',
                    borderWidth: 2,
                    pointRadius: 3,
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { font: { size: 10 }, usePointStyle: true } }
                },
                scales: {
                    r: {
                        min: 0, max: 100,
                        ticks: { display: false },
                        grid: { color: '#e5e7eb' },
                        pointLabels: { font: { size: 10 } }
                    }
                }
            }
        });
    }
};
