"""CPU functionality."""

import sys
import os
from datetime import datetime
import select
import tty
import termios


class NonBlockingConsole(object):

    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_data(self):
        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            return sys.stdin.read(1)
        return False


class CPU:
    """Main CPU class."""

    def __init__(self):
        """Construct a new CPU."""
        self.ram = [0] * 256
        self.reg = [f'{0:08b}'] * 8
        self.IS = 6
        self.IM = 5
        self.SP = 7
        self.KEY = 0xf4
        self.reg[self.SP] = 0xf4
        self.pc = 0x00
        self.fl = 0x00
        self.heap_height = 0
        self.arg_1 = 0xff
        self.arg_2 = 0xfe
        self.interrupts = True
        self.next_room = ''
        # Map functions. {is_alu_function: {sets_pc: {function_code: function}}}
        self.op_map = {1: {0: {0b0000: self.ADD,
                               0b1000: self.AND,
                               0b0111: self.CMP,
                               0b0110: self.DEC,
                               0b0011: self.DIV,
                               0b0101: self.INC,
                               0b0100: self.MOD,
                               0b0010: self.MUL,
                               0b1001: self.NOT,
                               0b1010: self.OR,
                               0b1100: self.SHL,
                               0b1101: self.SHR,
                               0b0001: self.SUB,
                               0b1011: self.XOR,
                               },
                           1: None},
                       0: {1: {0b0000: self.CALL,
                               0b0010: self.INT,
                               0b0011: self.IRET,
                               0b0101: self.JEQ,
                               0b1010: self.JGE,
                               0b0111: self.JGT,
                               0b1001: self.JLE,
                               0b1000: self.JLT,
                               0b0100: self.JMP,
                               0b0110: self.JNE,
                               0b0001: self.RET,
                               },
                           0: {0b0001: self.HLT,
                               0b0011: self.LD,
                               0b0010: self.LDI,
                               0b0000: self.NOP,
                               0b0110: self.POP,
                               0b1000: self.PRA,
                               0b0111: self.PRN,
                               0b0101: self.PUSH,
                               0b0100: self.ST,
                               }
                           }
                       }

    def load(self):
        """Load a program into memory."""
        args = sys.argv[1:]
        if args:
            file = os.path.join(args[0])
        else:
            file = 'clue.ls8'
        with open(file, 'r') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if line == '':
                    continue
                self.ram[self.heap_height] = f'{int(line, 2):08b}'
                self.heap_height += 1

    def first(self):
        """Get the value for the first active register."""
        return self.ram_read(self.arg_1)

    def second(self):
        """Get the value for the second active register."""
        return self.ram_read(self.arg_2)

    def PRN(self):
        """Print a number."""
        number = self.reg[int(self.first(), 2)]
        print(int(number, 2), end='', flush=True)
        return number

    def PRA(self):
        """Print a character."""
        address = self.reg[int(self.first(), 2)]
        character = chr(int(address, 2))
        print(f'{character}', end='', flush=True)
        return character

    def LDI(self):
        """Load immediate.

        Set a register value."""
        self.reg[int(self.first(), 2)] = self.second()

    def HLT(self):
        """Halt program."""
        pass

    def LD(self):
        """Load the value in memory at address in arg_2 into register in arg_1"""
        self.reg[int(self.first(), 2)] = self.ram[int(self.reg[int(self.second(), 2)], 2)]

    def PUSH(self):
        """Move pointer to next stack position and set value."""
        self.reg[self.SP] -= 1
        self.ram[self.reg[self.SP]] = self.reg[int(self.first(), 2)]

    def POP(self):
        """Get value from top of stack and move pointer."""
        self.reg[int(self.first(), 2)] = self.ram[self.reg[self.SP]]
        self.reg[self.SP] += 1

    def CALL(self):
        """Store location of pc before jumping to given address."""
        self.reg[self.SP] -= 1
        self.ram[self.reg[self.SP]] = self.pc + 1
        self.pc = int(self.reg[int(self.first(), 2)], 2)

    def RET(self):
        """Return from CALL."""
        self.pc = self.ram[self.reg[self.SP]]
        self.reg[self.SP] += 1

    def ST(self):
        """Store value of second register in memory at adress stored in first."""
        self.ram[int(self.reg[int(self.first(), 2)], 2)] = self.reg[int(self.second(), 2)]

    def INT(self):
        """Interrupt program and jump to interrupt handler.

        Reset IS bits.
        Halt interrupts.
        Store all but 8th register in stack, followed by fl and current pc.
        Move pc to interrupt handler address.
        """
        interrupt = int(self.first(), 2)
        # Clear the bit of interrupt being handled while preserving other
        # potentially set interrupts.
        self.reg[self.IS] = f'{int(self.reg[self.IS], 2) & 7 - ((0xff - interrupt) + 1):08b}'
        self.interrupts = False
        self.reg[self.SP] -= 1
        self.ram[self.reg[self.SP]] = self.pc
        self.reg[self.SP] -= 1
        self.ram[self.reg[self.SP]] = self.fl
        for i in range(7):
            self.reg[self.SP] -= 1
            self.ram[self.reg[self.SP]] = self.reg[i]
            self.reg[i] = '00000000'
        self.pc = int(self.ram[interrupt], 2)

    def IRET(self):
        """Return from interrupt.

        Restore all but 8th register from stack, followed by fl and pc.
        """
        for i in range(6, -1, -1):
            self.reg[i] = self.ram[self.reg[self.SP]]
            self.reg[self.SP] += 1
        self.fl = self.ram[self.reg[self.SP]]
        self.reg[self.SP] += 1
        self.pc = self.ram[self.reg[self.SP]]
        self.reg[self.SP] += 1
        self.interrupts = True

    def NOP(self):
        """No operation."""
        pass

    def JMP(self):
        """Jump."""
        self.pc = int(self.reg[int(self.first(), 2)], 2)

    def JEQ(self):
        """Jump if equal flag set."""
        if self.fl & 1:
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def JNE(self):
        """Jump if equal flag not set."""
        if not self.fl & 1:
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def JGT(self):
        """Jump if greater flag set."""
        if self.fl & (1 << 1):
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def JGE(self):
        """Jump if greater or equal flags set."""
        if self.fl & 1 or self.fl & (1 << 1):
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def JLT(self):
        """Jump if less flag set."""
        if self.fl & (1 << 2):
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def JLE(self):
        """Jump if less or equal flags set."""
        if self.fl & 1 or self.fl & (1 << 2):
            self.pc = int(self.reg[int(self.first(), 2)], 2)
        else:
            self.pc += 1

    def DEC(self):
        """Decrement"""
        deced = (int(self.reg[int(self.first(), 2)], 2) - 1) & 0xff
        self.reg[int(self.first(), 2)] = f'{deced:08b}'

    def INC(self):
        """Increment."""
        inced = (int(self.reg[int(self.first(), 2)], 2) + 1) & 0xff
        self.reg[int(self.first(), 2)] = f'{inced:08b}'

    def ADD(self):
        added = (int(self.reg[int(self.first(), 2)], 2) + int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{added:08b}'

    def SUB(self):
        """Subtract."""
        subbed = (int(self.reg[int(self.first(), 2)], 2) - int(self.reg[int(self.second(), 2)], 2)) * 0xff
        self.reg[int(self.first(), 2)] = f'{subbed:08b}'

    def MUL(self):
        """Multiply."""
        mulled = (int(self.reg[int(self.first(), 2)], 2) * int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{mulled:08b}'

    def DIV(self):
        """Integer divide."""
        dived = (int(self.reg[int(self.first(), 2)], 2) >> int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{dived:08b}'

    def MOD(self):
        """Modulus."""
        modded = (int(self.reg[int(self.first(), 2)], 2) % int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{modded:08b}'

    def AND(self):
        anded = (int(self.reg[int(self.first(), 2)], 2) & int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{anded:08b}'

    def OR(self):
        ored = (int(self.reg[int(self.first(), 2)], 2) | int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{ored:08b}'

    def XOR(self):
        xored = (int(self.reg[int(self.first(), 2)], 2) ^ int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{xored:08b}'

    def NOT(self):
        noted = int(~int(self.reg[int(self.first(), 2)], 2), 2) & 0xff
        self.reg[int(self.first(), 2)] = f'{noted:08b}'

    def SHL(self):
        """Shift left."""
        shled = (int(self.reg[int(self.first(), 2)], 2) << int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{shled:08b}'

    def SHR(self):
        """Shift right."""
        shred = (int(self.reg[int(self.first(), 2)], 2) >> int(self.reg[int(self.second(), 2)], 2)) & 0xff
        self.reg[int(self.first(), 2)] = f'{shred:08b}'

    def CMP(self):
        """Make a comparison and set the appropriate fl bit.

        FL bits: 00000LGE

        L Less-than: during a CMP, set to 1 if registerA is less than registerB,
          zero otherwise.
        G Greater-than: during a CMP, set to 1 if registerA is greater than
          registerB, zero otherwise.
        E Equal: during a CMP, set to 1 if registerA is equal to registerB, zero
          otherwise.
        """
        comp_a, comp_b = int(self.reg[int(self.first(), 2)], 2), int(self.reg[int(self.second(), 2)], 2)
        if comp_a == comp_b:
            self.fl = self.fl & 0b00000001
            self.fl = self.fl | 0b00000001
        if comp_a > comp_b:
            self.fl = self.fl & 0b00000010
            self.fl = self.fl | 0b00000010
        if comp_a < comp_b:
            self.fl = self.fl & 0b00000100
            self.fl = self.fl | 0b00000100

    def trace(self):
        """
        Handy function to print out the CPU state. You might want to call this
        from run() if you need help debugging.
        """

        print(f"TRACE: pc: {self.pc}, fl: {self.fl}, "
              f"ram: {self.ram_read(self.pc)}, "
              f"ram +: {self.ram_read(self.pc + 1)}, ram ++: {self.ram_read(self.pc + 2)},", end='')

        print('\nRegisters: ')
        for i in range(8):
            print(f"{self.reg[i]}", end=', ')
        print('\n\n')

    def ram_read(self, address):
        """Get the value stored in ram at address."""
        return self.ram[address]

    def ram_write(self, address, value):
        """Set the ram address to value."""
        self.ram[address] = value

    def run(self):
        """Run the CPU."""
        # Initialize timer and keyboard listener.
        then = datetime.now()
        with NonBlockingConsole() as nbc:

            # Continue until HLT reached.
            while True:
                args = 0xff  # ram[args] and ram[args + 1] hold values for registers arg_1 and arg_2.

                if self.interrupts:
                    # Check time interrupt.
                    now = datetime.now()
                    time = (now - then).seconds
                    if time >= 1:
                        then = datetime.now()
                        self.reg[self.IS] = '00000001'

                    # Check keyboard interrupt.
                    key = nbc.get_data()
                    if key:
                        if key == '\x1b':  # x1b is ESC
                            self.HLT()
                        self.ram_write(self.KEY, f'{ord(key):08b}')
                        self.reg[self.IS] = '00000010'

                    # Check if any interrupts have been triggered.
                    mask = int(self.reg[self.IM], 2) & int(self.reg[self.IS], 2)
                    for i in range(8):
                        interrupted = (mask >> i) & 1 == 1
                        if interrupted:
                            # Write the address of the triggered interrupt vector to ram[args].
                            self.ram_write(args, f'{(args - 7) + i:08b}')
                            self.INT()
                            break
                if isinstance(self.ram_read(self.pc), int):
                    return self.next_room
                # Retrieve and decode instruction from memory.
                instruction = int(self.ram_read(self.pc), 2)
                _bytes = instruction >> 6  # Number of places to advance pc.
                alu = (instruction & 0b00100000) >> 5  # 1 if an alu instruction.
                adv_pc = (instruction & 0b00010000) >> 4  # 1 if instruction advances pc.
                op_code = instruction & 0b00001111

                # Get required number of bytes from memory and load register vectors.
                for _ in range(_bytes):
                    self.pc += 1
                    self.ram_write(args, self.ram_read(self.pc))
                    args -= 1

                # Advance the pc if required.
                if not adv_pc:
                    self.pc += 1

                # Print debugging info.
                # self.trace()

                # Call the operation from the op_map.
                if op_code in self.op_map[alu][adv_pc]:
                    info = self.op_map[alu][adv_pc][op_code]()
                    if info:
                        self.next_room += info
                else:
                    print(f'Unknown instruction {op_code} at address {self.pc}')
                    # sys.exit(-1)
