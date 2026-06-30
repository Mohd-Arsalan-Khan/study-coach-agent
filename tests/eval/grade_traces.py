import json
import os
import sys
import time
import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def evaluate():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    traces_path = os.path.join(base_dir, "artifacts", "traces", "generated_traces.json")
    config_path = os.path.join(base_dir, "tests", "eval", "eval_config.yaml")
    
    with open(traces_path, "r", encoding="utf-8") as f:
        traces_data = json.load(f)
        eval_cases = traces_data.get("eval_cases", [])
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    metrics = {m["name"]: m for m in config.get("custom_metrics", [])}
    metrics_to_run = config.get("metrics_to_run", [])
    
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY")
    )
    model = "meta/llama-3.1-8b-instruct"
    
    print("Evaluating traces...")
    
    results = {}
    for case in eval_cases:
        case_id = case.get("id")
        prompt = json.dumps(case.get("prompt"))
        response = case.get("response")
        agent_data = json.dumps(case.get("agent_data"))
        
        results[case_id] = {}
        for m_name in metrics_to_run:
            m = metrics.get(m_name)
            if not m or "prompt_template" not in m:
                continue
                
            eval_prompt = m["prompt_template"].format(
                prompt=prompt,
                response=response,
                agent_data=agent_data
            )
            
            max_retries = 3
            delay = 5
            for attempt in range(max_retries + 1):
                try:
                    time.sleep(2) # Respect rate limit
                    res = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": eval_prompt}],
                        response_format={"type": "json_object"}
                    )
                    score_data = json.loads(res.choices[0].message.content)
                    results[case_id][m_name] = score_data
                    print(f"[{case_id}] {m_name}: Score {score_data.get('score')} - {score_data.get('explanation')[:50]}...")
                    break
                except Exception as e:
                    if attempt < max_retries:
                        print(f"[{case_id}] {m_name} Encountered error, retrying in {delay} seconds (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        print(f"[{case_id}] {m_name} Evaluation Failed: {e}")
                        results[case_id][m_name] = {"score": 0, "explanation": str(e)}
                        break
                
    # Show scorecard
    print("\n\n" + "="*50)
    print("FINAL SCORECARD")
    print("="*50)
    for case_id, metric_scores in results.items():
        print(f"\nScenario: {case_id}")
        for m_name, score_data in metric_scores.items():
            print(f"  {m_name}: {score_data.get('score')}/5")
            print(f"  Reason: {score_data.get('explanation')}")
            
if __name__ == "__main__":
    evaluate()
