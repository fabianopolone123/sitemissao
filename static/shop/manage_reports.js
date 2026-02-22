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
        showChartError('Erro ao carregar gráficos. Atualize a página (Ctrl+F5).');
        return;
    }

    const productLabels = getJson('chart-product-labels', []);
    const productCounts = getJson('chart-product-counts', []);
    const paymentLabels = getJson('chart-payment-labels', []);
    const paymentTotals = getJson('chart-payment-totals-data', []);

    try {
        new Chart(document.getElementById('chart-products-sold'), {
            type: 'bar',
            data: {
                labels: productLabels,
                datasets: [{
                    label: 'Quantidade vendida',
                    data: productCounts,
                    backgroundColor: ['#19543d', '#d9a441', '#366f8a', '#a04f4f', '#7d5cc6', '#2f8a5c'],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2.2,
                scales: { y: { beginAtZero: true } },
            },
        });
    } catch (error) {
        console.error('Falha no gráfico de produtos vendidos:', error);
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
        console.error('Falha no gráfico de valor por forma de pagamento:', error);
    }

})();
