# -*- coding: utf-8 -*-
import os
import json
import time

def estimate_capacity(manifest_path, target_rows_millions):
    if not os.path.exists(manifest_path):
        print(f"Error: Manifest {manifest_path} not found.")
        return
        
    with open(manifest_path, 'r') as f: manifest = json.load(f)
        
    base_rows = manifest.get('metadata', {}).get('total_records', 1685923)
    base_size_bytes = 0
    for tbl, meta in manifest.get('tables', {}).items():
        base_size_bytes += meta.get('size', 0)
        
    multiplier = (target_rows_millions * 1000000) / max(base_rows, 1)
    est_raw_size_mb = (base_size_bytes * multiplier) / (1024 * 1024)
    min_est_mb = est_raw_size_mb * 2.0
    max_est_mb = est_raw_size_mb * 3.0
    
    print("==================================================")
    print("   MySQL Capacity Estimator (Based on Manifest)   ")
    print("==================================================")
    print(f"Base Manifest Rows: {base_rows:,}")
    print(f"Base Manifest Raw Size: {base_size_bytes / (1024*1024):.2f} MB")
    print(f"Target Rows: {target_rows_millions} Million")
    print(f"Scale Multiplier: {multiplier:.2f}x")
    print(f"Estimated Raw CSV Size: {est_raw_size_mb:.2f} MB")
    print(f"Estimated MySQL InnoDB Size (Data + Index): {min_est_mb:.2f} MB - {max_est_mb:.2f} MB")
    
def run_benchmark():
    print("\n==================================================")
    print("   Read-Only DB Benchmark Tool                    ")
    print("==================================================")
    
    db_host = os.getenv("MOD_DB_HOST") or os.getenv("MOD_V2_DB_HOST")
    db_name = os.getenv("MOD_DB_NAME") or os.getenv("MOD_V2_DB_NAME")
    db_user = os.getenv("MOD_DB_USER") or os.getenv("MOD_V2_DB_USER")
    db_password = os.getenv("MOD_DB_PASSWORD") or os.getenv("MOD_V2_DB_PASSWORD")
    db_port = os.getenv("MOD_DB_PORT") or os.getenv("MOD_V2_DB_PORT") or "3306"
    
    if not (db_host and db_user and db_password and db_name):
        print("Status: UNKNOWN")
        print("Warning: Missing database credentials in environment variables.")
        print("Not fabricating performance metrics. Pure estimator mode.")
        return
        
    from sqlalchemy import create_engine, text
    from urllib.parse import quote_plus
    
    # Redact password for display
    print(f"Connecting to host: {db_host}, database: {db_name}, user: {db_user}, port: {db_port}")
    
    pwd = quote_plus(db_password)
    db_url = f"mysql+pymysql://{db_user}:{pwd}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            t0 = time.time()
            row = conn.execute(text("SELECT COUNT(*) FROM org_unit")).scalar()
            t1 = time.time()
            print(f"Query 1 (COUNT org_unit): {t1-t0:.4f}s [Result: {row}]")
            
            t0 = time.time()
            row = conn.execute(text("SELECT COUNT(*) FROM business_document")).scalar()
            t1 = time.time()
            print(f"Query 2 (COUNT business_document): {t1-t0:.4f}s [Result: {row}]")
    except Exception as e:
        print("Status: ERROR")
        print(f"Benchmark connection or execution failed.")

if __name__ == '__main__':
    estimate_capacity('/home/ubuntu/mod/artifacts/v2-sim-data/manifest.json', 10.0)
    run_benchmark()
