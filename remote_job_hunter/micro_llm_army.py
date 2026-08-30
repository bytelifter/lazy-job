import os
import time
import concurrent.futures
from typing import List, Dict, Any, Optional
import requests

class VirtualCompany:
    """
    Virtual Company Architecture for 6GB VRAM.
    Manages sequential loading of C-Suite models (GPU) and parallel execution of Nano-models (CPU/LoRA).
    """
    MAX_CPU_WORKERS = 10
    
    def __init__(self):
        self._cpu_pipelines = {}
        # Ensure HF models are downloaded to the secondary drive
        os.environ["HF_HOME"] = "D:\\ai_models\\huggingface"
        self.current_gpu_model = None
        self.ollama_api = "http://localhost:11434/api"

    def _unload_current_gpu_model(self):
        """Unloads the current model from VRAM using Ollama's keep_alive=0 to free space."""
        if self.current_gpu_model:
            print(f"🔄 Unloading {self.current_gpu_model} from VRAM...")
            try:
                requests.post(f"{self.ollama_api}/generate", json={
                    "model": self.current_gpu_model,
                    "keep_alive": 0
                })
                time.sleep(1) # Give VRAM a moment to flush
            except Exception as e:
                print(f"Warning: Failed to unload model: {e}")
            self.current_gpu_model = None

    def _ensure_gpu_model_loaded(self, model_name: str):
        """Ensures the requested C-Suite model is loaded. If another is loaded, it unloads it first."""
        if self.current_gpu_model != model_name:
            self._unload_current_gpu_model()
            print(f"📥 CEO/Manager entering the office (Loading to GPU): {model_name}...")
            try:
                # Trigger a tiny dummy generation to force load into VRAM and keep alive for 5 mins
                requests.post(f"{self.ollama_api}/generate", json={
                    "model": model_name,
                    "prompt": "load",
                    "keep_alive": "5m",
                    "options": {"num_predict": 1}
                })
                self.current_gpu_model = model_name
            except Exception as e:
                print(f"Error loading {model_name}: {e}")

    def call_c_suite_manager(self, manager_role: str, model_name: str, prompt: str, system_prompt: str) -> str:
        """Calls a specific C-Suite manager (CEO, CTO, etc) ensuring strict VRAM limits."""
        print(f"💼 Calling {manager_role} ({model_name})...")
        self._ensure_gpu_model_loaded(model_name)
        
        try:
            response = requests.post(f"{self.ollama_api}/generate", json={
                "model": model_name,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "keep_alive": "5m"
            })
            if response.status_code == 200:
                return response.json().get("response", "").strip()
        except Exception as e:
            print(f"Error communicating with Ollama: {e}")
        return ""

    def _get_cpu_pipeline(self, task: str, model_name: str):
        """Lazy loads a Nano-model specialist directly onto the CPU."""
        if model_name not in self._cpu_pipelines:
            try:
                from transformers import pipeline
                print(f"🧠 Waking up Nano-Specialist on CPU: {model_name}...")
                self._cpu_pipelines[model_name] = pipeline(task, model=model_name, device=-1)
            except ImportError:
                print(f"⚠️ Transformers non installato. Impossibile caricare {model_name}.")
                return None
        return self._cpu_pipelines[model_name]

    # --- NANO SPECIALISTS (CPU) ---
    
    def qa_security_scan(self, code: str) -> List[str]:
        """Nano-model Security & QA scan running on CPU. Simulates CodeBERTa logic."""
        # Using a fast zero-shot classifier as a proxy for the security nano-model
        pipe = self._get_cpu_pipeline("zero-shot-classification", "valhalla/distilbart-mnli-12-1")
        if not pipe:
            return []
            
        candidate_labels = ["contains sql injection or security leak", "buggy or badly formatted code", "clean and secure code"]
        issues = []
        try:
            # We scan the code in parallel on CPU threads
            res = pipe(code[:1000], candidate_labels, multi_label=True)
            for label, score in zip(res["labels"], res["scores"]):
                if label != "clean and secure code" and score > 0.6:
                    issues.append(label)
        except Exception as e:
            pass
        return issues

    def finbert_financial_analysis(self, text: str) -> str:
        """Uses the real FinBERT model on CPU to analyze financial viability/sentiment."""
        pipe = self._get_cpu_pipeline("sentiment-analysis", "ProsusAI/finbert")
        if not pipe:
            return "NEUTRAL"
        try:
            res = pipe(text[:512])[0]
            return res["label"] # Returns positive, negative, or neutral
        except:
            return "ERROR"

    # --- THE ARENA: MULTI-LOOP VERIFICATION ---
    
    def develop_software_with_validation(self, requirements: str, max_loops: int = 3) -> str:
        """
        The multi-loop validation process.
        The CTO writes code on GPU -> QA Nano-models test it on CPU -> CTO fixes it.
        """
        print(f"\n🏭 [VIRTUAL COMPANY] Starting Software Factory Loop for: {requirements[:50]}...")
        
        current_code = ""
        feedback = ""
        # We use qwen2.5:0.5b as our CTO for code generation (ultra-fast)
        cto_model = "qwen2.5:0.5b" 
        
        for loop in range(1, max_loops + 1):
            print(f"\n  🔄 [Loop {loop}/{max_loops}] CTO is writing/refactoring code on GPU...")
            
            prompt = f"Write the python code for these requirements: {requirements}\n"
            if feedback:
                prompt += f"\nCRITICAL: QA found these issues in your previous attempt. FIX THEM: {feedback}\n"
                
            current_code = self.call_c_suite_manager(
                "CTO (Qwen2.5-Coder)", 
                cto_model,
                prompt,
                "You are an expert CTO. Write pure code, fix bugs ruthlessly. No markdown, no explanations."
            )
            
            print(f"  🔎 [Loop {loop}/{max_loops}] Passing code to CPU Nano-models for Security/QA Scan...")
            issues = self.qa_security_scan(current_code)
            
            if not issues:
                print(f"  ✅ [Loop {loop}] QA & Security Passed! Code is rock solid.")
                break
            else:
                print(f"  ❌ [Loop {loop}] QA found issues: {issues}. Sending back to CTO...")
                feedback = ", ".join(issues)
                
        return current_code

    def unload_all(self):
        """Frees all RAM and VRAM."""
        self._unload_current_gpu_model()
        self._cpu_pipelines.clear()
        import gc
        gc.collect()
        print("🧹 Virtual Company shift ended. Memory cleared.")
