import argparse
import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

try:
    from tools.neural_adversary import NeuralAdversaryEngine
    HAS_NEURAL_ENGINE = True
except ImportError:
    # Try local import if running directly e.g. from tools/
    try:
        # Add parent dir to path to find config
        import sys
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            
        from config.constants import DEFAULT_MAX_BYTES
        from neural_adversary import NeuralAdversaryEngine
        HAS_NEURAL_ENGINE = True
    except ImportError:
        HAS_NEURAL_ENGINE = False
        DEFAULT_MAX_BYTES = 8 * 1024 * 1024 # Fallback
        print("[Warning] neural_adversary or config not found. Falling back to defaults.")

try: 
    from config.constants import DEFAULT_MAX_BYTES
except ImportError:
    DEFAULT_MAX_BYTES = 8 * 1024 * 1024

SIZE_UNITS = {
    "b": 1,
    "bytes": 1,
    "k": 1024,
    "kb": 1024,
    "m": 1024 ** 2,
    "mb": 1024 ** 2,
    "g": 1024 ** 3,
    "gb": 1024 ** 3,
}

DEFAULT_MAX_SINGLE_SIZE = DEFAULT_MAX_BYTES

LEVELS = ["INFO", "WARN", "ERROR", "DEBUG", "TRACE"]
THREADS = ["main", "Render thread", "Server thread", "Worker-1", "Worker-2", "IO-Worker", "Netty Client IO"]

GAME_VERSIONS = ["1.20.1", "1.19.2", "1.18.2", "1.16.5"]
JAVA_VERSIONS = ["17.0.10", "21.0.2", "1.8.0_312"]
OS_LIST = ["Windows 11 (10.0)", "Windows 10 (10.0)", "Linux (5.15)"]
GPU_LIST = [
    "NVIDIA GeForce RTX 3060",
    "NVIDIA GeForce GTX 1660",
    "AMD Radeon RX 6600",
    "Intel(R) UHD Graphics 770",
]

LOADERS = [
    {"name": "Forge", "id": "forge", "logger": "net.minecraftforge.fml.loading"},
    {"name": "Fabric", "id": "fabric", "logger": "net.fabricmc.loader"},
    {"name": "NeoForge", "id": "neoforge", "logger": "net.neoforged.fml.loading"},
]

LOGGER_NAMES = [
    "minecraft/Minecraft",
    "fml/LOADING",
    "net.minecraftforge.fml.loading",
    "ModLauncher",
    "ResourcePack",
    "mixin/PROCESSOR",
    "RenderSystem",
    "SoundEngine",
    "ChunkRender",
    "net.minecraft.client.renderer",
    "com.mojang.authlib",
    "net.minecraft.server.MinecraftServer",
    "net.minecraft.client.main.Main",
    "NetworkManager",
    "LWJGL",
]

MOD_LIBRARY = [
    {"id": "journeymap", "versions": ["5.9.18", "5.9.15"], "name": "JourneyMap"},
    {"id": "jei", "versions": ["15.2.0.22", "15.1.0.19"], "name": "Just Enough Items"},
    {"id": "sodium", "versions": ["0.5.7", "0.4.11"], "name": "Sodium"},
    {"id": "iris", "versions": ["1.6.17", "1.6.12"], "name": "Iris Shaders"},
    {"id": "lithium", "versions": ["0.11.1", "0.10.5"], "name": "Lithium"},
    {"id": "create", "versions": ["0.5.1.c", "0.5.1.b"], "name": "Create"},
    {"id": "appliedenergistics2", "versions": ["15.0.14", "14.1.2"], "name": "AE2"},
    {"id": "botania", "versions": ["1.20.1-445", "1.19.2-440"], "name": "Botania"},
    {"id": "mekanism", "versions": ["10.4.6", "10.3.9"], "name": "Mekanism"},
    {"id": "thermal", "versions": ["10.0.0", "9.3.0"], "name": "Thermal"},
    {"id": "geckolib", "versions": ["4.4.9", "4.3.1"], "name": "GeckoLib"},
    {"id": "architectury", "versions": ["9.1.12", "8.2.89"], "name": "Architectury"},
]

MIXINS = [
    "mixins.common.json:BlockMixin",
    "mixins.client.json:RenderMixin",
    "mixins.common.json:ItemMixin",
    "mixins.server.json:ServerChunkMixin",
    "mixins.render.json:BufferBuilderMixin",
]

PACKS = [
    "Default",
    "VanillaTweaks",
    "BetterLeaves",
    "Faithful32x",
    "ComplementaryShaders",
]

RESOURCES = [
    "minecraft:textures/blocks/stone.png",
    "minecraft:textures/blocks/oak_log.png",
    "minecraft:textures/gui/widgets.png",
    "minecraft:textures/environment/moon_phases.png",
]

ITEMS = [
    "minecraft:iron_ingot",
    "minecraft:diamond",
    "minecraft:oak_planks",
    "minecraft:ancient_debris",
]

HOSTS = [
    "play.example.net:25565",
    "127.0.0.1:25565",
    "mc.hypothetical.org:25565",
    "vanilla.survival.gg:25565",
]

REASONS = [
    "Registry object is null",
    "Failed to load class net.minecraft.client.Minecraft",
    "Out of memory: Java heap space",
    "Missing mod dependency",
    "Invalid Mixin configuration",
    "Unexpected error during resource reload",
    "Chunk rendering failed due to invalid buffer state",
]

MOD_CLASSES = [
    "ExampleMod",
    "WorldGen",
    "ClientHooks",
    "ServerHooks",
    "RenderPipeline",
]

STARTUP_MESSAGES = [
    "ModLauncher running: args {args}",
    "Loading Minecraft {mc_version} with {loader} {loader_ver}",
    "Found mod file /mods/{modjar}",
    "Launching in {profile} mode",
    "LWJGL Version: {lwjgl}",
    "OpenGL Version: {glver}",
    "Using default game log config client-1.12.xml (outputs: file)",
]

