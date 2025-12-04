from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="classmonitor",
    version="1.0.0",
    author="ClassMonitor Team",
    author_email="support@classmonitor.com",
    description="A comprehensive monitoring software with video recording, time overlay, and announcement features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/classmonitor",
    py_modules=["monitoring_app", "windows_admin"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video :: Capture",
        "Topic :: Multimedia :: Video :: Display",
        "Environment :: X11 Applications :: Qt",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "tts": ["pyttsx3"],
        "dev": ["pytest", "black", "flake8"],
    },
    entry_points={
        "console_scripts": [
            "classmonitor=monitoring_app:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="monitoring video recording surveillance education classroom",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/classmonitor/issues",
        "Source": "https://github.com/yourusername/classmonitor",
        "Documentation": "https://github.com/yourusername/classmonitor/wiki",
    },
)
