from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="classmonitor",
    version="1.0.0",
    author="ClassMonitor Team",
    description="A comprehensive monitoring software with video recording, time overlay, and announcement features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/classmonitor",
    py_modules=["monitoring_app"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video :: Capture",
    ],
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.8.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
        "PyQt5>=5.15.0",
        "PyQt-Fluent-Widgets>=1.5.0",
    ],
    entry_points={
        "console_scripts": [
            "classmonitor=monitoring_app:main",
        ],
    },
)