LOADING_MESSAGES = [
    "Applying mixin: {mixin}",
    "Skipping unknown resource pack {pack}",
    "Loading model {res}",
    "Loaded {count} recipes",
    "Registry remapped {count} objects",
    "Resource reload completed in {ms}ms",
    "Data pack {pack} missing metadata", 
    "Language '{lang}' loaded ({count} entries)",
]

PLAY_MESSAGES = [
    "Preparing spawn area: {pct}%",
    "Server thread ping took {ms}ms", 
    "Saved game successfully",
    "World backup complete",
    "Chunk {x},{z} was in an unexpected state",
    "Recipe conflict detected for {item}",
    "Network channel pipeline rebuilt",
    "Packet size {count} exceeds threshold",
    "Connecting to server {host}",
    "GC pause detected: {ms}ms",
]

WARNING_MESSAGES = [
    "Slow operation detected: {ms}ms",
    "Resource pack {pack} contains invalid characters",
    "Mod {mod} is missing a mcmod.info file",
    "Sound {res} not found",
    "Unknown recipe type: {item}",
    "Skipping entity with invalid data at {x}, {z}",
    "Unable to play sound: {res}",
]

SCENARIOS = {
    "normal": {
        "description": "常规启动+轻微告警",
        "error_bias": 0.0,
        "warnings_bias": 0.0,  # Reduced from 0.08 to prevent random unsafe warnings
        "extra_lines": [],
        "force_reason": None,
        "safe_mode": True,    # Flag for _format_message
    },
    "oom": {
        "description": "内存不足崩溃",
        "error_bias": 0.02,
        "warnings_bias": 0.12,
        "extra_lines": [
            "[GC] Pause Young (Allocation Failure) {ms}ms",
            "[GC] Pause Full (Ergonomics) {ms}ms",
            "java.lang.OutOfMemoryError: Java heap space",
            "java.lang.OutOfMemoryError: Metaspace",
            "java.lang.OutOfMemoryError: GC overhead limit exceeded"
        ],
        "force_reason": [
            "Out of memory: Java heap space",
            "Out of memory: Metaspace",
            "Out of memory: GC overhead limit exceeded",
            "Exception in thread \"main\" java.lang.OutOfMemoryError"
        ],
    },
    "missing_dependency": {
        "description": "模组依赖缺失",
        "error_bias": 0.02,
        "warnings_bias": 0.15,
        "extra_lines": [
            "Missing or unsupported mandatory dependencies: {dep}",
            "Mod ID: '{dep}'",
            "Mod {mod} requires {dep}",
            "Could not look up mod dependency {dep}",
            "Requirements for {mod} not met"
        ],
        "force_reason": [
            "Missing mod dependency",
            "Mod resolution failed",
            "Dependency requirements not met",
            "Failed to validate mod dependencies"
        ],
    },
    "gl_error": {
        "description": "OpenGL/渲染错误",
        "error_bias": 0.015,
        "warnings_bias": 0.12,
        "extra_lines": [
            "OpenGL debug message: id={count}, source=API, type=ERROR, severity=HIGH, message=GL_INVALID_OPERATION",
            "GLFW error 65542: WGL: The driver does not appear to support OpenGL",
            "OpenGL error 1282: Invalid operation",
            "Render thread failed to initialize buffer",
            "Extremely high tick lag detected during rendering"
        ],
        "force_reason": [
            "Chunk rendering failed due to invalid buffer state",
            "Tesselating block model failed",
            "Unable to initialize OpenGL context",
            "Encountered an unexpected exception during render"
        ],
    },
    "mixin_conflict": {
        "description": "Mixin 冲突",
        "error_bias": 0.02,
        "warnings_bias": 0.18,
        "extra_lines": [
            "Mixin apply failed {mixin}",
            "Invalid Mixin configuration {mixin}",
            "Found incompatible mixin configuration",
            "Mod {mod} failed to load mod due to conflict",
            "Mixin transformation error"
        ],
        "force_reason": [
            "Invalid Mixin configuration",
            "Mixin transformation failed",
            "Critical injection failure",
            "Compatibility error in Mixin config"
        ],
    },
    "version_conflict": {
        "description": "版本不兼容/冲突",
        "error_bias": 0.012,
        "warnings_bias": 0.14,
        "extra_lines": [
            "Mod {mod} has failed to load correctly",
            "Mod {mod} requires minecraft {mc_version}+",
            "Found mod file /mods/{modjar_conflict1}",
            "Found mod file /mods/{modjar_conflict2}",
            "Mod {mod} is incompatible with loaded version",
            "Version mismatch for {mod}"
        ],
        "force_reason": [
            "Failed to load class net.minecraft.client.Minecraft",
            "Mod incompatible with game version",
            "Version mismatch detected",
            "Duplicate mod found"
        ],
    },
    "compound": {
        "description": "复合型错误 (多因素叠加)",
        "error_bias": 0.03,
        "warnings_bias": 0.22,
        "extra_lines": [
            "Missing or unsupported mandatory dependencies: {dep}",
            "Mixin apply failed {mixin}",
            "OpenGL debug message: id={count}, source=API, type=ERROR, severity=HIGH, message=GL_INVALID_OPERATION",
            "Failed to load texture: {res}",
            "Mod {mod} has failed to load correctly",
        ],
        "force_reason": None,
    },
    "adversarial": {
        "description": "[AI] 对抗性融合样本 (Adversarial Fusion)",
        "error_bias": 0.05,
        "warnings_bias": 0.5, # Extreme noise
        "extra_lines": [], # Handled dynamically by Fuser
        "force_reason": None, # Handled dynamically
    },
}


