import json
import logging
import os
import sqlite3
import numpy as np
from typing import List, Tuple
from gensim.models import Word2Vec

# Configure logging
logging.getLogger("gensim").setLevel(logging.ERROR)

class SkillBrain:
    def __init__(self, model_path="skill_vectors.model", semantic_path="description_embeddings.pt"):
        self.model_path = model_path
        self.semantic_path = semantic_path
        self.behavior_model = None
        self.semantic_model = None
        
        # Cache for descriptions vectors: {skill_id: vector}
        self.description_vectors = {}
        self.IGNORE_IDS = {0, "0"} 
        self.device = 'cpu' # Will be updated to 'cuda' during load if available

    def _get_embedder(self):
        """
        Lazy loader for SentenceTransformer.
        """
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.device = device
            print(f"[Brain] AI Hardware Acceleration: {device.upper()}")
            
            return SentenceTransformer('all-MiniLM-L6-v2', device=device)
        except ImportError:
            import traceback
            print(f"[Brain] Error: sentence_transformers import failed: {traceback.format_exc()}")
            print("[Brain] Error: sentence_transformers not installed. Semantic Lobe disabled.")
            return None

    def _load_descriptions_from_db(self, db_path="master.db") -> dict:
        if not os.path.exists(db_path):
            return {}
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT skill_id, name, description FROM skills")
        rows = cursor.fetchall()
        conn.close()
        
        desc_map = {}
        for sid, name, desc in rows:
            if desc:
                # Combine Name + Desc for context
                text = f"{name}. {desc}" 
                desc_map[sid] = text
        return desc_map

    def train(self, json_paths: List[str], db_path="master.db"):
        """
        Trains models only if they are missing.
        """
        if isinstance(json_paths, str):
            json_paths = [json_paths]

        # 1. Behavioral Training (Fast)
        if not os.path.exists(self.model_path):
            print(f"[Brain] Training Behavioral Lobe...")
            training_sentences = []
            
            for path in json_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)
                    
                    for entry in raw_data:
                        skill_ids = entry.get('skill_ids', [])
                        clean = [str(sid) for sid in skill_ids if sid not in self.IGNORE_IDS]
                        if len(clean) > 1:
                            training_sentences.append(clean)
            
            if training_sentences:
                self.behavior_model = Word2Vec(
                    sentences=training_sentences, 
                    vector_size=100, 
                    window=100, 
                    min_count=1, 
                    workers=4, 
                    sg=1, 
                    epochs=30
                )
                self.behavior_model.save(self.model_path)
                print(f"[Brain] Behavioral Lobe saved to {self.model_path}")
            else:
                print("[Brain] Warning: No training data found.")

        # 2. Semantic Training (Slow on first run)
        if not os.path.exists(self.semantic_path):
            print("[Brain] Training Semantic Lobe (Description Embeddings)...")
            embedder = self._get_embedder()
            
            if embedder:
                desc_map = self._load_descriptions_from_db(db_path)
                if desc_map:
                    ids = list(desc_map.keys())
                    texts = list(desc_map.values())
                    
                    # Heavy Computation
                    embeddings = embedder.encode(texts, convert_to_tensor=True, show_progress_bar=True)
                    
                    import torch
                    torch.save({'ids': ids, 'embeddings': embeddings}, self.semantic_path)
                    print("[Brain] Semantics Saved.")

        # 3. Force load everything into RAM
        self.load()

    def load(self):
        """Loads models from disk into RAM."""
        # Load Behavioral
        if os.path.exists(self.model_path):
            try:
                self.behavior_model = Word2Vec.load(self.model_path)
                print(f"[Brain] Behavioral Model Loaded ({len(self.behavior_model.wv)} terms).")
            except Exception as e:
                print(f"[Brain] Behavioral Load Error: {e}")
        
        # Load Semantics
        if os.path.exists(self.semantic_path) and not self.description_vectors:
            import torch
            
            try:
                data = torch.load(self.semantic_path, map_location=torch.device('cpu'))
                ids = data['ids']
                embeddings = data['embeddings']
                self.description_vectors = {sid: emb for sid, emb in zip(ids, embeddings)}
                print(f"[Brain] Semantic Vectors Ready ({len(ids)} descriptions loaded).")
            except Exception as e:
                print(f"[Brain] Semantic Load Error: {e}")
                self.semantic_model = self._get_embedder()

    def suggest(self, current_skills: List[int], top_n=50, use_semantic=True) -> List[Tuple[int, float]]:
        # Models are guaranteed loaded by train() called in init
        
        # 1. Behavioral Scoring
        behavior_scores = {}
        if self.behavior_model:
            valid_keys = [str(s) for s in current_skills if str(s) in self.behavior_model.wv]
            if valid_keys:
                try:
                    # Get raw list. We get more than top_n to allow for re-ranking
                    raw_suggestions = self.behavior_model.wv.most_similar(positive=valid_keys, topn=top_n*4)
                    for sid_str, score in raw_suggestions:
                        behavior_scores[int(sid_str)] = score
                except Exception as e:
                    print(f"[Brain] Behavioral Error: {e}")

        if not use_semantic:
            # RETURN BEHAVIORAL ONLY (Standard/Legacy Mode)
            return sorted(behavior_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # 2. Semantic Scoring
        semantic_scores = {}
        if self.description_vectors and len(current_skills) > 0:
            import torch
            from sentence_transformers import util
            
            # Quick Stack (Fast RAM op)
            current_vectors = [self.description_vectors[sid] for sid in current_skills if sid in self.description_vectors]
            
            if current_vectors:
                bar_theme = torch.stack(current_vectors).mean(dim=0)
                
                # Matrix Math
                all_ids = list(self.description_vectors.keys())
                all_embs = torch.stack(list(self.description_vectors.values()))
                
                # Cosine Similarity (Fast)
                cos_scores = util.cos_sim(bar_theme, all_embs)[0]
                
                # Dynamic K
                k_val = min(top_n * 4, len(cos_scores))
                top_results = torch.topk(cos_scores, k=k_val)
                
                for score, idx in zip(top_results.values, top_results.indices):
                    semantic_scores[all_ids[idx]] = float(score)

        # 3. Fusion
        final_scores = {}
        all_candidate_ids = set(behavior_scores.keys()) | set(semantic_scores.keys())
        input_set = set(current_skills)

        for sid in all_candidate_ids:
            if sid in input_set: continue
            
            b_score = behavior_scores.get(sid, 0.0)
            s_score = semantic_scores.get(sid, 0.0)
            
            # Weighted Average
            # Behavior 0.4 / Semantic 0.6
            final_score = (b_score * 0.4) + (s_score * 0.6)
            final_scores[sid] = final_score

        return sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Compatibility Hook
    def train_from_json(self, json_path):
        # We assume database path relative to json for now, or use defaults
        self.train(json_path)