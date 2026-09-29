import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import ast

# Path to the JSON file relative to the resources folder
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'src', 'assets', 'skills_data.json')

def get_default_skill(new_id):
    return {
        "skill_id": new_id,
        "name": "New Custom Skill",
        "description": "Enter skill description here.",
        "profession": 0,
        "attribute": 0,
        "campaign": 0,
        "energy_cost": 5,
        "health_cost": 0,
        "adrenaline": 0,
        "activation": 1.0,
        "aftercast": 0.0,
        "recharge": 5.0,
        "weapon_req": 0,
        "combo_req": 0,
        "is_elite": 0,
        "is_touch": 0,
        "target_type": 0,
        "aoe_range": "Single",
        "is_pve_only": 0,
        "in_pre": 0,
        "skill_type": "spell",
        "hasPvP": 0,
        "overcast": 0,
        "upkeep": 0,
        "tags": [],
        "stats": [],
        "acquisition": {
            "quests": "",
            "trainers": "",
            "hero_trainers": "",
            "capture": "",
            "campaign": ""
        }
    }

class SkillEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bookah Skill Editor")
        self.root.geometry("1000x750")
        
        self.apply_dark_mode()
        
        self.skills_data = {}
        self.current_skill_key = None
        self.temp_new_skill = None
        self.stat_entries = []
        self.prop_entries = {}
        self.removed_fields = set()
        self.current_acquisition = {}
        
        self.available_fields = [
            "profession", "attribute", "campaign", "energy_cost", "health_cost",
            "adrenaline", "activation", "aftercast", "recharge", "weapon_req",
            "combo_req", "is_elite", "is_touch", "target_type", "aoe_range",
            "is_pve_only", "in_pre", "skill_type", "hasPvP", "overcast",
            "upkeep", "tags"
        ]
        
        self.load_data()
        self.build_ui()

    def apply_dark_mode(self):
        bg_color = "#2b2b2b"
        fg_color = "#e0e0e0"
        entry_bg = "#3c3f41"
        btn_bg = "#4b4d4f"
        
        self.root.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure(".", 
                        font=("Lazelar", 10),
                        background=bg_color, 
                        foreground=fg_color, 
                        fieldbackground=entry_bg, 
                        insertcolor=fg_color,
                        troughcolor=bg_color,
                        bordercolor="#1e1e1e",
                        lightcolor="#4b4d4f",
                        darkcolor="#1e1e1e")
                        
        style.configure("TButton", background=btn_bg, foreground=fg_color, borderwidth=1, focuscolor=btn_bg, font=("Lazelar", 10))
        style.map("TButton", background=[("active", "#5c5f61")], foreground=[("active", fg_color)])
        
        style.configure("TLabelframe", background=bg_color, foreground=fg_color, bordercolor="#4b4d4f")
        style.configure("TLabelframe.Label", background=bg_color, foreground=fg_color, font=("Lazelar", 10, "bold"))

    def load_data(self):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                self.skills_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load skills data:\n{e}")

    def save_data(self):
        try:
            sorted_data = {}
            for k in sorted(self.skills_data.keys(), key=lambda x: int(x) if x.lstrip('-').isdigit() else float('inf')):
                sorted_data[k] = self.skills_data[k]
                
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, indent=2)
                
            self.skills_data = sorted_data
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save skills data:\n{e}")

    def build_ui(self):
        # Search Frame
        search_frame = ttk.Frame(self.root, padding=10)
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="Search (ID or Name):").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=35)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<Return>', lambda event: self.search_skill())
        ttk.Button(search_frame, text="Search", command=self.search_skill).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(search_frame, text="|").pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Create New Skill", command=self.create_new_skill).pack(side=tk.LEFT, padx=2)
        
        # Info Frame
        self.info_frame = ttk.LabelFrame(self.root, text="Skill Info", padding=10)
        self.info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        top_info = ttk.Frame(self.info_frame)
        top_info.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(top_info, text="ID (Index):").pack(side=tk.LEFT)
        self.id_var = tk.StringVar()
        ttk.Entry(top_info, textvariable=self.id_var, width=10).pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(top_info, text="Name:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        ttk.Entry(top_info, textvariable=self.name_var, width=40).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(top_info, text="Edit Acquisition", command=self.open_acq_window).pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(self.info_frame, text="Description:").pack(anchor=tk.W)
        self.desc_text = tk.Text(self.info_frame, height=4, wrap=tk.WORD, 
                                 font=("Lazelar", 10),
                                 bg="#3c3f41", fg="#e0e0e0", insertbackground="#e0e0e0", selectbackground="#2f65ca", bd=0, padx=5, pady=5)
        self.desc_text.pack(fill=tk.X, pady=(5, 0))
        
        # Split Frame for Properties (Left) and Stats (Right)
        split_frame = ttk.Frame(self.root)
        split_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- LEFT: Additional Properties ---
        self.props_frame = ttk.LabelFrame(split_frame, text="Additional Properties", padding=10)
        self.props_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        prop_top = ttk.Frame(self.props_frame)
        prop_top.pack(fill=tk.X, pady=(0, 5))
        
        self.prop_combo = ttk.Combobox(prop_top, values=self.available_fields, state="normal")
        self.prop_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(prop_top, text="+ Add Field", command=self.add_property_row).pack(side=tk.LEFT, padx=5)
        
        self.prop_canvas = tk.Canvas(self.props_frame, bg="#2b2b2b", highlightthickness=0)
        prop_scroll = ttk.Scrollbar(self.props_frame, orient="vertical", command=self.prop_canvas.yview)
        self.prop_inner = ttk.Frame(self.prop_canvas)
        self.prop_inner.bind("<Configure>", lambda e: self.prop_canvas.configure(scrollregion=self.prop_canvas.bbox("all")))
        self.prop_canvas.create_window((0, 0), window=self.prop_inner, anchor="nw")
        self.prop_canvas.configure(yscrollcommand=prop_scroll.set)
        
        self.prop_canvas.pack(side="left", fill="both", expand=True)
        prop_scroll.pack(side="right", fill="y")
        
        # --- RIGHT: Stats ---
        self.stats_frame = ttk.LabelFrame(split_frame, text="Attributes (Lerps to nearest whole number)", padding=10)
        self.stats_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        btn_frame = ttk.Frame(self.stats_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_frame, text="+ Add New Stat", command=self.add_stat).pack(side=tk.LEFT)
        
        self.canvas = tk.Canvas(self.stats_frame, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.stats_frame, orient="vertical", command=self.canvas.yview)
        self.stats_inner_frame = ttk.Frame(self.canvas)
        
        self.stats_inner_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.stats_inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Action Frame
        action_frame = ttk.Frame(self.root, padding=10)
        action_frame.pack(fill=tk.X)
        
        ttk.Button(action_frame, text="Save & Lerp", command=self.save_and_lerp).pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="Delete Skill", command=self.delete_skill).pack(side=tk.RIGHT, padx=5)
        ttk.Button(action_frame, text="Reload JSON", command=self.reload_data).pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(action_frame, text="", foreground="#50fa7b", font=("Lazelar", 10, "bold"))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def search_skill(self):
        query = self.search_var.get().strip().lower()
        if not query: return
        
        found_key = None
        found_skill = None
        
        for key, skill in self.skills_data.items():
            if str(skill.get("skill_id", "")) == query or str(key) == query:
                found_key = key
                found_skill = skill
                break
        
        if not found_skill:
            for key, skill in self.skills_data.items():
                if query in skill.get("name", "").lower():
                    found_key = key
                    found_skill = skill
                    break
                    
        if found_skill:
            self.populate_ui(found_key, found_skill)
        else:
            messagebox.showinfo("Not Found", f"No skill found matching '{query}'")

    def delete_skill(self):
        if not self.current_skill_key:
            return
            
        if self.current_skill_key == "NEW":
            self.temp_new_skill = None
            self.current_skill_key = None
            self.status_label.config(text="Discarded new skill.")
            self.id_var.set("")
            self.name_var.set("")
            self.desc_text.delete("1.0", tk.END)
            for widget in self.prop_inner.winfo_children(): widget.destroy()
            for widget in self.stats_inner_frame.winfo_children(): widget.destroy()
            return
            
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete ID {self.current_skill_key}?"):
            if self.current_skill_key in self.skills_data:
                del self.skills_data[self.current_skill_key]
                self.save_data()
                
            self.current_skill_key = None
            self.id_var.set("")
            self.name_var.set("")
            self.desc_text.delete("1.0", tk.END)
            for widget in self.prop_inner.winfo_children(): widget.destroy()
            for widget in self.stats_inner_frame.winfo_children(): widget.destroy()
            
            self.status_label.config(text="Skill deleted.")
            self.root.after(3000, lambda: self.status_label.config(text=""))

    def reload_data(self):
        self.load_data()
        self.current_skill_key = None
        self.id_var.set("")
        self.name_var.set("")
        self.desc_text.delete("1.0", tk.END)
        for widget in self.prop_inner.winfo_children(): widget.destroy()
        for widget in self.stats_inner_frame.winfo_children(): widget.destroy()
        
        self.status_label.config(text="Reloaded JSON from disk.")
        self.root.after(3000, lambda: self.status_label.config(text=""))

    def open_acq_window(self):
        if not self.current_skill_key:
            messagebox.showwarning("Warning", "Please search for a skill or create a new one first.")
            return
            
        acq_win = tk.Toplevel(self.root)
        acq_win.title("Edit Acquisition")
        acq_win.geometry("600x600")
        acq_win.configure(bg="#2b2b2b")
        acq_win.grab_set()
        
        def create_text(parent, label_text, default_val, height=4):
            ttk.Label(parent, text=label_text, font=("Lazelar", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
            txt = tk.Text(parent, height=height, wrap=tk.WORD, bg="#3c3f41", fg="#e0e0e0", insertbackground="#e0e0e0", selectbackground="#2f65ca", bd=0, padx=5, pady=5, font=("Lazelar", 10))
            txt.pack(fill=tk.X, padx=10)
            txt.insert(tk.END, default_val)
            return txt
            
        ttk.Label(acq_win, text="Campaign:", font=("Lazelar", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
        camp_var = tk.StringVar(value=self.current_acquisition.get("campaign", ""))
        ttk.Entry(acq_win, textvariable=camp_var).pack(fill=tk.X, padx=10)
        
        q_txt = create_text(acq_win, "Quests (One per line, Format: Name|URL):", self.current_acquisition.get("quests", ""))
        t_txt = create_text(acq_win, "Trainers (One per line, Format: Name|URL):", self.current_acquisition.get("trainers", ""))
        ht_txt = create_text(acq_win, "Hero Trainers:", self.current_acquisition.get("hero_trainers", ""))
        c_txt = create_text(acq_win, "Capture:", self.current_acquisition.get("capture", ""))
        
        def apply_acq():
            self.current_acquisition["campaign"] = camp_var.get().strip()
            self.current_acquisition["quests"] = q_txt.get("1.0", tk.END).strip().replace('\\n', '\n')
            self.current_acquisition["trainers"] = t_txt.get("1.0", tk.END).strip().replace('\\n', '\n')
            self.current_acquisition["hero_trainers"] = ht_txt.get("1.0", tk.END).strip().replace('\\n', '\n')
            self.current_acquisition["capture"] = c_txt.get("1.0", tk.END).strip().replace('\\n', '\n')
            acq_win.destroy()
            
        ttk.Button(acq_win, text="Apply", command=apply_acq).pack(pady=15)

    def create_new_skill(self):
        max_id = 0
        for key, skill in self.skills_data.items():
            try:
                sid = int(skill.get("skill_id", 0))
                if sid > max_id:
                    max_id = sid
            except ValueError:
                pass
                
        new_id = max_id + 1
        self.temp_new_skill = get_default_skill(new_id)
        
        self.populate_ui("NEW", self.temp_new_skill)
        
        self.status_label.config(text="New Skill staged! Adjust ID & click Save.")
        self.root.after(4000, lambda: self.status_label.config(text=""))

    def add_stat(self):
        if not self.current_skill_key:
            messagebox.showwarning("Warning", "Please search for a skill or create a new one first.")
            return
            
        stat_name = simpledialog.askstring("New Stat", "Enter the name of the new stat (e.g. Damage, Duration):")
        if not stat_name:
            return
            
        skill = self.temp_new_skill if self.current_skill_key == "NEW" else self.skills_data[self.current_skill_key]
        if "stats" not in skill:
            skill["stats"] = []
            
        new_stat = {
            "skill_id": skill["skill_id"],
            "stat_name": stat_name,
            "variable_index": len(skill["stats"])
        }
        
        for rank in range(21):
            new_stat[f"rank_{rank}"] = 0
            
        skill["stats"].append(new_stat)
        self.populate_ui(self.current_skill_key, skill)

    def add_property_row(self, field_name=None, value=None):
        if not self.current_skill_key:
            messagebox.showwarning("Warning", "Please load a skill first.")
            return
            
        if not field_name:
            field_name = self.prop_combo.get().strip()
            
        if not field_name or field_name in self.prop_entries:
            return
            
        row_frame = ttk.Frame(self.prop_inner)
        row_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(row_frame, text=field_name, width=15, font=("Lazelar", 9, "bold")).pack(side=tk.LEFT, padx=5)
        
        if value is None:
            value = 0 if field_name not in ["skill_type", "aoe_range"] else ""
            if field_name == "tags": value = "[]"
            
        if isinstance(value, list):
            value = str(value).replace("'", '"')
            
        var = tk.StringVar(value=str(value))
        ttk.Entry(row_frame, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        def remove_row(f_name=field_name, frame=row_frame):
            frame.destroy()
            if f_name in self.prop_entries:
                del self.prop_entries[f_name]
            self.removed_fields.add(f_name)
                
        ttk.Button(row_frame, text="X", width=3, command=remove_row).pack(side=tk.LEFT, padx=5)
        self.prop_entries[field_name] = var
        if field_name in self.removed_fields:
            self.removed_fields.remove(field_name)

    def populate_ui(self, key, skill):
        self.current_skill_key = key
        
        # Acquisition
        acq_data = skill.get("acquisition", None)
        if isinstance(acq_data, dict):
            self.current_acquisition = acq_data.copy()
        else:
            self.current_acquisition = { "quests": "", "trainers": "", "hero_trainers": "", "capture": "", "campaign": "" }
        
        self.id_var.set(str(skill.get('skill_id', key)))
        self.name_var.set(skill.get('name', 'Unknown'))
        
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert(tk.END, skill.get("description", ""))
        
        # Properties
        for widget in self.prop_inner.winfo_children():
            widget.destroy()
        self.prop_entries.clear()
        self.removed_fields.clear()
        
        ignore_keys = {"skill_id", "name", "description", "stats", "acquisition"}
        for k, v in skill.items():
            if k not in ignore_keys:
                # Only populate fields that have non-default/active values to keep UI clean
                if v or v not in [0, 0.0, "", [], "[]"]:
                    self.add_property_row(k, v)
        
        # Stats
        for widget in self.stats_inner_frame.winfo_children():
            widget.destroy()
        self.stat_entries = []
        
        stats = skill.get("stats", [])
        if not stats:
            ttk.Label(self.stats_inner_frame, text="No scalable stats. Click '+ Add New Stat'.").pack(pady=10)
            return
            
        ttk.Label(self.stats_inner_frame, text="Idx", font=("Lazelar", 9, "bold")).grid(row=0, column=0, padx=3, pady=5)
        ttk.Label(self.stats_inner_frame, text="Stat Name", font=("Lazelar", 9, "bold")).grid(row=0, column=1, padx=3, pady=5, sticky=tk.W)
        ttk.Label(self.stats_inner_frame, text="Rank 0 Val", font=("Lazelar", 9, "bold")).grid(row=0, column=2, padx=3, pady=5)
        ttk.Label(self.stats_inner_frame, text="Target Rank", font=("Lazelar", 9, "bold")).grid(row=0, column=3, padx=3, pady=5)
        ttk.Label(self.stats_inner_frame, text="Target Val", font=("Lazelar", 9, "bold")).grid(row=0, column=4, padx=3, pady=5)
        
        # Determine default target rank (5 for Norn title track -9, 15 otherwise)
        attr_val = skill.get("attribute", 0)
        default_target_rank = 5 if attr_val == -9 else 15
        
        for i, stat in enumerate(stats):
            stat_name = stat.get("stat_name", f"Stat {i}")
            val_0 = stat.get("rank_0", 0)
            
            # Detect target rank from stat object
            t_rank = default_target_rank
            if stat.get("rank_5") is not None and stat.get("rank_5") == stat.get("rank_20") and stat.get("rank_5") != val_0:
                t_rank = 5
            elif stat.get("rank_12") is not None and stat.get("rank_12") == stat.get("rank_20") and stat.get("rank_12") != val_0:
                t_rank = 12
            
            val_target = stat.get(f"rank_{t_rank}", stat.get("rank_15", 0))
            
            var_idx = tk.StringVar(value=str(i))
            ent_idx = ttk.Entry(self.stats_inner_frame, textvariable=var_idx, width=4)
            ent_idx.grid(row=i+1, column=0, padx=3, pady=3)
            
            ttk.Label(self.stats_inner_frame, text=stat_name).grid(row=i+1, column=1, padx=3, pady=3, sticky=tk.W)
            
            var_0 = tk.StringVar(value=str(val_0))
            ent_0 = ttk.Entry(self.stats_inner_frame, textvariable=var_0, width=10)
            ent_0.grid(row=i+1, column=2, padx=3, pady=3)
            
            var_trank = tk.StringVar(value=str(t_rank))
            ent_trank = ttk.Entry(self.stats_inner_frame, textvariable=var_trank, width=6)
            ent_trank.grid(row=i+1, column=3, padx=3, pady=3)
            
            var_target = tk.StringVar(value=str(val_target))
            ent_target = ttk.Entry(self.stats_inner_frame, textvariable=var_target, width=10)
            ent_target.grid(row=i+1, column=4, padx=3, pady=3)
            
            self.stat_entries.append({
                "stat_index": i,
                "var_idx": var_idx,
                "var_0": var_0,
                "var_trank": var_trank,
                "var_target": var_target
            })

    def parse_value(self, val_str):
        val_str = val_str.strip()
        if val_str == "": return ""
        
        if val_str.startswith("[") and val_str.endswith("]"):
            try:
                return ast.literal_eval(val_str)
            except:
                pass
                
        try:
            if "." in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return val_str

    def save_and_lerp(self):
        if not self.current_skill_key:
            return
            
        new_id_str = self.id_var.get().strip()
        try:
            new_id_int = int(new_id_str)
        except ValueError:
            messagebox.showerror("Error", "ID must be a valid integer.")
            return
            
        if self.current_skill_key == "NEW":
            if new_id_str in self.skills_data:
                if not messagebox.askyesno("Overwrite", f"ID {new_id_str} already exists. Overwrite it?"):
                    return
            skill = self.temp_new_skill
            skill["skill_id"] = new_id_int
            self.skills_data[new_id_str] = skill
            self.current_skill_key = new_id_str
            self.temp_new_skill = None
        elif new_id_str != self.current_skill_key:
            if new_id_str in self.skills_data:
                if not messagebox.askyesno("Overwrite", f"ID {new_id_str} already exists. Overwrite it?"):
                    return
            
            skill = self.skills_data.pop(self.current_skill_key)
            skill["skill_id"] = new_id_int
            self.skills_data[new_id_str] = skill
            self.current_skill_key = new_id_str
        else:
            skill = self.skills_data[self.current_skill_key]
        
        skill["name"] = self.name_var.get().strip()
        skill["description"] = self.desc_text.get("1.0", tk.END).strip()
        skill["acquisition"] = self.current_acquisition
        
        # Properties - only delete fields if they were explicitly removed via 'X'
        for k in self.removed_fields:
            if k in skill:
                if k in ["skill_type", "aoe_range", "tags"]:
                    skill[k] = "" if k != "tags" else []
                else:
                    skill[k] = 0
            
        for field_name, str_var in self.prop_entries.items():
            skill[field_name] = self.parse_value(str_var.get())
        
        # Stats
        stats = skill.get("stats", [])
        new_stats = []
        try:
            for entry_data in self.stat_entries:
                idx = entry_data["stat_index"]
                sort_idx = int(entry_data["var_idx"].get())
                v0 = float(entry_data["var_0"].get())
                trank = max(1, min(20, int(entry_data["var_trank"].get())))
                vtarget = float(entry_data["var_target"].get())
                
                stat_obj = stats[idx]
                stat_obj["variable_index"] = sort_idx
                
                for rank in range(21):
                    if rank <= trank:
                        lerp_val = v0 + (vtarget - v0) * (rank / float(trank))
                    else:
                        lerp_val = vtarget
                    stat_obj[f"rank_{rank}"] = round(lerp_val)
                    
                new_stats.append((sort_idx, stat_obj))
                
            new_stats.sort(key=lambda x: x[0])
            skill["stats"] = [s[1] for s in new_stats]
                    
        except ValueError:
            messagebox.showerror("Error", "Please ensure all Indices, Values, and Target Rank inputs are valid numbers.")
            return
            
        self.save_data()
        self.status_label.config(text="Saved and Lerped successfully!")
        self.root.after(3000, lambda: self.status_label.config(text=""))

if __name__ == "__main__":
    root = tk.Tk()
    app = SkillEditorApp(root)
    root.mainloop()