def _pick_version_conflict_pair(rng: random.Random) -> tuple[str, str] | None:
    candidates = [m for m in MOD_LIBRARY if len(m.get("versions", [])) >= 2]
    if not candidates:
        return None
    mod = rng.choice(candidates)
    versions = rng.sample(mod["versions"], k=2)
    return f"{mod['id']}-{versions[0]}.jar", f"{mod['id']}-{versions[1]}.jar"


def _scenario_signal_lines(rng: random.Random, scenario: str, context: dict) -> list[str]:
    dep = rng.choice(["geckolib", "architectury", "fabric-api", "cloth-config"])
    mod = rng.choice(context["mods"])["id"] if context.get("mods") else "examplemod"
    mixin = rng.choice(MIXINS)
    conflict_pair = context.get("version_conflict_pair") or ("example-1.0.0.jar", "example-2.0.0.jar")

    if scenario == "oom":
        return [
            "java.lang.OutOfMemoryError: Java heap space",
            "[GC] Pause Full (Ergonomics) 1200ms",
        ]
    if scenario == "missing_dependency":
        return [
            f"Missing or unsupported mandatory dependencies: {dep}",
            f"Mod ID: '{dep}'",
            f"Mod {mod} requires {dep}",
        ]
    if scenario == "gl_error":
        return [
            "GLFW error 65542: WGL: The driver does not appear to support OpenGL",
            "OpenGL error 1282: Invalid operation",
        ]
    if scenario == "mixin_conflict":
        return [
            f"Invalid Mixin configuration {mixin}",
            "Found incompatible mixin configuration",
        ]
    if scenario == "version_conflict":
        return [
            f"Found mod file /mods/{conflict_pair[0]}",
            f"Found mod file /mods/{conflict_pair[1]}",
            f"Mod {mod} is incompatible with loaded version",
        ]
    if scenario == "compound":
        return [
            f"Missing or unsupported mandatory dependencies: {dep}",
            f"Invalid Mixin configuration {mixin}",
            "OpenGL error 1282: Invalid operation",
            "java.lang.OutOfMemoryError: Java heap space",
        ]
    return []


def parse_size(value: str) -> int:
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$", value)
    if not match:
        raise ValueError(f"无法解析大小: {value}")
    num = float(match.group(1))
    unit = match.group(2).lower() or "b"
    if unit not in SIZE_UNITS:
        raise ValueError(f"未知单位: {unit}")
    return int(num * SIZE_UNITS[unit])


def choose_size(args: argparse.Namespace) -> int:
    if args.size:
        return parse_size(args.size)
    if args.min_size and args.max_size:
        min_b = parse_size(args.min_size)
        max_b = parse_size(args.max_size)
        if max_b < min_b:
            min_b, max_b = max_b, min_b
        return random.randint(min_b, max_b)
    if args.min_size:
        return parse_size(args.min_size)
    if args.max_size:
        return parse_size(args.max_size)
    return parse_size("5mb")


def _format_message(rng: random.Random, phase: str, context: dict, fuser=None, progress=0.0) -> str:
    picked_mod = rng.choice(context["mods"])
    modjar_mod = rng.choice(context["mods"])
    conflict_pair = context.get("version_conflict_pair")
    base = {
        "mod": picked_mod["id"],
        "modclass": rng.choice(MOD_CLASSES),
        "mixin": rng.choice(MIXINS),
        "pack": rng.choice(PACKS),
        "pct": rng.randint(1, 100),
        "host": rng.choice(HOSTS),
        "count": rng.randint(1, 5000),
        "ms": rng.randint(1, 5000),
        "item": rng.choice(ITEMS),
        "res": rng.choice(RESOURCES),
        "x": rng.randint(-5000, 5000),
        "z": rng.randint(-5000, 5000),
        "mc_version": context["game_version"],
        "loader": context["loader"]["name"],
        "loader_ver": context["loader_version"],
        "modjar": f"{modjar_mod['id']}-{modjar_mod['version']}.jar",
        "modjar_conflict1": conflict_pair[0] if conflict_pair else f"{picked_mod['id']}-{picked_mod['version']}.jar",
        "modjar_conflict2": conflict_pair[1] if conflict_pair else f"{picked_mod['id']}-{picked_mod['version']}.jar",
        "profile": rng.choice(["client", "development", "vanilla"]),
        "lwjgl": rng.choice(["3.3.2", "3.3.1", "3.2.3"]),
        "glver": rng.choice(["4.6", "4.5", "3.3"]),
        "lang": rng.choice(["en_us", "zh_cn", "ja_jp"]),
        "args": "--username Player --version {mc_version}".format(mc_version=context["game_version"]),
    }

    if phase == "startup":
        template = rng.choice(STARTUP_MESSAGES)
    elif phase == "loading":
        template = rng.choice(LOADING_MESSAGES)
    elif phase == "play":
        template = rng.choice(PLAY_MESSAGES)
    else:
        template = rng.choice(PLAY_MESSAGES)


    # Realistic complexity injection:
    # 30% chance to inject random "background noise" (benign errors/warnings) regardless of context
    # This simulates a real modpack where logs are never perfectly clean.
    if rng.random() < 0.30:
         pool = BACKGROUND_NOISE
         # Occasional "scary looking but harmless" messages
         if rng.random() < 0.05:
             pool += SCARY_BUT_HARMLESS_NOISE
         template = rng.choice(pool)

    if rng.random() < context.get("warnings_bias", 0.08):
        if context.get("safe_mode"):
            # Safe Mode: only gentle warnings
            template = rng.choice([
                "Mod {mod} requested re-init",
                "Datapack validation failed for {pack}",
                "Skipping unknown resource pack {pack}",
                "[KubeJS] Loading scripts...", # Tweaker noise is usually safe
            ])
        else:
            # Mix regular warnings with heavy tweaker/mixin spam if configured
            pool = WARNING_MESSAGES + TWEAKER_MESSAGES
            # If we are in specific scenarios, we might skew towards related noise
            # but usually we want specific noise.
            template = rng.choice(pool)
    
    # === Adversarial Injection ===
    if fuser:
        decoy_msg = fuser.inject_decoy_signal(phase, progress)
        if decoy_msg:
            return decoy_msg
    # =============================

    return template.format(**base)


