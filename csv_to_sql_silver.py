import pandas as pd
import sqlite3

def build_silver_layer(bronze_db_path, silver_db_path):
    print("Initiating Silver Layer Pipeline...")
    
    # 1. Read from Bronze
    conn_bronze = sqlite3.connect(bronze_db_path)
    print("[Silver Layer] Extracting raw data from Bronze database...")
    df_silver = pd.read_sql("SELECT * FROM bronze_sales_raw", conn_bronze)
    conn_bronze.close()

    # 2. Execute Data Cleansing
    print("[Silver Layer] Executing data cleansing and standardization...")
    
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

    df_silver['customer_id'] = df_silver['customer_id'].fillna(-1)
    df_silver['is_cancelled'] = df_silver['invoice_no'].astype(str).str.upper().str.startswith('C').astype(int)
    df_silver = df_silver[(df_silver['quantity'] != 0) & (df_silver['unit_price'] > 0)]

    df_silver['total_line_price'] = df_silver['quantity'] * df_silver['unit_price']

    df_silver['invoice_date'] = pd.to_datetime(df_silver['invoice_date'], errors='coerce')
    df_silver['invoice_year_month'] = df_silver['invoice_date'].dt.strftime('%Y-%m')
    df_silver['invoice_year'] = df_silver['invoice_date'].dt.year
    df_silver['invoice_month'] = df_silver['invoice_date'].dt.month
    df_silver['invoice_date'] = df_silver['invoice_date'].astype(str)

    # 3. Write to Silver
    conn_silver = sqlite3.connect(silver_db_path)
    df_silver.to_sql('silver_sales_cleansed', conn_silver, if_exists='replace', index=False)
    print(f"[Silver Layer] Cleansing complete. Saved {len(df_silver)} records to {silver_db_path}.")
    conn_silver.close()

if __name__ == "__main__":
    bronze_db = 'retail_bronze.db'
    silver_db = 'retail_silver.db'
    build_silver_layer(bronze_db, silver_db)