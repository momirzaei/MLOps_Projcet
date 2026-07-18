import pandas as pd
import sqlite3

def execute_medallion_pipeline(csv_file_path, database_path):
    print("Initiating Medallion Architecture Pipeline...")
    connection = sqlite3.connect(database_path)

    # ==========================================
    # Bronze Layer: Ingestion of Raw Data
    # ==========================================
    print("[Bronze Layer] Ingesting raw data...")
    df_raw = pd.read_csv(csv_file_path)
    #df_raw.to_sql('bronze_sales_raw', connection, if_exists='replace', index=False)
    print(f"[Bronze Layer] Successfully ingested {len(df_raw)} records.")

    # ==========================================
    # Silver Layer: Data Cleansing and Transformation
    # ==========================================
    print("[Silver Layer] Executing data cleansing and standardization...")
    df_silver = df_raw.copy()

    # 1. Standardize column naming conventions
    column_mapping = {
        'Country': 'country',
        'Customer ID': 'customer_id',
        'Price': 'unit_price',
        'InvoiceDate': 'invoice_date',
        'Quantity': 'quantity',
        'Description': 'product_description',
        'StockCode': 'stock_code',
        'Invoice': 'invoice_no'
    }
    df_silver.rename(columns=column_mapping, inplace=True)

    # 2. Handle missing Customer IDs (Imputation for Guest Checkouts)
    # Assigning -1 to retain total sales volume while segregating unknown users
    df_silver['customer_id'] = df_silver['customer_id'].fillna(-1)
    
    # 3. Handle Cancellations and Anomalies
    # Identify cancelled orders based on the 'C' prefix in the invoice number
    df_silver['is_cancelled'] = df_silver['invoice_no'].astype(str).str.upper().str.startswith('C').astype(int)
    
    # Filter absolute anomalies (zero/negative prices or zero quantity), retaining valid negative quantities (returns)
    df_silver = df_silver[(df_silver['quantity'] != 0) & (df_silver['unit_price'] > 0)]

    # 4. Feature Engineering: Calculate total price per line item
    # Note: For cancellations (is_cancelled=1), quantity is negative, resulting in a negative total_line_price
    df_silver['total_line_price'] = df_silver['quantity'] * df_silver['unit_price']

    # 5. Temporal transformations
    df_silver['invoice_date'] = pd.to_datetime(df_silver['invoice_date'], errors='coerce')
    df_silver['invoice_year_month'] = df_silver['invoice_date'].dt.strftime('%Y-%m')
    df_silver['invoice_year'] = df_silver['invoice_date'].dt.year
    df_silver['invoice_month'] = df_silver['invoice_date'].dt.month
    
    df_silver['invoice_date'] = df_silver['invoice_date'].astype(str)

    df_silver.to_sql('silver_sales_cleansed', connection, if_exists='replace', index=False)
    print(f"[Silver Layer] Cleansing complete. Valid records: {len(df_silver)}.")

    # ==========================================
    # Gold Layer: Consumption-Ready Data (Facts & Aggregates)
    # ==========================================
    print("[Gold Layer] Generating Fact and Aggregate tables...")

    # Table 1: Consumption Fact Table
    df_silver.to_sql('gold_fact_sales', connection, if_exists='replace', index=False)

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
    pd.read_sql(query_product_metrics, connection).to_sql('gold_agg_product_metrics', connection, if_exists='replace', index=False)

    # Table 3: Geographical (Country) Metrics Aggregation
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
    pd.read_sql(query_country_metrics, connection).to_sql('gold_agg_country_metrics', connection, if_exists='replace', index=False)

    # Table 4: Temporal (Monthly) Trends Aggregation
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
    pd.read_sql(query_monthly_trends, connection).to_sql('gold_agg_monthly_trends', connection, if_exists='replace', index=False)

    # Table 5: Customer RFM Analysis
    # Excluding guest checkouts (-1) as lifecycle analysis requires known identities
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
    pd.read_sql(query_rfm_analysis, connection).to_sql('gold_agg_customer_rfm', connection, if_exists='replace', index=False)

    print("[Gold Layer] All analytical tables generated successfully.")
    print("Pipeline execution completed without errors.")
    
    connection.close()

if __name__ == "__main__":
    csv_path = 'online_retail_II.csv'
    db_path = 'retail_medallion_gold2.db'
    execute_medallion_pipeline(csv_path, db_path)