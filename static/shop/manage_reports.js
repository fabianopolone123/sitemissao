(function () {
    function showChartError(message) {
        document.querySelectorAll('.report-card canvas').forEach((canvas) => {
            const p = document.createElement('p');
            p.className = 'cart-meta';
            p.textContent = message;
            canvas.replaceWith(p);
        });
    }

    function getJson(id, fallback) {
        const el = document.getElementById(id);
        if (!el) {
            return fallback;
        }
        try {
            return JSON.parse(el.textContent);
        } catch (error) {
            return fallback;
        }
    }

    if (typeof Chart === 'undefined') {
        showChartError('Erro ao carregar graficos. Atualize a pagina (Ctrl+F5).');
        return;
    }

    const dailyLabels = getJson('chart-daily-labels', []);
    const dailyValues = getJson('chart-daily-values', []);
    const dailyCounts = getJson('chart-daily-counts', []);
    const paymentLabels = getJson('chart-payment-labels', []);
    const paymentCounts = getJson('chart-payment-counts', []);
    const paymentTotals = getJson('chart-payment-totals-data', []);
    const statusCounter = getJson('chart-status-counter', {});

    try {
        new Chart(document.getElementById('chart-daily-revenue'), {
            type: 'line',
            data: {
                labels: dailyLabels,
                datasets: [
                    {
                        label: 'R$ por dia',
                        data: dailyValues,
                        borderColor: '#19543d',
                        backgroundColor: 'rgba(25,84,61,0.2)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Qtd pedidos',
                        data: dailyCounts,
                        borderColor: '#d9a441',
                        backgroundColor: 'rgba(217,164,65,0.15)',
                        fill: false,
                        tension: 0.3,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2.2,
                scales: {
                    y: { beginAtZero: true },
                    y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } },
                },
            },
        });

    } catch (error) {
        console.error('Falha no grafico de faturamento diario:', error);
    }

    try {
        new Chart(document.getElementById('chart-payment-methods'), {
            type: 'bar',
            data: {
                labels: paymentLabels,
                datasets: [{
                    label: 'Quantidade',
                    data: paymentCounts,
                    backgroundColor: ['#19543d', '#d9a441', '#366f8a', '#a04f4f'],
                }],
            },
            options: { responsive: true, maintainAspectRatio: true, aspectRatio: 2.2, scales: { y: { beginAtZero: true } } },
        });

    } catch (error) {
        console.error('Falha no grafico de pedidos por forma de pagamento:', error);
    }

    try {
        new Chart(document.getElementById('chart-payment-totals'), {
            type: 'doughnut',
            data: {
                labels: paymentLabels,
                datasets: [{
                    label: 'Total',
                    data: paymentTotals,
                    backgroundColor: ['#19543d', '#d9a441', '#366f8a', '#a04f4f'],
                }],
            },
            options: { responsive: true, maintainAspectRatio: true, aspectRatio: 2.2 },
        });

    } catch (error) {
        console.error('Falha no grafico de valor por forma de pagamento:', error);
    }

    try {
        new Chart(document.getElementById('chart-status'), {
            type: 'pie',
            data: {
                labels: ['Pago + Entregue', 'Pago + Nao entregue', 'Nao pago'],
                datasets: [{
                    data: [
                        statusCounter.paid_delivered || 0,
                        statusCounter.paid_undelivered || 0,
                        statusCounter.unpaid || 0,
                    ],
                    backgroundColor: ['#2f8a5c', '#d9a441', '#9b2c2c'],
                }],
            },
            options: { responsive: true, maintainAspectRatio: true, aspectRatio: 2.2 },
        });
    } catch (error) {
        console.error('Falha no grafico de status:', error);
    }
})();
