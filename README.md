# BOOKAH (Build Optimization & Organization for Knowledge-Agnostic Hominids)

A build maker for Guild Wars 1 with PvX wiki integrated and a "Smart Mode" that uses AI to find synergy.

## Technical Architecture

The system is built on a tripartite analysis engine:

1.  **Behavioral Engine (Word2Vec)**: Implements `SkillBrain` utilizing `Gensim` to analyze historical meta-build data (via `skill_vectors.model`). It treats build sequences as "sentences" to identify statistical correlations and frequent skill pairings.
2.  **Semantic Engine (Sentence-Transformers)**: Uses `Sentence-BERT` to process raw skill descriptions. It maps mechanical relationships (e.g., condition providers vs. consumers) into high-dimensional vector space (`description_embeddings.pt`).
3.  **Heuristic Mechanics Engine**: A rule-based system (`src/engine.py`) that performs hard-check validation for attributes, energy management, and mechanical "Basic Needs" (e.g., self-heals, condition removal).

## Core Components

*   **`bookah.py`**: Entry point for the primary UI application (built with `tkinter` / `customtkinter`).
*   **`analyzer.py`**: Standalone utility for generating interactive synergy maps using `pyvis` and `networkx`.
*   **`src/engine.py`**: The primary logic hub for skill filtering, suggestion ranking, and team context management.
*   **`src/skill2vec.py`**: Interface for neural embedding lookups and vector similarity calculations.
*   **`master.db`**: SQLite database containing the skill registry, ID mappings, and raw mechanics data.

## Prerequisites

*   Python 3.10 or 3.11
*   Cuda-capable GPU (optional, for faster embedding inference)

## Installation

```bash
# Clone the repository
git clone https://github.com/SavvyStuffs/BOOKAH.git
cd BOOKAH

# Install dependencies
pip install -r requirements.txt
```

## Usage

### GUI Application
Launch with:
```bash
python bookah.py
```

## Data Assets

*   **`description_embeddings.pt`**: Pre-computed PyTorch tensors for skill semantics.
*   **`skill_vectors.model`**: Trained Word2Vec model for behavioral analysis.
*   **`all_skills.json`**: Source data for statistical analysis (extracted from PvX Wiki).

## License

Distributed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license. See `LICENSE` for details.