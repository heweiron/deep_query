import re
import pyodbc
import requests


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
    conn.close()
    return results

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



# Main
if __name__ == "__main__":
    schema = get_sql_server_schema()
    question = "List all employees hired after 2020 with salary over 70000"
    sql_query = ask_deepseek_ollama(question, schema)

    print("\nGenerated SQL Query:\n", sql_query)

    # Optional: Run it
    try:
        result = run_sql_query(sql_query)

        if result:
            # Get column names from cursor description
            column_names = [desc[0] for desc in result[0].cursor_description]
            explanation = ask_deepseek_to_explain_result(question, result, column_names)
            print("\nExplanation:\n", explanation)
        else:
            print("No results to explain.")


        print("\nQuery Result:")
        for row in result:
            print(row)
    except Exception as e:
        print("\nSQL Execution Error:", e)