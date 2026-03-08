(function () {
    function wrapLabel(label, maxLineLength) {
        const text = String(label || '').trim();
        if (!text) {
            return ['Item'];
        }

        const words = text.split(/\s+/);
        const lines = [];
        let currentLine = '';

        words.forEach((word) => {
            const nextLine = currentLine ? `${currentLine} ${word}` : word;
            if (nextLine.length <= maxLineLength || !currentLine) {
                currentLine = nextLine;
                return;
            }
            lines.push(currentLine);
            currentLine = word;
        });

        if (currentLine) {
            lines.push(currentLine);
        }

        return lines;
    }

    function showChartError(message) {
        document.querySelectorAll('.report-card canvas').forEach((canvas) => {
            const paragraph = document.createElement('p');
            paragraph.className = 'cart-meta';
            paragraph.textContent = message;
            canvas.replaceWith(paragraph);
        });
    }

    function getJson(id, fallback) {
        const element = document.getElementById(id);
        if (!element) {
            return fallback;
        }
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return fallback;
        }
    }

    if (typeof Chart === 'undefined') {
        showChartError('Erro ao carregar graficos. Atualize a pagina (Ctrl+F5).');
        return;
    }

    const productLabels = getJson('chart-product-labels', []);
    const productCounts = getJson('chart-product-counts', []);
    const paymentLabels = getJson('chart-payment-labels', []);
    const paymentTotals = getJson('chart-payment-totals-data', []);
    const wrappedProductLabels = productLabels.map((label) => wrapLabel(label, 18));

    try {
        new Chart(document.getElementById('chart-products-sold'), {
            type: 'bar',
            data: {
                labels: wrappedProductLabels,
                datasets: [{
                    label: 'Quantidade vendida',
                    data: productCounts,
                    backgroundColor: ['#19543d', '#d9a441', '#366f8a', '#a04f4f', '#7d5cc6', '#2f8a5c'],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                    },
                    y: {
                        ticks: {
                            autoSkip: false,
                        },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title(items) {
                                const firstItem = items && items[0];
                                if (!firstItem) {
                                    return '';
                                }
                                return productLabels[firstItem.dataIndex] || '';
                            },
                        },
                    },
                },
            },
        });
    } catch (error) {
        console.error('Falha no grafico de produtos vendidos:', error);
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
})();
