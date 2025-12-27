# B.O.O.K.A.H. <br>(Build Optimization & Organization for Knowledge-Agnostic Hominids)

A high-performance build creation and analysis tool for Guild Wars 1, powered by a Hybrid Neural/Mechanics Engine to identify deep mechanical synergies and counter-play.

## Key Features

### Hybrid Analysis Architecture
B.O.O.K.A.H. employs a multi-dimensional approach to identify skill relationships:
*   **Behavioral Modeling (Word2Vec)**: Analyzes thousands of meta-builds to identify statistical correlations and frequent skill pairings used by the community.
*   **Semantic Context (Sentence-BERT)**: Processes skill descriptions using Natural Language Processing to identify mechanical and thematic connections that raw statistics might overlook.

### Smart Synergy Engine (MechanicsEngine)
The engine analyzes builds as complex systems of resources and effects, enforcing **18 Synergy Laws** (e.g., Law of Gravity for Knockdowns, Law of Hexes).
*   **Smart Mode**: Activates the full capabilities of the engine. It enables **Semantic Analysis** to suggest skills based on shared mechanics (e.g., finding "Strike a Burning Foe" skills if you have a burning source), and injects **Basic Needs** suggestions (automatically detecting missing self-heals or energy management).
*   **Standard Mode**: Purely statistical suggestions based on the meta.

### Team Build Management
*   **Active Team Context**: Load an entire team build into the analysis context. The AI will suggest skills for your current bar that synergize with your teammates (e.g., if they spam conditions, it suggests "Fragility").
*   **Redundancy Checks**: Prevents suggesting unique effects (like Spirits) that your team already provides.

### Advanced Tools
*   **Attribute Editor**: Full 200-point distribution with authentic cost curves and PvE Title Track support.
*   **Build Uniqueness**: Checks your current bar against thousands of known builds to tell you if your creation is truly unique or a meta-clone.
*   **Pre-Searing Support**: dedicated filter to strictly limit suggestions to skills available in Pre-Searing Ascalon.

## Index of Functions

| Control | Description |
| :--- | :--- |
| **Load Teambuild to Bar** | Loads a team's skills into the AI context. Suggestions for your empty slots will now specifically synergize with that team. |
| **Cycle Suggestions** | Rotates through the top 100 AI suggestions for your empty slots. Useful if the top pick isn't what you want. |
| **Is this unique?** | Compares your current 8-skill bar against the entire database. Shows builds that are 50%+ similar. |
| **Smart Mode (Checkbox)** | Toggles the Semantic Lobe and "Basic Needs" logic. Uncheck for pure "Old School" meta-statistical suggestions. |
| **Pre (Checkbox)** | Strictly filters ALL suggestions (Neural, Basic Needs, Counters) to only show skills available in Pre-Searing. |
| **Lock (Checkbox)** | Freezes the current suggestions in place, allowing you to edit the bar without the AI constantly recalculating. |
| **PvP (Checkbox)** | Switches the engine to use PvP versions of skills (different energy/recharge/effects) and excludes PvE-only skills. |
| **Manage Teams** | Opens the Team Manager to create, rename, or delete custom team builds. |
| **Select Template Folder** | Sets the directory where the "Export" feature will save your build files. |

## Getting Started
Run the application using Python 3.10:
```bash
pip install -r requirements.txt
python bookah.py
```

## Legal
*   **Code & Logic**: Licensed under [CC BY-NC-SA 4.0](LICENSE). You are free to share and adapt this code for non-commercial purposes, provided you credit the author and share under the same license.
*   **Game Assets**: Guild Wars content and materials are trademarks and copyrights of ArenaNet and its licensors. All rights reserved. This tool is a fan project and is not affiliated with ArenaNet or NCSOFT.
