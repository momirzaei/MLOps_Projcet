import json
import time
import os
import re
import subprocess
import mlflow
from sql_agent import initialize_groq_sql_agent, GroqTokenTracker, CUSTOM_SYSTEM_PROMPT
from dotenv import load_dotenv

load_dotenv()

GOLDEN_SET_PATH = "golden_set.json"
DATABASE_URI = "sqlite:///retail_gold.db"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing! Please check your .env file.")

EXPERIMENT_NAME = "Medallion-Agent-Evaluation"

MODEL_NAME = "llama-3.3-70b-versatile"
TEMPERATURE = 0.0

# Pricing per 1M tokens (Llama-3-8b approx rates)
COST_PER_1M_INPUT = 0.05  
COST_PER_1M_OUTPUT = 0.08 

def get_dvc_data_version():
    """Extracts the latest Git commit hash as the data version."""
    try:
        commit_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode('utf-8')
        return commit_hash
    except Exception:
        return "unknown_version"

def extract_numeric_values(text):
    """Extracts all numbers (integers and floats) from a string."""
    return [float(x) for x in re.findall(r'-?\d+\.?\d*', str(text))]

def verify_result(expected_preview, raw_observation, final_output):
    """
    Deterministic evaluation: Checks if the expected number exists in the 
    raw database observation or final output with a 0.01 tolerance.
    """
    if not expected_preview or len(expected_preview) == 0:
        return False
        
    expected_val = list(expected_preview[0].values())[0]
    
    if isinstance(expected_val, (int, float)):
        extracted_numbers = extract_numeric_values(raw_observation) + extract_numeric_values(final_output)
        for num in extracted_numbers:
            if abs(num - expected_val) <= 0.01:  
                return True
        return False
    else:
        expected_str = str(expected_val).lower()
        return expected_str in str(raw_observation).lower() or expected_str in str(final_output).lower()

def evaluate_and_log():
    with open(GOLDEN_SET_PATH, 'r', encoding='utf-8') as f:
        golden_set = json.load(f)

    BATCH_SIZE = 8
    test_subset = golden_set[0:BATCH_SIZE] 

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow_tracking.db")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    tracker = GroqTokenTracker()
    
    agent = initialize_groq_sql_agent(DATABASE_URI, GROQ_API_KEY, tracker=tracker)
    data_version = get_dvc_data_version()

    print(f" Starting evaluation batch (Questions 1 to {len(test_subset)})...")

    with mlflow.start_run(run_name=f"Batch_Eval_{data_version}"):
        
        metrics = {
            "successful_executions": 0,
            "correct_results": 0,
            "total_latency": 0,
            "total_retries_and_blocks": 0
        }
        
        all_generated_sqls = []

        with open("system_prompt_snapshot.txt", "w", encoding="utf-8") as f:
            f.write(CUSTOM_SYSTEM_PROMPT)
        mlflow.log_artifact("system_prompt_snapshot.txt")

        for idx, item in enumerate(test_subset):
            q_id = item["id"]
            question = item["question"]
            expected_preview = item["result_preview"]
            
            print(f"\n--- [Q{q_id}] {question} ---")
            start_time = time.time()
            
            try:
                tracker.clear_tool_logs()
                
                response = agent.invoke(
                    {"input": question},
                    config={"callbacks": [tracker]}
                )
                
                latency = time.time() - start_time
                metrics["total_latency"] += latency
                metrics["successful_executions"] += 1
                
                final_output = response.get('output', '')
                
                raw_db_observation = ""
                step_retries = 0
                
                all_generated_sqls.append("\n=======================")
                all_generated_sqls.append(f"Q{q_id}: {question}")
                
                if not tracker.tool_logs:
                    all_generated_sqls.append(" MODEL HALLUCINATED! (No DB queries executed)")
                else:
                    for i, log in enumerate(tracker.tool_logs):
                        all_generated_sqls.append(f"--- Query {i+1} ---")
                        all_generated_sqls.append(f"SQL: {log['query']}")
                        all_generated_sqls.append(f"DB Result: {log['result']}")
                        
                        raw_db_observation += str(log['result'])
                        if "Error" in str(log['result']) or "BLOCKED" in str(log['result']):
                            step_retries += 1
                
                metrics["total_retries_and_blocks"] += step_retries
                all_generated_sqls.append(f"Final Output: {final_output}")
                
                is_correct = verify_result(expected_preview, raw_db_observation, final_output)
                
                if is_correct:
                    metrics["correct_results"] += 1
                    print(f" PASS | Latency: {latency:.2f}s | Retries: {step_retries}")
                else:
                    print(f" FAIL | Expected: {expected_preview} | Got Raw: {raw_db_observation}")

            except Exception as e:
                print(f"CRITICAL FAIL | {str(e)}")
                all_generated_sqls.append(f"CRITICAL FAIL | {str(e)}")

        # Calculate Final Aggregated Metrics
        total_q = len(test_subset)
        exec_acc = (metrics["successful_executions"] / total_q) * 100 if total_q > 0 else 0
        res_acc = (metrics["correct_results"] / total_q) * 100 if total_q > 0 else 0
        avg_latency = (metrics["total_latency"] / total_q) if total_q > 0 else 0
        
        # Financial Cost Calculation
        est_cost = ((tracker.prompt_tokens / 1_000_000) * COST_PER_1M_INPUT) + \
                   ((tracker.completion_tokens / 1_000_000) * COST_PER_1M_OUTPUT)

        mlflow.log_param("model_name", MODEL_NAME)
        mlflow.log_param("temperature", TEMPERATURE)
        mlflow.log_param("data_version_hash", data_version)
        mlflow.log_param("batch_size", total_q)
        mlflow.log_param("golden_set_file", GOLDEN_SET_PATH)
        mlflow.log_param("database_uri", DATABASE_URI)
        
        mlflow.log_metric("execution_accuracy", exec_acc)
        mlflow.log_metric("result_accuracy", res_acc)
        mlflow.log_metric("avg_latency_sec", avg_latency)
        mlflow.log_metric("total_firewall_blocks_and_retries", metrics["total_retries_and_blocks"])
        mlflow.log_metric("total_tokens", tracker.total_tokens)
        mlflow.log_metric("estimated_cost_usd", est_cost)
        
        with open("generated_sqls.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(all_generated_sqls))
        mlflow.log_artifact("generated_sqls.txt")

        print("\n==========================================")
        print("MLFLOW EVALUATION REPORT")
        print(f"Data Version:     {data_version}")
        print(f"Execution Acc:    {exec_acc:.1f}%")
        print(f"Result Acc:       {res_acc:.1f}%")
        print(f"Tokens Consumed:  {tracker.total_tokens}")
        print(f"Estimated Cost:   ${est_cost:.6f}")
        print("==========================================")
        print("Run 'mlflow ui' in your terminal to see the dashboard.")

if __name__ == "__main__":
    evaluate_and_log()