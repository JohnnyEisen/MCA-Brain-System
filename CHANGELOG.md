# Changelog

## v1.1.0 - 2026-02-06

### Refactoring & Professionalization
* **Core Terminology Update**: Renamed "AI Engine" to "Diagnostics Lab" and "Analysis Engine" for clarity and professionalism.
* **Build System Optimization**: Improved `package_release.py` with strict type hinting and robust error handling.
* **Large File Support**: Implemented deterministic file splitting for GitHub release artifacts >2GB.
* **UI Improvements**: Standardized labels in `app.py` and `lab_mixins.py` to remove marketing jargon.
* **Environment Setup**: Refined batch scripts (`install_ai.bat`, `Start_Repair.bat`) for better user experience.

## v1.0.0 - 2026-02-05

### Features
* **Modular Architecture**: Core and external library separation.
* **Analysis Engine**: Optional semantic analysis support via PyTorch.
* **Automated Testing**: Log generation tools and unit tests.
* **Privacy Controls**: Build pipeline and `.gitignore` hardening.

### Notes
* Project evolved from internal v4.x prototypes.
