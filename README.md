# VerilogHex

A Python package for reading and writing Verilog hex files.

This package supports the Verilog hex format that is used to initialise simulation memories using the Verilog `$readmemh` system task.  This format is supported by `srec_cat` which provides comprehensive conversion from/to multiple common binary formats.  Details on the format can be found here: https://linux.die.net/man/5/srec_vmem

The motivation for this package was to provide a pure Python implementation to convert between VMEM and a bytearray for sending and receiving memory data over a socket.

## Installation
```
pip install veriloghex
```

## Usage

```python
from pathlib import Path
from veriloghex import VerilogHex

# Open a hex file and parse the contents to a bytearray
vmem = VerilogHex(filename_or_io_obj)
bytes = vmem.tobytes()

# Write out a VMEM file using any byte width
with Path('mem.8.vmem').open('w') as f:
	f.write(vmem.tovmem(width_bytes=1)
    
with Path('mem.16.vmem').open('w') as f:
	f.write(vmem.tovmem(width_bytes=2)
    
with Path('mem.32.vmem').open('w') as f:
	f.write(vmem.tovmem(width_bytes=4)

# Initialise from a list of bytes and write out as VMEM
vmem = VerilogHex([0xde, 0xad, 0xbe, 0xef])
print(vmem.tovmem())

```

## Status

This package is in development and may change considerably during that time.  The API takes inspiration from `intelhex` and `bincopy`, both of which perform similar tasks but don't support the Verilog hex format.