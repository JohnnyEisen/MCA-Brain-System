from setuptools import setup, find_packages

# Read dependencies from requirements.txt
with open("requirements.txt", encoding="utf-8") as f:
    requirements = []
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            # Exclude index-url flags for setup.py standard compatibility
            if "--index-url" in line:
                line = line.split("--index-url")[0].strip()
            requirements.append(line)

setup(
    name="mca-brain-system",
    version="1.1.0",
    description="Minecraft Crash Analyzer with Diagnostics Lab",
    author="Brain AI Systems",
    packages=find_packages(include=[
        "mca_core", "mca_core.*", 
        "brain_system", "brain_system.*",
        "config", "config.*",
        "tools", "tools.*",
        "utils", "utils.*",
        "dlcs", "dlcs.*",
        "plugins", "plugins.*"
    ]),
    include_package_data=True,
    python_requires=">=3.10",
    url="https://github.com/JohnnyEisen/MCA-Brain-System",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "mca-gui=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
        "Topic :: Games/Entertainment :: Simulation",
    ],
)
