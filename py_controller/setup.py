from setuptools import setup, find_packages

with open("py_controller/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("py_controller/requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if not line.startswith("#")]

setup(
    name="legrid-controller",
    version="1.0.0",
    author="Legrid Team",
    description="LED Grid Controller for Raspberry Pi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/legrid-controller",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "legrid-controller=py_controller.main:main",
        ],
    },
)