def _format_log_line(ts: datetime, rng: random.Random, message: str, level: str | None = None, logger_name: str | None = None, thread: str | None = None) -> str:
    lvl = level or rng.choice(LEVELS)
    module = logger_name or rng.choice(LOGGER_NAMES)
    tname = thread or rng.choice(THREADS)
    return f"[{ts.strftime('%H:%M:%S.%f')[:-3]}] [{tname}/{lvl}] [{module}]: {message}\n"


# 扩充模组库：Tech, Magic, QoL, Libs, Tweakers
TECH_MODS = [
    ("mekanism", "Mekanism", ["10.4.6", "10.3.9"]),
    ("mekanism_generators", "Mekanism Generators", ["10.4.6", "10.3.9"]),
    ("mekanism_tools", "Mekanism Tools", ["10.4.6", "10.3.9"]),
    ("thermal_expansion", "Thermal Expansion", ["10.0.0", "9.3.0"]),
    ("thermal_foundation", "Thermal Foundation", ["10.0.0", "9.3.0"]),
    ("thermal_dynamics", "Thermal Dynamics", ["10.0.0", "9.3.0"]),
    ("avaritia", "Avaritia", ["1.0.0", "0.9.5"]),
    ("draconicevolution", "Draconic Evolution", ["3.0.28", "3.0.25"]),
    ("enderio", "Ender IO", ["6.0.22", "5.3.70"]),
    ("ae2", "Applied Energistics 2", ["15.0.14", "14.1.2"]),
    ("refinedstorage", "Refined Storage", ["1.12.3", "1.11.7"]),
    ("immersiveengineering", "Immersive Engineering", ["9.2.2", "8.4.0"]),
    ("create", "Create", ["0.5.1.c", "0.5.1.f"]),
    ("create_stuff_additions", "Create Stuff & Additions", ["2.0.1", "1.1.0"]),
    ("gregtech", "GregTech CEu", ["2.6.2", "2.5.0"]),
]

MAGIC_MODS = [
    ("botania", "Botania", ["445", "440"]),
    ("thaumcraft", "Thaumcraft", ["6.1.7", "6.1.1"]),
    ("bloodmagic", "Blood Magic", ["3.2.6", "3.1.9"]),
    ("ars_nouveau", "Ars Nouveau", ["4.2.0", "3.8.1"]),
    ("occultism", "Occultism", ["1.100.0", "1.85.0"]),
    ("astralsorcery", "Astral Sorcery", ["1.16.2", "1.15.0"]),
    ("irons_spellbooks", "Iron's Spells 'n Spellbooks", ["3.0.1", "2.1.2"]),
    ("twilightforest", "The Twilight Forest", ["4.3.0", "4.2.1"]),
]

QOL_MODS = [
    ("jei", "Just Enough Items", ["15.2.0.22", "11.6.0.1016"]),
    ("jer", "Just Enough Resources", ["1.3.1", "0.14.0"]),
    ("jade", "Jade", ["11.6.2", "8.7.1"]),
    ("theoneprobe", "The One Probe", ["10.0.0", "9.0.0"]),
    ("journeymap", "JourneyMap", ["5.9.18", "5.9.7"]),
    ("xaerominimap", "Xaero's Minimap", ["23.8.4", "22.17.0"]),
    ("mouse_tweaks", "Mouse Tweaks", ["2.25", "2.14"]),
    ("controlling", "Controlling", ["12.0.2", "10.0.0"]),
    ("appleskin", "AppleSkin", ["2.5.1", "2.4.0"]),
    ("clumps", "Clumps", ["12.0.0", "9.0.4"]),
    ("fastleafdecay", "Fast Leaf Decay", ["30", "28"]),
]

LIB_MODS = [
    ("geckolib", "GeckoLib", ["4.4.9", "4.2.0", "3.1.40"]),
    ("architectury", "Architectury API", ["9.1.12", "6.5.77"]),
    ("cloth_config", "Cloth Config", ["11.1.106", "8.2.88"]),
    ("curios", "Curios API", ["5.9.1", "5.4.2"]),
    ("patchouli", "Patchouli", ["81", "77"]),
    ("citadel", "Citadel", ["2.4.1", "1.9.0"]),
    ("balm", "Balm", ["7.1.4", "4.6.0"]),
    ("bookshelf", "Bookshelf", ["19.0.12", "16.1.11"]),
    ("placebo", "Placebo", ["8.3.1", "7.1.2"]),
    ("titanium", "Titanium", ["3.8.22", "3.7.10"]),
    ("forge", "Forge", ["47.1.0", "43.2.0"]), # Often shows up in mod list
]

TWEAKER_MODS = [
    ("kubejs", "KubeJS", ["2001.6.4-build.120", "1902.6.1-build.300"]),
    ("rhino", "Rhino", ["2001.2.2-build.18", "1902.2.9-build.14"]),
    ("crafttweaker", "CraftTweaker", ["14.0.18", "10.1.37"]),
    ("contenttweaker", "ContentTweaker", ["1.0.0", "0.5.0"]),
    ("mixinbooter", "MixinBooter", ["8.8", "8.6"]),
]

# Flatten for generation
EXTENDED_MOD_LIBRARY = []
for cat in [TECH_MODS, MAGIC_MODS, QOL_MODS, LIB_MODS, TWEAKER_MODS]:
    for mid, mname, mvers in cat:
        EXTENDED_MOD_LIBRARY.append({"id": mid, "name": mname, "versions": mvers})

