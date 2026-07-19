import os
import sqlglot
from sqlglot import exp
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_core.callbacks import BaseCallbackHandler

class GroqTokenTracker(BaseCallbackHandler):
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.tool_logs = []
        self.current_tool = None
        self.current_tool_input = None

    def clear_tool_logs(self):
        self.tool_logs = []
        self.current_tool = None
        self.current_tool_input = None

    def on_llm_end(self, response, **kwargs):

        for generation_list in response.generations:
            for generation in generation_list:

                if not hasattr(generation, "message"):
                    continue

                msg = generation.message

                # ---------- Preferred ----------
                if getattr(msg, "usage_metadata", None):

                    usage = msg.usage_metadata

                    self.prompt_tokens += usage.get("input_tokens", 0)
                    self.completion_tokens += usage.get("output_tokens", 0)
                    self.total_tokens += usage.get("total_tokens", 0)

                # ---------- Older LangChain ----------
                elif hasattr(msg, "response_metadata"):

                    usage = msg.response_metadata.get("token_usage", {})

                    self.prompt_tokens += usage.get("prompt_tokens", 0)
                    self.completion_tokens += usage.get("completion_tokens", 0)
                    self.total_tokens += usage.get("total_tokens", 0)

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.current_tool = serialized.get("name", "unknown")
        self.current_tool_input = input_str

    def on_tool_end(self, output, **kwargs):
        if self.current_tool == "sql_db_query":
            self.tool_logs.append({
                "query": self.current_tool_input,
                "result": output
            })
        self.current_tool = None
        self.current_tool_input = None


ALLOWED_TABLES = {
    "gold_fact_sales",
    "gold_agg_product_metrics",
    "gold_agg_country_metrics",
    "gold_agg_monthly_trends",
    "gold_agg_customer_rfm"
}
MAX_ROW_LIMIT = 100

def secure_and_format_sql(sql_query: str) -> str:
    try:
        statements = sqlglot.parse(sql_query, read="sqlite")
        if len(statements) > 1:
            raise ValueError("SECURITY BLOCK: Multiple SQL statements are strictly forbidden.")
        
        ast = statements[0]

        if not isinstance(ast, exp.Select):
            raise ValueError("SECURITY BLOCK: Only SELECT queries are permitted.")

        with_clause = ast.args.get("with")
        if with_clause and with_clause.args.get("recursive"):
            raise ValueError("SECURITY BLOCK: Recursive CTEs are forbidden due to memory limits.")

        for table in ast.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name not in ALLOWED_TABLES:
                raise ValueError(f"SECURITY BLOCK: Access to table '{table_name}' is denied. Only Gold layer tables are allowed.")

        for join in ast.find_all(exp.Join):
            if join.side == "CROSS" or (not join.args.get("on") and not join.args.get("using")):
                raise ValueError("SECURITY BLOCK: Cartesian joins are forbidden to prevent performance degradation.")

        # Generate a safe limit node by parsing a dummy query
        safe_limit_node = sqlglot.parse_one(f"SELECT 1 LIMIT {MAX_ROW_LIMIT}").args.get("limit")
        
        limit_expr = ast.args.get("limit")
        if limit_expr:
            try:
                # Attempt to extract the integer value of the existing limit
                current_limit = int(limit_expr.expression.this)
                if current_limit > MAX_ROW_LIMIT:
                    ast.set("limit", safe_limit_node)
            except Exception:
                # If existing limit is unparsable (e.g., subquery), overwrite it
                ast.set("limit", safe_limit_node)
        else:
            # If no limit exists, inject the safe limit
            ast.set("limit", safe_limit_node)

        return ast.sql(dialect="sqlite")

    except sqlglot.errors.ParseError as e:
        raise ValueError(f"PARSING ERROR: Invalid SQL syntax generated. Details: {e}")


