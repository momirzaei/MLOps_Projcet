import pandas as pd
import sqlite3

def build_bronze_layer(csv_file_path, bronze_db_path):
    print("Initiating Bronze Layer Pipeline...")
    
    # Connect only to the Bronze database
    conn_bronze = sqlite3.connect(bronze_db_path)

    print("[Bronze Layer] Ingesting raw data...")
    df_raw = pd.read_csv(csv_file_path)
    df_raw.to_sql('bronze_sales_raw', conn_bronze, if_exists='replace', index=False)
    
    print(f"[Bronze Layer] Successfully ingested {len(df_raw)} records into {bronze_db_path}.")
    conn_bronze.close()

if __name__ == "__main__":
    csv_path = 'online_retail_II.csv'
    bronze_db = 'retail_bronze.db'
    build_bronze_layer(csv_path, bronze_db)