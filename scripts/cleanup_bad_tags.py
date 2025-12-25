import sqlite3
import os

DB_FILE = "master.db"

def cleanup():
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Cleanup Type_Healing_Self
    print("Scanning Type_Healing_Self for false positives...")
    cursor.execute("SELECT t.skill_id, s.name, s.description FROM skill_tags t JOIN skills s ON t.skill_id = s.skill_id WHERE t.tag = 'Type_Healing_Self'")
    skills = cursor.fetchall()
    
    removals = []
    
    valid_keywords = ["you gain", "heal yourself", "you are healed", "regeneration", "resurrect", "heals for"]
    # "heals for" covers "Trap heals for X"
    
    for sid, name, desc in skills:
        if not desc: 
            removals.append((sid,))
            continue
            
        d = desc.lower()
        is_valid = False
        
        for kw in valid_keywords:
            if kw in d:
                is_valid = True
                break
        
        # Exception: "Health" alone is not enough (could be "Target Health")
        
        if not is_valid:
            print(f"  Removing Type_Healing_Self from: {name}")
            removals.append((sid,))
            
    cursor.executemany("DELETE FROM skill_tags WHERE skill_id=? AND tag='Type_Healing_Self'", removals)
    print(f"Removed {len(removals)} invalid Self Heal tags.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    cleanup()
