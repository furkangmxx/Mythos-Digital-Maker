"""
MythosCards Exporter - Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path

# README dosyasını oku
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8') if (this_directory / "README.md").exists() else ""

# Versiyon bilgisini src/version.py'dan al
version_file = this_directory / "src" / "version.py"
version_dict = {}
if version_file.exists():
    exec(version_file.read_text(encoding='utf-8'), version_dict)
    version = version_dict.get('PROGRAM_VERSION', '1.0.0')
else:
    version = '1.0.0'

# Gereksinimler
install_requires = [
    'pandas>=1.3.0',
    'openpyxl>=3.0.0',
    'xlsxwriter>=3.0.0',
    'click>=8.0.0',
    'python-dateutil>=2.8.0',
    'platformdirs>=2.0.0',
    'pytz>=2021.1',
]

# Opsiyonel gereksinimler
extras_require = {
    'icu': ['PyICU>=2.8'],
    'dev': [
        'pytest>=6.0.0',
        'pytest-cov>=2.12.0',
        'black>=21.0.0',
        'flake8>=3.9.0',
        'mypy>=0.910',
    ],
    'build': [
        'pyinstaller>=4.5.0',
        'auto-py-to-exe>=2.20.0',
    ],
}

# Tüm opsiyonel gereksinimler
extras_require['all'] = sum(extras_require.values(), [])

setup(
    name="mythos-cards-exporter",
    version=version,
    description="MythosCards Checklist to Card List Exporter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Furkan Gümüş",
    author_email="furkan@mythoscards.com",
    url="https://github.com/mythoscards/exporter",
    
    # Paketler
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    
    # Python versiyonu
    python_requires=">=3.8",
    
    # Gereksinimler
    install_requires=install_requires,
    extras_require=extras_require,
    
    # Entry points
    entry_points={
        'console_scripts': [
            'cards-export=main:cli',
            'mythoscards=main:main',
            'mythoscards-gui=main:launch_gui',
        ],
    },
    
    # Sınıflandırma
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Spreadsheet",
        "Topic :: Utilities",
    ],
    
    # Dosya dahil etme
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.md", "*.yml", "*.yaml"],
    },
    
    # Zip dosyası olarak kurulum yapma
    zip_safe=False,
    
    # Test
    test_suite="tests",
    
    # Keywords
    keywords="excel, checklist, cards, export, turkish, mythoscards",
    
    # Proje URL'leri
    project_urls={
        "Bug Reports": "https://github.com/mythoscards/exporter/issues",
        "Source": "https://github.com/mythoscards/exporter",
        "Documentation": "https://github.com/mythoscards/exporter/wiki",
    },
)