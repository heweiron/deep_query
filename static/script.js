async function askQuestion() {
    const question = document.getElementById('question').value;
    if (!question.trim()) return;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('sqlDiv').style.display = 'none';
    document.getElementById('resultDiv').style.display = 'none';
    document.getElementById('explanationDiv').style.display = 'none';

    try {
        const res = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        const data = await res.json();

        if (data.error) {
            alert("Error: " + data.error);
            return;
        }

        document.getElementById('sqlDiv').style.display = 'block';
        document.getElementById('sqlQuery').textContent = data.sql;

        // Display table
        const table = document.getElementById('resultsTable');
        table.innerHTML = '';

        const header = document.createElement('tr');
        data.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            header.appendChild(th);
        });
        table.appendChild(header);

        data.results.forEach(row => {
            const tr = document.createElement('tr');
            data.columns.forEach(col => {
                const td = document.createElement('td');
                td.textContent = row[col];
                tr.appendChild(td);
            });
            table.appendChild(tr);
        });

        document.getElementById('resultDiv').style.display = 'block';

        document.getElementById('explanationDiv').style.display = 'block';

        // Convert <think> blocks to styled divs
        let explanationHtml = data.explanation.replace(/<think>([\s\S]*?)<\/think>/gi, (match, content) => {
            return `<div class="think-block">${content.trim()}</div>`;
        });

        // Convert markdown to HTML
        explanationHtml = marked.parse(explanationHtml);

        // Display it
        const explanationEl = document.getElementById('explanationText');
        explanationEl.innerHTML = explanationHtml;

    } catch (e) {
        alert("Something went wrong: " + e.message);
    } finally {
        // Hide loader no matter what
        document.getElementById('loading').style.display = 'none';
    }
}