# Benign background noise (Realism)
BACKGROUND_NOISE = [
    "Signature is missing from Jar file for {modjar}",
    "Potentially Dangerous alternative prefix 'minecraft' for name '{item}'",
    "Parsing error loading built-in advancement {mod}:init",
    "Ignoring recipe {mod}:crafting for {item}",
    "Unable to play empty soundEvent: minecraft:entity.generic.small_fall",
    "Fetching skin for {host}",
    "User {host} connected with UUID {count}",
    "Syncing Entity Data... {pct}%",
    "Advancements reloaded for {count} players",
    "Couldn't load loot table {res}",
    "Empty height range: {x} to {z}",
    "Sent {count} bytes to server",
    "Received {count} bytes from server",
    "Can't keep up! Is the server overloaded? Running {ms}ms or {pct} ticks behind",
]

# Messages that look scary but are usually not the crash cause
SCARY_BUT_HARMLESS_NOISE = [
    "An exception was thrown, the game will display an error screen and halt.", # Note: often printed by mods handling errors gracefully
    "Caught exception in thread 'Render Thread'", # Sometimes just a flicker
    "Narrator library not available",
    "Failed to load 'options.txt', defaults loaded",
    "Sound system started, but {count} sounds failed to preload",
    "Ambiguity between {mod} and minecraft items",
]

# Extra heavy spam messages for KubeJS/Tweakers
TWEAKER_MESSAGES = [
    "[KubeJS] Loading scripts...",
    "[KubeJS] Scripts loaded successfully in {ms}ms",
    "[KubeJS] Server script 'server_scripts/recipes.js' loaded",
    "[KubeJS] Client script 'client_scripts/tooltip.js' loaded",
    "[CraftTweaker] Starting script loading...",
    "[CraftTweaker] Loaded 1245 recipes in {ms}ms",
    "[CraftTweaker] Recipe modification at line 42: minecraft:iron_ingot",
    "[Mixin] Prepared {count} mixins for {mod}",
    "[Mixin] Mixing {mixin} into {modclass}",
    "[DataPack] Reloading data packs: [vanilla, modresources, KubeJS, custom_tweaks]",
    "Reloading ResourceManager: Default, Fabric Mods, KubeJS Resource Pack",
]

def _pick_mods(rng: random.Random) -> list[dict]:
    # Simulate realistic pack sizes:
    # 20% small (10-30), 50% medium (50-120), 30% huge (200-350)
    roll = rng.random()
    if roll < 0.2:
        count = rng.randint(10, 30)
    elif roll < 0.7:
        count = rng.randint(50, 150)
    else:
        count = rng.randint(200, 350)
    
    # Ensure dependencies and cores are picked
    core_mods = rng.sample([m for m in EXTENDED_MOD_LIBRARY if m["id"] in ["jei", "geckolib", "architectury", "cloth_config"]], k=3)
    
    # Pick rest
    others_pool = [m for m in EXTENDED_MOD_LIBRARY if m not in core_mods]
    # Allow duplicates to simulate addons or weird shading? No, unique IDs usually.
    # But for "hundreds of mods" we might need to fake some if library is small.
    # We'll just sample with replacement if count > len, creating "addon" names.
    
    picked_list = list(core_mods)
    
    if count < len(others_pool):
        picked_list.extend(rng.sample(others_pool, k=count - len(core_mods)))
    else:
        picked_list.extend(others_pool)
        # Generate fake addons for filler
        needed = count - len(picked_list)
        base_mods = [m for m in EXTENDED_MOD_LIBRARY if "api" not in m["id"]]
        for _ in range(needed):
            base = rng.choice(base_mods)
            suffix = rng.choice(["Addon", "Tweaks", "Integration", "Plus", "Expansion", "Compat"])
            picked_list.append({
                "id": f"{base['id']}_{suffix.lower()}",
                "name": f"{base['name']} {suffix}",
                "versions": base["versions"]
            })
            
    final_picked = []
    for m in picked_list:
        final_picked.append({
            "id": m["id"],
            "name": m["name"],
            "version": rng.choice(m["versions"]),
        })
    return final_picked


def _format_mod_list_lines(mods: list[dict]) -> list[str]:
    lines = []
    for m in mods:
        lines.append(f"\t\t{m['id']}\t\t{m['version']}\t\t{m['name']}\n")
    return lines


