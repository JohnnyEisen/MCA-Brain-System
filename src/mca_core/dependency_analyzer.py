import logging
from collections import defaultdict
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

logger = logging.getLogger(__name__)

class DependencyAnalyzer:
    def __init__(self, mod_list, dependency_pairs):
        """
        mod_list: dict of mod_id -> set(versions)
        dependency_pairs: list of (mod_id, depends_on_mod_id)
        """
        self.mod_list = mod_list
        self.dependency_pairs = dependency_pairs
        self.graph = self._build_graph()

    def _build_graph(self):
        if not HAS_NETWORKX:
            return None
        G = nx.DiGraph()
        for mod in self.mod_list:
            G.add_node(mod)
        for src, dst in self.dependency_pairs:
            G.add_edge(src, dst)
        return G

    def detect_cycles(self):
        if not self.graph:
            return []
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except Exception as e:
            logger.error(f"Error detecting cycles: {e}")
            return []

    def analyze_version_conflicts(self):
        # This requires more detailed dependency info (e.g. version ranges)
        # which might not be fully available from simple log parsing.
        # We will implement a placeholder or basic check if version info is passed.
        conflicts = []
        # Logic to check if multiple versions of the same mod are required
        # or if installed version doesn't match requirement.
        return conflicts

    def get_conflict_combinations(self, known_conflicts):
        """
        known_conflicts: list of dicts defining incompatible mod sets
        e.g. [{"mods": ["modA", "modB"], "reason": "..."}]
        """
        found_conflicts = []
        installed_mods = set(self.mod_list.keys())
        
        for conflict in known_conflicts:
            conflict_mods = set(conflict.get("mods", []))
            if conflict_mods.issubset(installed_mods):
                found_conflicts.append({
                    "mods": list(conflict_mods),
                    "reason": conflict.get("reason", "Unknown conflict")
                })
        return found_conflicts
