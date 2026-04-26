import re
import os
def get_basic_info(text):
    mc = re.search(r"Minecraft Version: (.*)", text)
    mc_ver = mc.group(1) if mc else "Unknown"
    return mc_ver

print(get_basic_info("Minecraft Version: 1.16.5"))