def _format_crash_report(ts: datetime, rng: random.Random, context: dict) -> list[str]:
    reason = context.get("force_reason") or rng.choice(REASONS)
    mod = rng.choice(context["mods"])
    modclass = rng.choice(MOD_CLASSES)
    crash_id = rng.randint(100000, 999999)

    # Dynamic stack trace generation
    stack_template = []
    if "Out of memory" in reason or "Memory" in reason:
        stack_template = [
            f"{reason}\n",
            "\tat java.util.Arrays.copyOf(Arrays.java:3332)\n",
            "\tat java.lang.AbstractStringBuilder.ensureCapacityInternal(AbstractStringBuilder.java:124)\n",
            "\tat java.lang.StringBuilder.append(StringBuilder.java:448)\n"
        ]
    elif "Mixin" in reason:
        stack_template = [
            "org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: An unexpected critical error was encountered\n",
            f"\tat org.spongepowered.asm.mixin.transformer.MixinProcessor.applyMixins(MixinProcessor.java:363)\n",
            f"Caused by: org.spongepowered.asm.mixin.throwables.MixinApplyError: {reason}\n",
            f"\tat org.spongepowered.asm.mixin.transformer.MixinApplicatorStandard.apply(MixinApplicatorStandard.java:322)\n"
        ]
    elif "rendering" in reason or "OpenGL" in reason or "Tesselating" in reason:
        stack_template = [
            "net.minecraft.client.renderer.GameRenderer.func_195458_a(GameRenderer.java:820)\n",
            f"\tat net.minecraft.client.renderer.LevelRenderer.func_228418_a_(LevelRenderer.java:1320) ~[?:?]\n",
            f"\tat net.minecraft.client.renderer.LevelRenderer.func_228426_a_(LevelRenderer.java:1120) ~[?:?]\n",
            "Caused by: org.lwjgl.opengl.OpenGLException: Invalid operation (1282)\n"
        ]
    elif "dependency" in reason or "Missing" in reason:
         stack_template = [
            "net.minecraftforge.fml.LoadingFailedException: Loading errors encountered: [\n",
            f"\t{reason}\n",
            "]\n",
            "\tat net.minecraftforge.fml.ModLoader.waitForTransition(ModLoader.java:270) ~[fml:?]\n",
            "\tat net.minecraftforge.fml.ModLoader.dispatchAndHandleError(ModLoader.java:234) ~[fml:?]\n"
        ]
    else:
        stack_template = [
            f"java.lang.RuntimeException: {reason}\n",
             f"\tat com.example.mod.{modclass}.init({modclass}.java:42)\n",
             "\tat net.minecraft.client.Minecraft.run(Minecraft.java:790)\n",
             f"Caused by: java.lang.NullPointerException: {reason}\n"
        ]

    lines = [
        "---- Minecraft Crash Report ----\n",
        "// This doesn't make any sense!\n",
        "\n",
        f"Time: {ts.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"Description: {reason}\n",
        "\n",
    ] + stack_template

    lines.extend([
        "\n",
        "A detailed walkthrough of the error, its code path and all known details is as follows:\n",
        "---------------------------------------------------------------------------------------\n",
        "\n",
        f"-- Head --\n",
        f"Thread: {rng.choice(THREADS)}\n",
        f"Stacktrace:\n",
        f"\tat net.minecraft.client.Minecraft.runTick(Minecraft.java:770)\n",
        f"\tat net.minecraft.client.main.Main.main(Main.java:197)\n",
        "\n",
        "-- System Details --\n",
        f"Minecraft Version: {context['game_version']}\n",
        f"Minecraft Version ID: {context['game_version']}\n",
        f"Operating System: {context['os']}\n",
        f"Java Version: {context['java_version']}, {context['java_vendor']}\n",
        f"Java VM Version: {context['java_vm']}\n",
        f"Memory: {context['memory_used']} MB / {context['memory_total']} MB\n",
        f"CPUs: {context['cpu_count']}\n",
        f"GPU: {context['gpu']}\n",
        f"Loader: {context['loader']['name']} {context['loader_version']}\n",
        "\n",
        "-- Mod List --\n",
        "\t\tName\t\tVersion\t\tIdentifier\n",
    ])
    lines.extend(_format_mod_list_lines(context["mods"]))
    lines.extend([
        "\n",
        f"Crash Report UUID: {crash_id}\n",
    ])
    return lines


class AdversarialFuser:
    """
    Implements a GAN-like (Generative Adversarial Network) logic to 'fuse' multiple error 
    signatures into a single log. 
    Now upgraded to use Real Neural Networks (PyTorch) if available.
    """
    def __init__(self, rng, context):
        self.rng = rng
        self.context = context
        self.real_scenario = None
        self.decoy_scenarios = []
        
        # Initialize Neural Engine
        self.neural_agent = None
        if HAS_NEURAL_ENGINE:
            try:
                self.neural_agent = NeuralAdversaryEngine()
                self.neural_agent.load("e:/分析/analysis_data/adversary_model.pth")
            except Exception as e:
                print(f"[Adversary] Failed to init neural engine: {e}")

    def setup_fusion(self, available_scenarios):
        # 1. Pick a Hidden Truth (Real fatal error)
        candidates = [s for s in available_scenarios if s not in ["normal", "compound", "adversarial"]]
        self.real_scenario = self.rng.choice(candidates)
        
        # 2. Pick Decoys (Fake errors that appear loudly but aren't fatal)
        decoys = [s for s in candidates if s != self.real_scenario]
        self.decoy_scenarios = self.rng.sample(decoys, k=self.rng.randint(1, 2))
        
        return self.real_scenario

    def inject_decoy_signal(self, phase, progress):
        """
        Uses either Heuristic RNG or Neural Network to decide injection.
        """
        should_inject = False
        mutation_type = 0
        
        # A. Neural Policy (Real AI)
        if self.neural_agent:
            # phases: startup=0, loading=1, play=2
            phase_map = {"startup": 0, "loading": 1, "play": 2}
            p_idx = phase_map.get(phase, 1)
            
            # Action Space: 0=NoOp, 1=Inject_Noise, 2=Inject_Decoy, 3=Mutate, 4=Suppress
            action = self.neural_agent.decide_action("adversarial", progress, p_idx)
            
            if action == 2 or action == 3:
                should_inject = True
        
        # B. Simulated Heuristic (Fallback)
        else:
            if self.rng.random() < 0.15:
                should_inject = True

        # Execution
        if should_inject and self.decoy_scenarios:
            decoy = self.rng.choice(self.decoy_scenarios)
            signals = _scenario_signal_lines(self.rng, decoy, self.context)
            if signals:
                raw_sig = self.rng.choice(signals)
                mutations = [
                    f"[Suppressor] Swallowed exception: {raw_sig}",
                    f"[Watchdog] Detected potential issue (handled): {raw_sig}",
                    f"[Adversarial] Mocking error signal: {raw_sig}",
                    f"Example of error: {raw_sig}", 
                    raw_sig + " (ignored)"
                ]
                return self.rng.choice(mutations)
        return None


