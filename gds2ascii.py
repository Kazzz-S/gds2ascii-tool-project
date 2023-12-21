#!/usr/bin/env python3
# -*- coding: utf-8 -*-

######################################################################
#                                                                    #
#  Author: Michael Duh                                               #
#  Date: 25 Jan 2017                                                 #
#                                                                    #
#  This is a software to convert GDSii file to ASCii format          #
#  To use this software please put your .gds file in the same        #
#  folder. Output file will generate as JSON file.                   #
#                                                                    #
######################################################################

import sys
import struct
import json


# Reading Hex stream.
#
# input  : Hex format from raw file
# return : (list) [ record length, [record type, data type], [data1, data2, ...] ]
def readStream(stream):
    try:
        rec_data = []
        rec_size = struct.unpack('>h', stream.read(2))[0]
        stream.seek(0, 1)
        rec_type = struct.unpack('>b', stream.read(1))[0]
        stream.seek(0, 1)
        dat_type = struct.unpack('>b', stream.read(1))[0]
        stream.seek(0, 1)
        dat_size = {0x00: 1, 0x01: 1, 0x02: 2, 0x03: 4, 0x04: 4, 0x05: 8, 0x06: 1}
        for i in list(range(0, (rec_size-4)//dat_size[dat_type])):
            rec_data.append( stream.read(dat_size[dat_type]) )
            stream.seek(0, 1)
        return [rec_size, [rec_type, dat_type], rec_data]

    except:
        return -1

#--------------------------------------------------------------------------------------------------
# GDSII format
#
#   Ref. https://boolean.klaasholwerda.nl/interface/bnf/gdsformat.html
#
#     Eight-Byte Real
#
#     8-byte real = 4-word floating point representation
#     For all non-zero values:
#
#     A floating point number has three parts: the sign, the exponent, and the mantissa.
#     The value of a floating point number is defined as:
#     (Mantissa) x (16 raised to the true value of the exponent field).
#     The exponent field (bits 1-7) is in Excess-64 representation.
#     The 7-bit field shows a number that is 64 greater than the actual exponent.
#     The mantissa is always a positive fraction >=1/16 and <1. For a 4-byte real, the mantissa
#     is bits 8-31. For an 8-byte real, the mantissa is bits 8-63.
#     The binary point is just to the left of bit 8.
#     Bit 8 represents the value 1/2, bit 9 represents 1/4, etc.
#     In order to keep the mantissa in the range of 1/16 to 1, the results of floating point
#     arithmetic are normalized. Normalization is a process where by the mantissa is shifted
#     left one hex digit at a time until its left FOUR bits represent a non-zero quantity.
#     For every hex digit shifted, the exponent is decreased by one. Since the mantissa is shifted
#     four bits at a time, it is possible for the left three bits of the normalized mantissa to be zero.
#     A zero value, also called true zero, is represented by a number with all bits zero.
#
#     The following are representations of 4-byte and 8-byte reals, where S is the sign,
#     E is the exponent, and M is the magnitude. Examples of 4-byte reals are included in the
#     following pages, but 4-byte reals are not used currently.
#     The representation of the negative values of real numbers is exactly the same as the positive,
#     except that the highest order bit is 1, not 0. In the eight-byte real representation,
#     the first four bytes are exactly the same as in the four-byte real representation.
#     The last four bytes contain additional binary places for more resolution.
#
#     4-byte real:
#       SEEEEEEE MMMMMMMM MMMMMMMM MMMMMMMM
#
#     8-byte real:
#       SEEEEEEE MMMMMMMM MMMMMMMM MMMMMMMM MMMMMMMM MMMMMMMM MMMMMMMM MMMMMMMM
#       00000000 00111111 11112222 22222233 33333333 44444444 44555555 55566666
#       01234567 89012345 67890123 45678901 23456789 01234567 89012345 67890123
#--------------------------------------------------------------------------------------------------

# Convert an IBM 370 representation of floating-point number to an IEEE 754 format
#
# input  : an IBM 370 representation of floating-point number as an 8-byte array in big-endian order
# return : the double precision floating point number in the IEEE 754 format
def ibm370_to_ieee754( ibm_bytes, debug=False ):
    import math

    if debug:
        hex_string = ' '.join(['{:02x}'.format(b) for b in ibm_bytes])
        print( "Input IBM 370 floating-point number (hex) = %s" % hex_string )
        # 3e 41 89 37 4b c6 a7 f0  ==> 0.001
        # 39 44 b8 2f a0 9b 5a 54  ==> 1e-09

    # [1] Get the leftmost bit of the first byte that defines the sign.
    if ibm_bytes[0] & 0x80:
        sign = -1.0
    else:
        sign = +1.0

    # [2] The remaining 7 bits of the first byte form the base-16 exponent offset by +64.
    #     Note that 16**n == (2**4)**n == 2**(4*n).
    #                   ^                     ^^^
    exponent2 = int( 4 * ((ibm_bytes[0] & 0x7f) - 64) )

    # [3] The remaining 7 bytes form the mantissa in big-endian order, which is a base-16 float.
    mantissa = 0
    divisor  = 256.0
    for i in range(1, 8):
        mantissa += ibm_bytes[i] / divisor
        divisor  *= 256.0

    # [4] Compute the double value in the IEEE 754 format
    ieee754_value = sign * math.ldexp( mantissa, exponent2 )
    if debug:
        print( "    ==> Converted double value in the IEEE 754 format = %s" % ieee754_value )
    return ieee754_value

# Reading Hex stream.
#
# input  : (list) [ record length, [record type, data type], [data1, data2, ...] ]
# return : (string) record name
def appendName(record):
    name_list = {0x00 : 'HEADER',
                0x01 : 'BGNLIB',
                0x02 : 'LIBNAME',
                0x03 : 'UNITS',
                0x04 : 'ENDLIB',
                0x05 : 'BGNSTR',
                0x06 : 'STRNAME',
                0x07 : 'ENDSTR',
                0x08 : 'BONDARY',
                0x09 : 'PATH',
                0x0A : 'SERF',
                0x0B : 'AREF',
                0x0C : 'TEXT',
                0x0D : 'LAYER',
                0x0E : 'DATATYPE',
                0x0F : 'WIDTH',
                0x10 : 'XY',
                0x11 : 'ENDEL',
                0x12 : 'SNAME',
                0x13 : 'COLROW',
                0x15 : 'NODE',
                0x16 : 'TEXTTYPE',
                0x17 : 'PRESENTATION',
                0x19 : 'STRING',
                0x1A : 'STRANS',
                0x1B : 'MAG',
                0x1C : 'ANGLE',
                0x1F : 'REFLIBS',
                0x20 : 'FONTS',
                0x21 : 'PATHTYPE',
                0x22 : 'GENERATIONS',
                0x23 : 'ATTRATABLE',
                0x26 : 'ELFLAGS',
                0x2A : 'NODETYPE',
                0x2B : 'PROPATTR',
                0x2C : 'PROPVALUE',
                0x2D : 'BOX',
                0x2E : 'BOXTYPE',
                0x2F : 'PLEX',
                0x32 : 'TAPENUM',
                0x33 : 'TAPECODE',
                0x36 : 'FORMAT',
                0x37 : 'MASK',
                0x38 : 'ENDMASKS'
                }
    return name_list[record[1][0]]

# Extracting Hex Data to readable ASCii
#
# input  : (list) [ record length, [record type, data type], [data1, data2, ...] ]
# return : (list) [ASCii data, ASCii data, ... ]
def extractData(record):
    data = []
    if record[1][1] == 0x00:
        return data

    elif record[1][1] == 0x01:
        return data

    elif record[1][1] == 0x02:
        for i in list(range(0, (record[0]-4)//2)):
            data.append( struct.unpack('>h', record[2][i])[0] )
        return data

    elif record[1][1] == 0x03:
        for i in list(range(0, (record[0]-4)//4)):
            data.append( struct.unpack('>l', record[2][i])[0] )
        return data

    elif record[1][1] == 0x04:
        for i in list(range(0, (record[0]-4)//4)):
            data.append( struct.unpack('>f', record[2][i])[0] )
        return data

    elif record[1][1] == 0x05:
        """
        for i in list(range(0, (record[0]-4)//8)):
            data.append( struct.unpack('>d', record[2][i])[0] )
        return data
        """

        # The 8-byte array is for the 'UNITS' record, which is a floating point number in IBM 370 representation.
        for i in list(range(0, (record[0]-4)//8)):
            double8bytes = record[2][i]
            ieee754FP = ibm370_to_ieee754( double8bytes, debug=False )
            data.append(ieee754FP)
        return data
    else:
        for i in list(range(0, (record[0]-4))):
            data.append( struct.unpack('>c', record[2][i])[0].decode("utf-8") )
        return data

# Main
# Command argument 1 : input .gds file path (mandatory)
# Command argument 2 : output .json file path (optional)
def main():
    if len(sys.argv) < 2 or sys.argv[1] == "-h":
        print( "Usage:" )
        print( "  $ gds2ascii.py <input.gds> [output.json]" )
        print( "" )
        sys.exit(0)
    inputFile = sys.argv[1]
    if len(sys.argv) == 3:
        outputFile = sys.argv[2]
    else:
        outputFile = None
    asciiOut = []

    with open(inputFile, mode='rb') as ifile:
        while True:
            record = readStream(ifile)
            data = extractData(record)
            name = appendName(record)
            asciiOut.append([name, data])
            print([name, data])
            if record[1][0] == 0x04:
                break

        if not outputFile == None:
            with open(outputFile, 'w') as ofile:
                json.dump(asciiOut, ofile, indent=4)


if __name__ == '__main__':
    main()
