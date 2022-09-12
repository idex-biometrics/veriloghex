# Copyright IDEX Biometrics
# Licensed under the MIT License, see LICENSE
# SPDX-License-Identifier: MIT

import re, logging, itertools
from typing import (Sequence, Union, Optional)
from pathlib import Path

LOG = logging.getLogger(__file__)

class VerilogHexSegmentMergeError(Exception):
    pass

class VerilogHexSegment:
    """ Represents a segment of data at a specific address.

    """
    def __init__(self, 
                 bytes: Optional[Union[Sequence[int], str]] = None, 
                 offset: Optional[Union[int, str]] = 0
                 ) -> None:
        """ Initialize a new segment.

        Arg: offset  A hex address offset for the word (RAM row index not byte address!)
        Arg: bytes   An empty string or a whitespace separated list of words

        """
        self._bytes = []
        self._offset = offset if isinstance(offset, int) else int(offset, 16)
        self._width_bytes = None

        if bytes:
            self.append(bytes)

    @property
    def size(self) -> int:
        """ Returns the size of the segment in bytes. """
        return len(self._bytes)

    @property
    def start(self) -> int:
        """ Returns the start address of the segment. """
        try:
            return self._offset * self._width_bytes
        except TypeError:
            return self._offset

    @property
    def end(self) -> int:
        """ Returns the end address of the segment (exclusive). """
        return self.start + self.size

    @property
    def bytes(self) -> list:
        return self._bytes

    @property
    def includes(self, address: int) -> bool:
        """ Returns true if the address sits within the segment. """
        return address >= self.start and address < self.end

    def __getitem__(self, address: int) -> int:
        return self._bytes[address - self.start]

    def append(self, bytes: Union[Sequence[int], str]) -> None:
        """ This method appends a list of bytes to the segment.

        The argument |bytes| can either be a sequence of integers representing each byte
        or a string in Verilog Hex format.  For the latter, it is expected that the string
        contains white space separated hex values in any byte width, e.g.:

            01 23 45 67 89 AB CD EF
            67452301 EFCDAB89

        """
        if isinstance(bytes, list):
            self._bytes.extend(bytes)

        elif isinstance(bytes, str):
            # ignore any blank lines
            if re.match(r"^\s*$", bytes): 
                return

            # strip off any leading/trailing white space
            bytes = bytes.rstrip().lstrip()

            # iterate over each word in the string and extend the byte array
            for word in bytes.split(' '):
                # split the string into a list of bytes
                bytes = re.findall(r"[0-9A-Fa-f]{2}", word)
                # reverse the list so that we are in little endian
                bytes.reverse()
                # append to the main array
                self._bytes.extend([int(b,16) for b in bytes])
                # update the word width if it hasn't already been initialized
                if self._width_bytes is None:
                    self._width_bytes = len(bytes)
        else:
            raise ValueError(f"unsupported type passed to append: {type(bytes)}")

    def merge(self, segment) -> None:
        """ Tries to merge two segments.
        
        Two segments, a and b, can be merged if they occupy a contiguous region, i.e. (a.end == b.start).

        """
        if self.end != segment.start:
            raise VerilogHexSegmentMergeError()
        self.append(segment.bytes)

    def tobytes(self, width_bytes: int = 1, padding: int = 0xff) -> bytearray:    
        """Returns a bytearray object that has been padded to the required alignment. """
        # Check alignment and pad where necessary
        bytes = [padding] * (self.start % width_bytes)
        # Append the list with the data
        bytes.extend(self._bytes)
        # Pad the end of the array if necessary
        if len(bytes) % width_bytes:
            bytes.extend([padding] * (width_bytes - (len(bytes) % width_bytes)))
        return bytearray(bytes)

    def tovmem(self, width_bytes: int = 4, padding: int = 0xff) -> Sequence[str]:
        """Returns a list of strings in Verilog hex format. """
        vmem = []
        # Check alignment and pad where necessary
        padded_bytes = self.tobytes(width_bytes, padding)
        # Set the starting offset of the segment
        offset = self.start // width_bytes
        # Iterate over slices of |width_bytes| bytes
        for bytes in zip(*(iter(padded_bytes),) * width_bytes):
            # Convert the ints in to LE hex strings
            word = ''.join(['{:02x}'.format(b) for b in reversed(bytes)])
            # Concatenat the word with its offset
            vmem.append(f"@{offset:08x} {word}")
            # Increment the RAM offset
            offset += 1
        return vmem

    def __iter__(self):
        """ Allows unpacking """
        yield self.start
        yield self.tobytes()