def write_log(output_path: str, target_bytes: int, seed: int | None, scenario: str = "normal", max_single_size: int | None = None) -> Tuple[int, int, dict]:
    rng = random.Random(seed)
    ts = datetime.now()
    max_single = max_single_size or DEFAULT_MAX_SINGLE_SIZE
    target_bytes = min(target_bytes, max_single)
    bytes_written = 0
    lines_written = 0
    buffer: list[str] = []
    buffer_bytes = 0
    buffer_limit = 1024 * 1024

    scenario_cfg = SCENARIOS.get(scenario, SCENARIOS["normal"])
    
    # === Adversarial Fusion Logic ===
    fuser = None
    real_scenario_key = scenario
    if scenario == "adversarial":
        fuser = AdversarialFuser(rng, {}) # Context updated later
        # We temporarily need valid scenarios list to pick from
        valid_keys = list(SCENARIOS.keys())
        real_scenario_key = fuser.setup_fusion(valid_keys)
        # We switch the 'effective' config to the real hidden error
        scenario_cfg = SCENARIOS.get(real_scenario_key, SCENARIOS["normal"])
        print(f"DEBUG: Adversarial active. Hidden Truth: {real_scenario_key}. Error Bias: {scenario_cfg.get('error_bias')}")
    # ================================

    conflict_pair = _pick_version_conflict_pair(rng) if real_scenario_key == "version_conflict" else None
    reason_raw = scenario_cfg.get("force_reason")
    if isinstance(reason_raw, list):
        picked_reason = rng.choice(reason_raw)
    else:
        picked_reason = reason_raw

    context = {
        "game_version": rng.choice(GAME_VERSIONS),

        "loader": rng.choice(LOADERS),
        "loader_version": f"{rng.randint(1, 50)}.{rng.randint(0, 9)}.{rng.randint(0, 9)}",
        "java_version": rng.choice(JAVA_VERSIONS),
        "java_vendor": rng.choice(["Oracle Corporation", "Eclipse Adoptium", "Microsoft", "Azul Systems"]),
        "java_vm": rng.choice(["OpenJDK 64-Bit Server VM", "Java HotSpot(TM) 64-Bit Server VM"]),
        "os": rng.choice(OS_LIST),
        "gpu": rng.choice(GPU_LIST),
        "cpu_count": rng.choice([4, 6, 8, 12, 16]),
        "memory_total": rng.choice([4096, 8192, 16384, 24576, 32768]),
        "memory_used": rng.choice([2048, 4096, 6144, 8192, 12288]),
        "mods": _pick_mods(rng),
        "warnings_bias": scenario_cfg.get("warnings_bias", 0.08),
        "safe_mode": scenario_cfg.get("safe_mode", False),
        "force_reason": picked_reason,
        "version_conflict_pair": conflict_pair,
    }
    
    # Update fuser context if active
    if fuser:
        fuser.context = context

    crash_inserted = False

    def _push_lines(lines: list[str]):
        nonlocal bytes_written, buffer_bytes, lines_written
        for line in lines:
            line_bytes = len(line.encode("utf-8"))
            buffer.append(line)
            buffer_bytes += line_bytes
            lines_written += 1
            if buffer_bytes >= buffer_limit:
                f.writelines(buffer)
                bytes_written += buffer_bytes
                buffer.clear()
                buffer_bytes = 0

    header_lines = [
        _format_log_line(ts, rng, f"Launching Minecraft {context['game_version']}"),
        _format_log_line(ts, rng, f"Java: {context['java_version']} ({context['java_vendor']})"),
        _format_log_line(ts, rng, f"OS: {context['os']}", logger_name="minecraft/Minecraft"),
        _format_log_line(ts, rng, f"Loading {context['loader']['name']} {context['loader_version']}", logger_name=context["loader"]["logger"]),
    ]

    header_lines.append(_format_log_line(ts, rng, "Mod list:\n", logger_name=context["loader"]["logger"]))
    for m in context["mods"]:
        header_lines.append(_format_log_line(ts, rng, f"\t{m['id']} {m['version']} ({m['name']})", logger_name=context["loader"]["logger"]))

    # 场景信号放在头部，避免截断读取丢失关键字
    for line in _scenario_signal_lines(rng, scenario, context):
        header_lines.append(_format_log_line(ts, rng, line, level="WARN", logger_name=context["loader"]["logger"]))

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        _push_lines(header_lines)
        while bytes_written < target_bytes:
            ts += timedelta(milliseconds=rng.randint(1, 60))
            progress = bytes_written / max(target_bytes, 1)
            if progress < 0.25:
                phase = "startup"
            elif progress < 0.55:
                phase = "loading"
            else:
                phase = "play"

            if not crash_inserted and progress > 0.75 and rng.random() < scenario_cfg.get("error_bias", 0.004):
                crash_inserted = True
                crash_intro = _format_log_line(ts, rng, "Encountered an unexpected exception", level="ERROR", logger_name="minecraft/Minecraft", thread="main")
                crash_saved = _format_log_line(ts, rng, "This crash report has been saved to: ./crash-reports/crash-2026-01-28_12.34.56-client.txt", level="ERROR", logger_name="minecraft/Minecraft", thread="main")
                _push_lines([crash_intro])
                _push_lines(_format_crash_report(ts, rng, context))
                _push_lines([crash_saved])
                continue

            message = _format_message(rng, phase, context, fuser, progress)
            if scenario_cfg.get("extra_lines") and rng.random() < 0.06:
                conflict_pair = context.get("version_conflict_pair")
                # Use a random mod from the current context for dependency errors to ensure variety
                dep_candidates = [m["id"] for m in context["mods"]]
                # Mix in some common libraries that might not be in the pack to simulate "missing lib"
                dep_candidates.extend(["geckolib", "architectury", "fabric-api", "cloth-config"])
                
                extra = rng.choice(scenario_cfg["extra_lines"]).format(
                    mod=rng.choice(context["mods"])["id"],
                    dep=rng.choice(dep_candidates),
                    mixin=rng.choice(MIXINS),
                    mc_version=context["game_version"],
                    ms=rng.randint(1, 5000),
                    count=rng.randint(1, 5000),
                    res=rng.choice(RESOURCES),
                    modjar_conflict1=conflict_pair[0] if conflict_pair else "unknown-1.jar",
                    modjar_conflict2=conflict_pair[1] if conflict_pair else "unknown-2.jar",
                )
                message = extra
            level = "WARN" if "failed" in message.lower() or "missing" in message.lower() else None
            line = _format_log_line(ts, rng, message, level=level)
            _push_lines([line])

        if buffer:
            f.writelines(buffer)
            bytes_written += buffer_bytes

    meta = {
        "scenario": scenario,
        "crash_inserted": crash_inserted,
        "mods": [m["id"] for m in context["mods"]],
        "loader": context["loader"]["name"],
        "game_version": context["game_version"],
        "capped_bytes": target_bytes,
    }
    return bytes_written, lines_written, meta


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def generate_batch(
    output_dir: str,
    target_bytes: int,
    seed: int | None,
    scenarios: list[str],
    count: int,
    report_path: str | None,
    progress_cb=None,
    cancel_cb=None,
    max_single_size: int | None = None,
) -> list[dict]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    rng = random.Random(seed)

    for i in range(count):
        if cancel_cb and cancel_cb():
            break
        
        # Handle "pipeline" or "all" keyword to rotate through all available scenarios
        if scenarios and (scenarios[0] == "pipeline" or scenarios[0] == "all"):
            # Exclude 'normal' and 'compound' from pure pipeline if desired, or keep all.
            # User wants: Memory (oom), Hardware (gl_error), Software (mixin/version/missing)
            # We define a fixed order for consistency
            fixed_order = ["oom", "gl_error", "missing_dependency", "mixin_conflict", "version_conflict", "compound", "normal"]
            scenario = fixed_order[i % len(fixed_order)]
        else:
            scenario = scenarios[i % len(scenarios)] if scenarios else "normal"

        log_seed = rng.randint(1, 1_000_000)
        file_name = f"generated_{scenario}_{i+1:03d}.log"
        output_path = out_dir / file_name
        if progress_cb:
            progress_cb("generate", i + 1, count, str(output_path), scenario)
        written, lines, meta = write_log(str(output_path), target_bytes, log_seed, scenario, max_single_size=max_single_size)
        summary.append({
            "file": str(output_path),
            "bytes": written,
            "lines": lines,
            "seed": log_seed,
            **meta,
        })

    if report_path:
        rpath = Path(report_path)
        rpath.parent.mkdir(parents=True, exist_ok=True)
        if rpath.suffix.lower() == ".json":
            rpath.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # CSV
            headers = ["file", "bytes", "lines", "seed", "scenario", "crash_inserted", "loader", "game_version", "mods"]
            rows = [headers]
            for item in summary:
                rows.append([
                    item.get("file"),
                    item.get("bytes"),
                    item.get("lines"),
                    item.get("seed"),
                    item.get("scenario"),
                    item.get("crash_inserted"),
                    item.get("loader"),
                    item.get("game_version"),
                    "|".join(item.get("mods", [])),
                ])
                rpath.write_text("\n".join(",".join(map(str, r)) for r in rows), encoding="utf-8")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="生成用于测试的 Minecraft 日志")
    parser.add_argument("--output", "-o", default="generated_latest.log", help="输出文件路径")
    parser.add_argument("--output-dir", default=None, help="批量输出目录（启用批量时生效）")
    parser.add_argument("--size", help="目标大小，如 10MB / 512KB / 2GB")
    parser.add_argument("--min-size", help="最小大小，如 1MB")
    parser.add_argument("--max-size", help="最大大小，如 5GB")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--scenario", default="normal", help="场景类型，支持逗号分隔或 'pipeline'：normal/oom/gl_error/mixin_conflict/pipeline")
    parser.add_argument("--count", type=int, default=1, help="批量生成数量")
    parser.add_argument("--report", default=None, help="生成报告路径（.json 或 .csv）")
    parser.add_argument("--config", default=None, help="配置文件（JSON），用于覆盖默认选项")
    parser.add_argument("--max-single-size", default="8MB", help="单文件大小上限，如 8MB")
    args = parser.parse_args()

    cfg = _load_config(args.config)
    if cfg:
        for k, v in cfg.items():
            if hasattr(args, k):
                setattr(args, k, v)

    target = choose_size(args)
    if target <= 0:
        raise SystemExit("目标大小必须大于 0")

    scenario_list = [s.strip() for s in str(args.scenario).split(",") if s.strip()]
    try:
        max_single = parse_size(str(args.max_single_size)) if args.max_single_size else DEFAULT_MAX_SINGLE_SIZE
    except Exception:
        max_single = DEFAULT_MAX_SINGLE_SIZE
    output_dir = args.output_dir

    if args.count and args.count > 1:
        out_dir = output_dir or os.path.dirname(os.path.abspath(args.output)) or "."
        generate_batch(out_dir, target, args.seed, scenario_list or ["normal"], args.count, args.report, max_single_size=max_single)
        print(f"已批量生成日志: {out_dir}")
        if args.report:
            print(f"已生成报告: {args.report}")
        return

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    written, lines, meta = write_log(output_path, target, args.seed, scenario_list[0] if scenario_list else "normal", max_single_size=max_single)
    print(f"已生成日志: {output_path}")
    print(f"目标大小: {target} bytes, 实际写入: {written} bytes, 行数: {lines}")
    if args.report:
        generate_batch(os.path.dirname(output_path) or ".", target, args.seed, [meta["scenario"]], 1, args.report)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Aborted] User cancelled operation.")
    except Exception as e:
        print(f"\n[Fatal Error] {e}")
