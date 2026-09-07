import os
from openai import OpenAI
from dotenv import load_dotenv
from mydb import get_schema_summary
from mydb import execute_query

load_dotenv()

client=OpenAI()

db_name = input("Enter database name: ")
Db_information = get_schema_summary(db_name)

user_input = input("Enter your question: ")

final_prompt = f'''
Database Information:\n{Db_information}\n\nUser Question:\n{user_input}\n\n
Answer the user's question based on the database information
provided. Give SQL Server (T-SQL) syntax only — use TOP instead of LIMIT.
Only generate a single SELECT statement. Never generate INSERT, UPDATE,
DELETE, DROP, ALTER, TRUNCATE, MERGE, EXEC, or any other data-modifying
or multi-statement SQL.
Return the raw SQL query with no markdown formatting, code fences, or explanation.'''

response=client.responses.create(
    model="gpt-4.1-mini",
    input=final_prompt)


query=response.output_text.strip()

final_response=execute_query(query, db_name)
print(final_response)