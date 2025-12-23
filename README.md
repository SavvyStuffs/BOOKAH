# B.O.O.K.A.H. <br>(Build Optimization & Organization for Knowledge-Agnostic Hominids)

A high-performance build creation and analysis tool for Guild Wars 1, designed to identify deep mechanical synergies between skills and optimize team compositions.

## Key Features

### Big Data Build Analysis
B.O.O.K.A.H. leverages the collective intelligence of the Guild Wars community. By analyzing every build on the PvX Wiki, the app breaks down over 2000 builds into nearly 9,000 unique skill pairs, with over 48,000 total skill pairings.
*   **Frequency-Based Suggestions**: Skills are ranked and suggested based on their historical success and frequency in established meta-builds.
*   **Deep Integration**: Every PvX team and solo build is integrated directly into the B.O.O.K.A.H. database.
*   **One-Click Export**: Browse the entire PvX library and save builds directly to your Guild Wars template folder for immediate use in-game.

### Smart Synergy Engine (beta)
The heart of the application is a custom-built engine that treats character builds as thermodynamic systems. It moves beyond simple condition matching, utilizing **18 Synergy Laws** to make suggestions for over 60% of skills:
*   **Law of Multiplication**: Detects AoE "Delivery" (e.g., Barrage) and suggests "Payloads" (e.g., Splinter Weapon).
*   **Law of Gravity**: Connects Knockdown providers with powerful "Punisher" skills.
*   **Law of Hexes**: Bidirectional logic for applying and shattering Hexes.
*   **Law of Spiritualism**: Manages Spirit summoning and exploitation (Spirit Light, Rupture Soul, etc.).
*   **Law of Disruption**: Pairs Interrupt-reliant bonuses with reliable shutdown skills.
*   **Target Awareness**: Suggestions respect Ally vs. Foe targeting to prevent logical mismatches.

### Advanced Attribute Editor
*   **Point Distribution**: Full control over 200 attribute points using the authentic Guild Wars cost curve (Rank 12 costs 97 points).
*   **PvE Title Tracks**: Integrated support for PvE ranks (0-10) for Sunspear, Lightbringer, Norn, Vanguard, Asuran, Dwarven, and Deldrimor tracks.
*   **Active Scanning**: The editor automatically detects and displays relevant attributes based on the skills currently in your bar.

### Team Build Management
*   **Folder Drop**: Drag and drop an entire folder of `.txt` build templates into the Team Build Manager to create a new Team Build instantly.
*   **Team Synergy Mode**: Load a whole team into the "Synergy Context" with the Load Team Build to Bar button. The engine will then suggest skills for your bar that specifically complement the selected team build.
*   **Redundancy Filtering**: Smart logic prevents redundant suggestions (e.g., it won't suggest a spirit that is already being brought by another team member).
*   **Team Manager**: Dedicated dialogs to add, modify, and prune builds within your custom teams.

### Interactive Tools
*   **Location Manager**: Tabbed interface to browse and select specific Explorable Zones and Missions. When an area is selected, the Bookah will suggest skills based on the skills used by the enemies in the area.
*   **Counter Build**: Use PvX wiki data and Smart Logic to suggest a build to specifically counter the provided build code. 
*   **Synergy Map**: Integrated web visualization tool to explore the complex web of skill relationships.

## Getting Started
Still in development. Run the application using Python 3.10:
```bash
pip install -r requirements.txt
python bookah.py
```