class VerilogHex:
    """ A class for reading and writing Verilog hex files.

    This class has methods for loading from and dumping to hex files in a format
    supported by the Verilog $readmemh function.

    """
    def __init__(self, 
                 source: Optional[Union[Sequence[int], str]] = None, 
                 offset: Optional[int] = 0
                 ) -> None:
        """If source is defined, then we populate the segments. 
        


        """
        self._segments = []
        self.padding = 0xff

        if source is not None:
            try:
                self.fromvmem(source)
            except Exception as e:
                try: 
                    self.frombytes(source, offset)
                except Exception as e:
                    raise e

    @property
    def size(self):
        return sum([seg.size for seg in self._segments])

    @property
    def num_segments(self):
        return len(self._segments)

    @property
    def segments(self):
        return self._segments

    def frombytes(self, bytes: Union[Sequence[int], bytearray], offset: Optional[int] = 0) -> None:
        """Load from a sequence of bytes. 
        
        The sequence can be a list of ints or a bytearray object.  An optional offset allows sparse 
        segements to be constructed.

        """
        self._segments.append(VerilogHexSegment(list(bytes), offset))

    def fromvmem(self, fobj):
        """Load from a Verilog hex file.
        
        This method parses a Verilog Hex file and extracts all segments.
        
        """
        try:
            line = fobj.readline()
        except AttributeError:
            fobj = Path(fobj).open()
            line = fobj.readline()        

        while line:
            if re.search(r"^\s*/\*", line):
                line = fobj.readline()
                continue

            # Look for offset markers of the form @hexoffset
            match = re.match(r"""\s*
                                 @([0-9A-Fa-f]+)
                                 \s*
                                 (.*?)
                                 \n
                              """, line, re.X )
            if match:
                (offset,bytes) = match.groups()
                segment = VerilogHexSegment(bytes,offset)
                LOG.debug(f"offset={offset}, bytes={bytes}")

                try:
                    self._segments[-1].merge(segment)
                except (IndexError, VerilogHexSegmentMergeError):
                    self._segments.append(segment)

            # Look for any more bytes in the segment
            match = re.match(r"""([A-Fa-f0-9\s]+)
                                 \n
                              """, line, re.X )
            if match:
                # Append more bytes to the segment
                self._segments[-1].append(match.group(1))

            # Continue onto the next line
            line = fobj.readline()

        if segment is None:
            raise RuntimeError("segment cannot be None")

        fobj.close()

    def tovmem(self, width_bytes: int = 4, padding: int = 0xff) -> str:
        vmem = []
        for segment in self._segments:
            vmem.extend(segment.tovmem(width_bytes, padding))
        return '\n'.join(vmem)

    def tobytes(self, width_bytes: int = 4, padding: int = 0xff) -> bytearray:
        bytes = bytearray()
        for segment in self._segments:
            bytes.extend(segment.tobytes(width_bytes, padding))
        return bytes

    def dump(self, file):
        print(self.tovmem())

    def __getitem__(self, address: int) -> int:
        assert address >= 0
        for segment in self._segments:
            try:
                return segment[address]
            except IndexError:
                continue
        return self.padding

    def __iter__(self):
        for segment in self._segments:
            yield segment
        
