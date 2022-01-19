import setuptools

with open("README.md") as f:
    long_description = f.read()

setuptools.setup(
    name="hopfenmatrix",
    version="0.4.7",
    author="Wolfgang Fischer, Niklas Pfister",
    author_email="kontakt@omikron.dev",
    description="A library to make matrix-nio easier",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hopfenspace/hopfenmatrix/",
    packages=setuptools.find_packages(include=("hopfenmatrix",)),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "matrix-nio[e2e]~=0.18.7",
        "Pillow~=9.0.0",
        "python-magic~=0.4.18",
        "aiofiles~=0.6.0",
        "mutagen~=1.45.1",
        "aiohttp~=3.8.1"
    ]
)
