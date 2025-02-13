from setuptools import setup, find_packages

setup(
    name="led_grid",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "rpi_ws281x>=5.0.0",
        "paho-mqtt==1.6.1",
        "numpy==1.24.3",
    ],
)
