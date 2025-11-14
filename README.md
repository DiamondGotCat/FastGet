
<img width="1920" alt="fastget" src="https://github.com/user-attachments/assets/6a8dfeb7-7714-4bf5-a890-555a49436ef8" />

# FastGet
High-speed File Downloading Tool

## How
It's using Multiple Thread Download.

This is need Range-select feature, in Server-side.

## Requiments
- CPython 3.9+
- `uv` [PyPI↗︎](https://pypi.org/project/uv/) or `pip3` [PyPI↗︎](https://pypi.org/project/pip/) 
- `nercone-modern` [PyPI↗︎](https://pypi.org/project/nercone-modern/)
- `rich` [PyPI↗︎](https://pypi.org/project/rich/)
- `requests` [PyPI↗︎](https://pypi.org/project/requests/)

## Installation

### using uv (recommended)
```
uv tool install nercone-fastget
```

### using pip3

**System Python:**
```
pip3 install nercone-fastget --break-system-packages
```

**Venv Python:**
```
pip3 install nercone-fastget
```

## Update

### using uv (recommended)
```
uv tool install nercone-fastget --upgrade
```

### using pip3

**System Python:**
```
pip3 install nercone-fastget --upgrade --break-system-packages
```

**Venv Python:**
```
pip3 install nercone-fastget --upgrade
```

## Usage

### Show helps
```
fastget [-h] [--help]
```

```
nercone@demo ~> fastget -h
usage: FastGet [-h] [-o OUTPUT] [-t THREADS] url

High-speed File Downloading Tool

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
  -t THREADS, --threads THREADS
```

### Download with default number of threads
```
fastget <url>
```

```
nercone@demo ~> fastget https://download.fedoraproject.org/pub/fedora/linux/releases/43/Workstation/x86_64/iso/Fedora-Workstation-Live-43-1.6.x86_64.iso
Total file size: 2.74GB (2,742,190,080 B)
(---------------------) DL All -  7% ( 1552/20922) | No Message
(---------------------) DL #1 -  7% (  348/5231) | No Message
(---------------------) DL #2 - 12% (  637/5231) | No Message
(---------------------) DL #3 -  6% (  315/5231) | No Message
(---------------------) DL #4 -  5% (  252/5231) | No Message
```

### Download with custom number of threads
```
fastget <url> [-t <number of threads>]
```

```
nercone@demo ~> fastget https://download.fedoraproject.org/pub/fedora/linux/releases/43/Workstation/x86_64/iso/Fedora-Workstation-Live-43-1.6.x86_64.iso -t 8
Total file size: 2.74GB (2,742,190,080 B)
(---------------------) DL All -  15% ( 3142/20922) | No Message
(---------------------) DL #1 -  19% ( 496/2616) | No Message
(---------------------) DL #2 -  12% ( 306/2616) | No Message
(---------------------) DL #3 -  21% ( 562/2616) | No Message
(---------------------) DL #4 -  14% ( 361/2616) | No Message
(---------------------) DL #5 -  20% ( 533/2616) | No Message
(---------------------) DL #6 -   9% ( 225/2616) | No Message
(---------------------) DL #7 -  14% ( 368/2616) | No Message
(---------------------) DL #8 -  11% ( 292/2616) | No Message
```

---

![PyPI - Version](https://img.shields.io/pypi/v/nercone-fastget)
