import sqlite3
import os

DB_FILE = "master.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    print("Fetching Type_Healing skills...")
    cursor.execute("SELECT t.skill_id, s.name, s.description, s.target_type FROM skill_tags t JOIN skills s ON t.skill_id = s.skill_id WHERE t.tag = 'Type_Healing'")
    skills = cursor.fetchall()
    
    print(f"Found {len(skills)} healing skills. Analyzing vectors...")
    
    updates = [] # List of (new_tag, skill_id)
    removals = [] # List of (skill_id)
    
    for sid, name, desc, target in skills:
        if not desc: desc = ""
        d = desc.lower()
        new_tag = None
        
        # 1. Lifesteal (Highest Priority - Offensive)
        if "steal" in d and "health" in d:
            new_tag = "Type_Healing_Lifesteal"
            
        # 2. Ally / Party (Support)
        elif target == 3 or "target ally" in d or "party" in d or "allies" in d or "other ally" in d or "resurrect" in d:
            new_tag = "Type_Healing_Ally"
            
        # 3. Self (Sustain)
        elif "you gain" in d or "heal yourself" in d or "you are healed" in d:
            new_tag = "Type_Healing_Self"
            
        else:
            # Fallback / Ambiguous
            # If it's a heal but doesn't mention target, usually Self (e.g. "Heal for 50")
            print(f"  [WARN] Ambiguous Vector: {name} (ID: {sid}) - Defaulting to Self")
            new_tag = "Type_Healing_Self"
            
        updates.append((new_tag, sid))
        removals.append((sid,))
        
    print(f"Applying {len(updates)} tag updates...")
    
    # Remove old tag
    cursor.executemany("DELETE FROM skill_tags WHERE skill_id=? AND tag='Type_Healing'", removals)
    
    # Insert new tags
    inserted = 0
    for tag, sid in updates:
        # Check if already exists to avoid dupes
        cursor.execute("SELECT 1 FROM skill_tags WHERE skill_id=? AND tag=?", (sid, tag))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO skill_tags (skill_id, tag) VALUES (?, ?)", (sid, tag))
            inserted += 1
            
    conn.commit()
    conn.close()
    print(f"Migration complete. {inserted} new tags inserted.")

if __name__ == "__main__":
    migrate()
