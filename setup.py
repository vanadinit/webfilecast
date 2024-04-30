from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='webfilecast',
    version='1.0.0',
    description='Webfrontend to cast local videos to your chromecast',
    keywords=['Chromecast', 'video', 'local', 'movie', 'terminalcast'],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/vanadinit/webfilecast',
    author='Johannes Paul',
    author_email='vanadinit@quantentunnel.de',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'terminalcast @ git+https://github.com/vanadinit/terminalcast@main',
        'Flask',
        'redis',
        'flask_socketio',
        'filetype>=1.0.0',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
