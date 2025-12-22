import json
import itertools
from collections import Counter
from pyvis.network import Network
import webbrowser
import os
import sqlite3
import networkx as nx
from networkx.algorithms import community

# ==========================================
# CONFIGURATION
# ==========================================
BUILDS_FILE = 'all_skills.json'   # Your build data
SKILLS_DB_FILE = 'skills2.db' # Your ID -> Name mapping
MIN_SUPPORT = 10                  # Pairs must appear this often to be shown
MIN_CONFIDENCE = 0.60             # 60% link strength required

# Distinct colors for communities
COMMUNITY_COLORS = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', 
    '#911eb4', '#46f0f0', '#f032e6', '#bcf60c', '#fabebe', 
    '#008080', '#e6beff', '#9a6324', '#fffac8', '#800000', 
    '#aaffc3', '#808000', '#ffd8b1', '#000075', '#808080'
]

class VisualAnalyzer:
    def __init__(self):
        self.skill_map = self._load_skills()
        self.builds = self._load_builds()
        
    def _load_skills(self):
        print(f"Loading skills from: {SKILLS_DB_FILE}...")
        
        # CASE 0: The file is a SQLite database
        if SKILLS_DB_FILE.endswith('.db'):
            try:
                conn = sqlite3.connect(SKILLS_DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT id, skill_name, skill_icon FROM skills_index")
                skill_map = {}
                for row in cursor.fetchall():
                    s_id = int(row[0])
                    skill_map[s_id] = {
                        'name': row[1],
                        'icon': row[2] if row[2] else f"{s_id}.jpg"
                    }
                conn.close()
                print(f" -> Successfully loaded {len(skill_map)} names and icons from SQLite.")
                return skill_map
            except Exception as e:
                print(f" -> SQLite load failed: {e}")
                # Fall through to JSON attempt if SQLite fails

        try:
            with open(SKILLS_DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            skill_map = {}
            
            # CASE 1: The file is a List [ {"id": 1, "name": "X"}, ... ]
            if isinstance(data, list):
                print(" -> Detected List format. Converting to Map...")
                for item in data:
                    # Try to find the ID key (could be 'id', 'skill_id', etc.)
                    s_id = item.get('id') or item.get('skill_id')
                    # Try to find the Name key (could be 'name', 'skill_name', etc.)
                    s_name = item.get('name') or item.get('skill_name') or item.get('en')
                    
                    if s_id is not None and s_name:
                        skill_map[int(s_id)] = {'name': s_name, 'icon': f"{s_id}.jpg"}

            # CASE 2: The file is a Dictionary { "1": "X", ... }
            elif isinstance(data, dict):
                print(" -> Detected Dictionary format. Normalizing keys...")
                for k, v in data.items():
                    # If the value is a dictionary (common in GW2 API), extract the name
                    if isinstance(v, dict):
                        name = v.get('name', f"Unknown-{k}")
                        skill_map[int(k)] = {'name': name, 'icon': f"{k}.jpg"}
                    # If the value is just a string, use it directly
                    else:
                        skill_map[int(k)] = {'name': str(v), 'icon': f"{k}.jpg"}

            print(f" -> Successfully loaded {len(skill_map)} entries.")
            return skill_map

        except FileNotFoundError:
            print(f"\n[CRITICAL ERROR] Could not find '{SKILLS_DB_FILE}'")
            return {}
        except Exception as e:
            print(f"[Error] Failed to parse skills DB: {e}")
            return {}

    def _load_builds(self):
        try:
            with open(BUILDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[Error] Could not find '{BUILDS_FILE}'")
            return []

    def get_skill_data(self, skill_id):
        # Returns the dict with name and icon
        return self.skill_map.get(skill_id, {'name': f"!!_ID_{skill_id}", 'icon': '0.jpg'})

    def generate_interactive_map(self):
        print("Analyzing data...")
        
        # 1. Tally up the skills
        pair_counts = Counter()
        skill_counts = Counter()
        
        for build in self.builds:
            skills = list(set(build.get('skill_ids', [])))
            skill_counts.update(skills)
            pair_counts.update(itertools.combinations(sorted(skills), 2))

        # 2. Build NetworkX Graph for Analysis
        print(f"Calculating Communities (Min Support: {MIN_SUPPORT}, Min Conf: {MIN_CONFIDENCE*100}%)...")
        G = nx.Graph()
        valid_edges = []
        
        for (id_a, id_b), count in pair_counts.items():
            if count < MIN_SUPPORT: continue
            
            freq_a = skill_counts[id_a]
            freq_b = skill_counts[id_b]
            conf_a_b = count / freq_a
            conf_b_a = count / freq_b
            
            if conf_a_b >= MIN_CONFIDENCE or conf_b_a >= MIN_CONFIDENCE:
                weight = max(conf_a_b, conf_b_a)
                G.add_edge(id_a, id_b, weight=weight)
                valid_edges.append((id_a, id_b, weight))

        # 3. Detect Communities
        # Uses Greedy Modularity optimization
        communities = community.greedy_modularity_communities(G)
        print(f" -> Found {len(communities)} distinct communities.")
        
        # Map node -> color
        node_colors = {}
        for i, comm in enumerate(communities):
            color = COMMUNITY_COLORS[i % len(COMMUNITY_COLORS)]
            for node_id in comm:
                node_colors[node_id] = color

        # 4. Initialize PyVis Graph
        net = Network(height='90vh', width='100%', bgcolor='#222222', font_color='white', cdn_resources='in_line')
        net.force_atlas_2based()
        
        added_skills = set()
        icons_base_path = "icons/skill_icons/"
        
        # 5. Add Nodes and Edges to PyVis
        for (id_a, id_b, weight) in valid_edges:
            data_a = self.get_skill_data(id_a)
            data_b = self.get_skill_data(id_b)
            
            if id_a not in added_skills:
                icon_path = icons_base_path + data_a['icon']
                if not icon_path.lower().endswith('.jpg'): icon_path += '.jpg'
                
                # Get Color
                color = node_colors.get(id_a, '#97c2fc') # Default blue if logic fails
                
                # Use 'color' for borders/backgrounds behind the image
                net.add_node(id_a, label=data_a['name'], title=f"Used in {skill_counts[id_a]} builds", 
                             shape='circularImage', image=icon_path, size=10 + (skill_counts[id_a]/15),
                             color=color, borderWidth=3)
                added_skills.add(id_a)
                
            if id_b not in added_skills:
                icon_path = icons_base_path + data_b['icon']
                if not icon_path.lower().endswith('.jpg'): icon_path += '.jpg'
                
                color = node_colors.get(id_b, '#97c2fc')
                
                net.add_node(id_b, label=data_b['name'], title=f"Used in {skill_counts[id_b]} builds", 
                             shape='circularImage', image=icon_path, size=10 + (skill_counts[id_b]/15),
                             color=color, borderWidth=3)
                added_skills.add(id_b)

            net.add_edge(id_a, id_b, value=weight, title=f"Synergy: {weight:.1%}")

        # 6. Save and Open
        output_file = "synergy_map.html"
        net.show_buttons(filter_=['physics'])
        html_content = net.generate_html()
        
        # --- Custom JS Injection for Manual Grouping ---
        custom_js = """
        <script type="text/javascript">
        // 1. Drag + Ctrl to Merge
        network.on("dragEnd", function (params) {
            // Check if Ctrl key was held during the drag
            if (!params.event.srcEvent.ctrlKey) return;
            if (params.nodes.length === 0) return;
            
            var draggedId = params.nodes[0];
            var pointer = params.pointer.canvas;
            
            // Get all node positions to find the closest one
            var positions = network.getPositions();
            var allIds = nodes.getIds();
            var closestId = null;
            var minDist = 500; // Hitbox radius (in canvas units)
            
            for (var i = 0; i < allIds.length; i++) {
                var id = allIds[i];
                if (id == draggedId) continue;
                
                var pos = positions[id];
                if (!pos) continue;
                
                var dx = pos.x - pointer.x;
                var dy = pos.y - pointer.y;
                var dist = Math.sqrt(dx*dx + dy*dy);
                
                if (dist < minDist) {
                    minDist = dist;
                    closestId = id;
                }
            }
            
            if (closestId) {
                var sourceNode = nodes.get(draggedId);
                var targetNode = nodes.get(closestId);
                
                // If they have different colors (communities), merge them
                if (sourceNode.color !== targetNode.color) {
                    var oldColor = sourceNode.color;
                    var newColor = targetNode.color;
                    
                    var updates = [];
                    var allNodes = nodes.get();
                    
                    // Update ALL nodes of the old community to the new color
                    for (var j = 0; j < allNodes.length; j++) {
                        if (allNodes[j].color === oldColor) {
                            updates.push({id: allNodes[j].id, color: newColor});
                        }
                    }
                    nodes.update(updates);
                    
                    // Add a permanent physical link to keep them together
                    edges.add({
                        from: draggedId, 
                        to: closestId, 
                        color: newColor, 
                        width: 3, 
                        title: "Manual Merge",
                        dashes: true
                    });
                    
                    console.log("Merged community " + oldColor + " into " + newColor);
                }
            }
        });

        // 2. Double Click Edge to Break Link
        network.on("doubleClick", function (params) {
            if (params.edges.length > 0) {
                var edgeId = params.edges[0];
                var edge = edges.get(edgeId);
                
                // Only allow deleting our manual merge links
                if (edge && edge.dashes === true) {
                    edges.remove(edgeId);
                    console.log("Removed manual link: " + edgeId);
                }
            }
        });
        </script>
        """
        
        # Inject script before body end
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", custom_js + "\n</body>")
        else:
            html_content += custom_js

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\nSUCCESS! Graph saved to '{output_file}'.")
        print("Opening it in your browser now...")
        webbrowser.open('file://' + os.path.realpath(output_file))

if __name__ == "__main__":
    app = VisualAnalyzer()
    app.generate_interactive_map()