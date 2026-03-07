import json
import os

DB_DIR = os.path.join(os.path.dirname(__file__), "../../db_storage")
QA_FILE = os.path.join(DB_DIR, "pending_qa.json")

class QAManager:
    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        if not os.path.exists(QA_FILE):
            with open(QA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
                
    def add_pending(self, original: str, refined: str):
        with open(QA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.append({"id": len(data)+1, "original": original, "refined": refined, "status": "pending"})
        with open(QA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def get_pending(self):
        with open(QA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [item for item in data if item["status"] == "pending"]
        
    def resolve_pending(self, item_id: int, answer: str):
        with open(QA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if item["id"] == item_id:
                item["status"] = "resolved"
                item["answer"] = answer
        with open(QA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def dismiss_pending(self, item_id: int):
        with open(QA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            if item["id"] == item_id:
                item["status"] = "dismissed"
        with open(QA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

qa_manager = QAManager()
