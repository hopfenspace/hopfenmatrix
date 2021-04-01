# Hopfenmatrix

This project tries to simplify the excellent `matrix-nio` library.

## Installation

This project is available via the pypi package manager. It depends on the E2E version of `matrix-nio`, `matrix-nio[e2e]`.
Because of this, the installation depends on the `libolm3` library.

### Debian

#### Debian 10 and below
The `libolm3` library is not available in Debian 10 and below.
It has to be installed from the `buster-backports` repository.
```
echo "deb http://ftp.debian.org/debian buster-backports main contrib" >> /etc/apt/sources.list
apt update
apt install python3 python3-pip
apt install -t buster-backports libolm-dev
python3 -m pip install -U hopfenmatrix
```

#### Debian Bullseye
```
apt update
apt install python3 python3-pip libolm-dev
python3 -m pip install -U hopfenmatrix
```

### Arch
```
pacman -S libolm python python-pip gcc
python -m pip install -U hopfenmatrix
```

### Fedora 30 and above
```
dnf install python3-pip python3-devel libolm libolm-devel gcc
python3 -m pip install -U hopfenmatrix
```
