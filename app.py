from flask import Flask, request, render_template, jsonify
import re
import pyodbc
import requests

app = Flask(__name__)


# Step 1: Get schema from SQL Server
def get_sql_server_schema():
    conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=Rong\sqlexpress;DATABASE=devDb;Trusted_Connection=yes;")
    cursor = conn.cursor()

    schema = ""
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """)
    
    current_table = None
    for row in cursor.fetchall():
        table = f"{row.TABLE_SCHEMA}.{row.TABLE_NAME}"
        if table != current_table:
            schema += f"\nTable: {table}\n"
            current_table = table
        schema += f"- {row.COLUMN_NAME} ({row.DATA_TYPE})\n"

    conn.close()
    return schema.strip()

# Step 2: Ask DeepSeek via Ollama
def ask_deepseek_ollama(nl_question, schema):
    url = "http://localhost:11434/api/chat"

    prompt = f"""
You are an assistant that writes **only raw SQL Server queries** — no explanations, no markdown, no formatting.

Here is the database schema:
{schema}

Convert this natural language question into a SQL query:
"{nl_question}"
"""

    payload = {
        "model": "deepseek-r1:8b",
        "messages": [
            {"role": "system", "content": "You are a helpful SQL assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    full_response = response.json()['message']['content']
    sql_only = extract_sql_only(full_response)
    return sql_only.strip()

# Step 3: get the generated SQL Query
def extract_sql_only(response_text):
    # Remove <think> sections
    response_text = re.sub(r"<think>[\s\S]*?</think>", "", response_text, flags=re.IGNORECASE)

    # Remove markdown-style ```sql blocks (if any)
    response_text = re.sub(r"```sql\s*([\s\S]*?)```", r"\1", response_text, flags=re.IGNORECASE)

    # Strip leading/trailing spaces
    return response_text.strip()


# Step 4: Optional — run the generated SQL
def run_sql_query(sql):
    conn = pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=Rong\\sqlexpress;DATABASE=devDb;Trusted_Connection=yes;")
    cursor = conn.cursor()
    cursor.execute(sql)
    results = cursor.fetchall()
    column_names = [desc[0] for desc in cursor.description]
    conn.close()
    return results, column_names

# Step 5: Have AI read the result and give user a human answer
def ask_deepseek_to_explain_result(nl_question, result_rows, column_names):
    url = "http://localhost:11434/api/chat"

    # Convert SQL result into a Markdown table
    header = "| " + " | ".join(column_names) + " |"
    separator = "| " + " | ".join(["---"] * len(column_names)) + " |"
    rows = "\n".join(["| " + " | ".join(str(col) for col in row) + " |" for row in result_rows])
    markdown_table = f"{header}\n{separator}\n{rows}"

    prompt = f"""
You are a helpful assistant that explains SQL query results in simple terms.

The user asked this question:
"{nl_question}"

The SQL query result is:
{markdown_table}

Please summarize what this result shows.
"""

    payload = {
        "model": "deepseek-r1:8b",
        "messages": [
            {"role": "system", "content": "You are a helpful SQL assistant who explains query results."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()['message']['content'].strip()




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data['question']

    try:
        schema = get_sql_server_schema()
        sql_query = ask_deepseek_ollama(question, schema)
        results, column_names = run_sql_query(sql_query)

        if results:
            explanation = ask_deepseek_to_explain_result(question, results, column_names)
        else:
            explanation = "No results found for this query."

        # Convert result rows to list of dicts for easy display in JS
        result_data = [dict(zip(column_names, row)) for row in results]

        return jsonify({
            'sql': sql_query,
            'results': result_data,
            'columns': column_names,
            'explanation': explanation
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