CUSTOM_SYSTEM_PROMPT = """
You are an expert Retail Business Intelligence Analyst.

Your task is to answer business questions by generating SQLite SQL.

=========================
DATABASE
=========================

This database follows the Medallion Architecture.

Tables:

1. gold_fact_sales
Transaction-level sales.

Columns:
invoice_no
stock_code
product_description
quantity
invoice_date
unit_price
customer_id
country
is_cancelled
total_line_price
invoice_year
invoice_month
invoice_year_month

------------------------------------------------

2. gold_agg_product_metrics

Aggregated product KPIs.

Contains:
net_units_sold
net_revenue
total_cancellations
distinct_transactions

------------------------------------------------

3. gold_agg_country_metrics

Aggregated country KPIs.

Contains:
total_registered_customers
total_invoices
net_revenue

------------------------------------------------

4. gold_agg_monthly_trends

Monthly KPIs.

Contains:
net_monthly_revenue
gross_monthly_revenue
total_refunded_amount
return_rate
monthly_transactions

------------------------------------------------

5. gold_agg_customer_rfm

Customer level KPIs.

Contains:
frequency_of_purchase
monetary_value
average_order_value

=========================
BUSINESS RULES
=========================

Cancelled transaction:

is_cancelled = 1

Completed transaction:

is_cancelled = 0

Net Revenue:

Revenue excluding cancelled invoices.

Gross Revenue:

Revenue before removing cancellations.

Refund Amount:

Revenue of cancelled invoices.

Customer Spend:

SUM(total_line_price)
WHERE is_cancelled = 0

=========================
ROUTING RULES
=========================

Use Aggregate tables whenever the requested metric already exists.

Examples:

country revenue
→ gold_agg_country_metrics

monthly revenue
→ gold_agg_monthly_trends

product revenue
→ gold_agg_product_metrics

customer ranking
→ gold_agg_customer_rfm

Transaction filtering
specific invoices
custom calculations
→ gold_fact_sales

=========================
VERY IMPORTANT
=========================

If the user asks:

"What is the total net revenue?"

DO NOT scan gold_fact_sales.

Instead execute:

SELECT SUM(net_revenue)
FROM gold_agg_country_metrics;

------------------------------------

If the user asks:

"What is the total gross revenue?"

Execute

SELECT SUM(gross_monthly_revenue)
FROM gold_agg_monthly_trends;

------------------------------------

If the user asks revenue for a specific month,
query gold_agg_monthly_trends.

If the user asks revenue for a country,
query gold_agg_country_metrics.

If the user asks revenue for a product,
query gold_agg_product_metrics.

Only use gold_fact_sales when aggregation tables cannot answer the question.

=========================
SQL RULES
=========================

Never invent columns.

Never invent tables.

Never use SELECT *.

Return only SQL.

After sql_db_query_checker ALWAYS execute sql_db_query.

Never stop after sql_db_query_checker.

The final answer MUST come from sql_db_query observation, never from the generated SQL.
"""

def initialize_groq_sql_agent(db_uri: str, api_key: str,tracker=None):
    
    # 1. Stop Token Leakage: Only expose Gold tables to LangChain
    db = SQLDatabase.from_uri(
        db_uri, 
        include_tables=list(ALLOWED_TABLES)
        
    )
    
    # 2. Injecting the Security Firewall (Interceptor)
    original_db_run = db.run
    
    def safe_db_run(command, *args, **kwargs):
        print(f"\n[Security Firewall] Original Query: {command.strip()}")
        try:
            safe_query = secure_and_format_sql(command)
            print(f"[Security Firewall] Secured Query: {safe_query}")
            return original_db_run(safe_query, *args, **kwargs)
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"[Security Firewall] BLOCKED! {error_msg}")
            return error_msg
        
    db.run = safe_db_run

    os.environ["GROQ_API_KEY"] = api_key

    callbacks = [tracker] if tracker else []
    
    llm = ChatGroq(
        temperature=0.0,
        model_name="llama-3.3-70b-versatile",
        callbacks=callbacks
    )
    
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        prefix=CUSTOM_SYSTEM_PROMPT,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )
    
    return agent_executor

if __name__ == "__main__":
    DATABASE_URI = "sqlite:///retail_gold.db"
    GROQ_API_KEY = ""
    
    try:
        agent = initialize_groq_sql_agent(DATABASE_URI, GROQ_API_KEY)
        test_query = "How many countries do we sell to?"
        
        response = agent.invoke({"input": test_query})
        print("\nFinal Analytical Result:")
        print(response['output'])
        
    except Exception as error:
        print(f"Execution failed with error: {error}")