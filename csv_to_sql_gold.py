import pandas as pd
import sqlite3

def build_gold_layer(silver_db_path, gold_db_path):
    print("Initiating Gold Layer Pipeline...")
    
    # 1. Read from Silver
    conn_silver = sqlite3.connect(silver_db_path)
    print("[Gold Layer] Extracting cleansed data from Silver database...")
    df_silver = pd.read_sql("SELECT * FROM silver_sales_cleansed", conn_silver)
    
    # 2. Connect to Gold
    conn_gold = sqlite3.connect(gold_db_path)
    print("[Gold Layer] Generating Fact and Aggregate tables...")

    # Table 1: Fact Table
    df_silver.to_sql('gold_fact_sales', conn_gold, if_exists='replace', index=False)

    # Table 2: Product Metrics Aggregation
    query_product_metrics = """
        SELECT 
            product_description,
            stock_code,
            SUM(quantity) as net_units_sold,
            SUM(total_line_price) as net_revenue,
            SUM(is_cancelled) as total_cancellations,
            COUNT(DISTINCT invoice_no) as distinct_transactions
        FROM silver_sales_cleansed
        GROUP BY product_description, stock_code
        ORDER BY net_revenue DESC
    """
    pd.read_sql(query_product_metrics, conn_silver).to_sql('gold_agg_product_metrics', conn_gold, if_exists='replace', index=False)

    # Table 3: Country Metrics
    query_country_metrics = """
        SELECT 
            country,
            COUNT(DISTINCT CASE WHEN customer_id != -1 THEN customer_id END) as total_registered_customers,
            COUNT(DISTINCT invoice_no) as total_invoices,
            SUM(total_line_price) as net_revenue
        FROM silver_sales_cleansed
        GROUP BY country
        ORDER BY net_revenue DESC
    """
    pd.read_sql(query_country_metrics, conn_silver).to_sql('gold_agg_country_metrics', conn_gold, if_exists='replace', index=False)

    # Table 4: Monthly Trends
    query_monthly_trends = """
        SELECT 
            invoice_year_month,
            invoice_year,
            invoice_month,
            SUM(total_line_price) as net_monthly_revenue,
            SUM(CASE WHEN is_cancelled = 0 THEN total_line_price ELSE 0 END) as gross_monthly_revenue,
            SUM(CASE WHEN is_cancelled = 1 THEN ABS(total_line_price) ELSE 0 END) as total_refunded_amount,
            SUM(CASE WHEN is_cancelled = 1 THEN ABS(total_line_price) ELSE 0 END) / 
                NULLIF(SUM(CASE WHEN is_cancelled = 0 THEN total_line_price ELSE 0 END), 0) as return_rate,
            COUNT(DISTINCT invoice_no) as monthly_transactions
        FROM silver_sales_cleansed
        GROUP BY invoice_year_month, invoice_year, invoice_month
        ORDER BY invoice_year_month ASC
    """
    pd.read_sql(query_monthly_trends, conn_silver).to_sql('gold_agg_monthly_trends', conn_gold, if_exists='replace', index=False)

    # Table 5: RFM Analysis
    query_rfm_analysis = """
        SELECT 
            customer_id,
            country,
            MAX(invoice_date) as last_purchase_date,
            COUNT(DISTINCT invoice_no) as frequency_of_purchase,
            SUM(total_line_price) as monetary_value,
            AVG(total_line_price) as average_order_value
        FROM silver_sales_cleansed
        WHERE customer_id != -1
        GROUP BY customer_id, country
        ORDER BY monetary_value DESC
    """
    pd.read_sql(query_rfm_analysis, conn_silver).to_sql('gold_agg_customer_rfm', conn_gold, if_exists='replace', index=False)

    print(f"[Gold Layer] All analytical tables generated successfully in {gold_db_path}.")
    
    conn_silver.close()
    conn_gold.close()

if __name__ == "__main__":
    silver_db = 'retail_silver.db'
    gold_db = 'retail_gold.db'
    build_gold_layer(silver_db, gold_db)