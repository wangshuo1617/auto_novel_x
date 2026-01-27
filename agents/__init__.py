"""智能体核心逻辑模块"""

# 为方便外部直接 import，这里做一次集中导出
from .trend_scout import TrendScout
from .world_architect import WorldArchitect
from .element_designer import ElementDesigner
from .plot_engineer import PlotEngineer
from .draft_smith import DraftSmith
from .style_polisher import StylePolisher
from .continuity_keeper import ContinuityKeeper

# 新增：已根据 prompt 补齐的智能体模块
from .arc_director import ArcDirector
from .lore_archivist import LoreArchivist
from .simulated_reader import SimulatedReader

__all__ = [
    "TrendScout",
    "WorldArchitect",
    "ElementDesigner",
    "PlotEngineer",
    "DraftSmith",
    "StylePolisher",
    "ContinuityKeeper",
    "ArcDirector",
    "LoreArchivist",
    "SimulatedReader",
]

