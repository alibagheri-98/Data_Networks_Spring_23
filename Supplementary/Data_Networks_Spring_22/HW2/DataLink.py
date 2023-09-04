from Layers import Node

from collections import deque

# Abstract classes for DL
class DataLink:
    def __init__(self, timeout=0, N_buffer=1, N_window=1) -> None:
        self.Node = None
        self.spare_time = 0  # minimum next available timestamp that this Node can transmit new packet over channel.
        # Buffering
        self.N_buffer = N_buffer  # Based on your algorithm
        self.N_window = N_window  # Based on your algorithm
        self.buffer_packet = deque()  # Empty queue
        self.buffer_seq_nr = deque(range(self.N_buffer))  # or reversed??
        # Timeout
        self.timeout = timeout
        # Set header for ACK, NAK
        self.ACK_header = 0xAA
        self.NAK_header = 0x55
    
    def assign_Node(self, Node:Node):
        """Assign this PHY to `Node` that contains this PHY."""
        self.Node = Node
    
    def get_sim_time(self):
        """Get simulator time. Actually fetch time from simulator and returns to ites elements like DL."""
        return self.simulator.get_sim_time()
    
    def start_transmit(self, IDU:dict):
        """Fullfil Tx buffer from L3 + Start transmitting packet + Set timer."""
        self.full_fil_buffer()  # Ensure buffer is full.
        pass  # Based on your algorithm: OVERRIDE THIS FUNCTION IN CHILDREN
        # For example: Not True
        self.Node.add_event((1, 'DL timeout', 3))  # set new timer

    def full_fil_buffer(self):
        """Fullfil transmitting buffer."""
        fullfil_req = {'SDU': 'push'}
        while len(self.buffer_packet) < self.N_buffer:
            self.Node.from_L2_to_L3(fullfil_req)
    
    def push_buffer(self, PDU):
        """Push new packet to buffer. L3 calls this function."""
        assert len(self.buffer_packet) < self.N_buffer, "L2 Buffer is full!"
        self.buffer_packet.appendleft(PDU)  # add PDU to buffer
    
    def pop_buffer(self):
        """Pop packet from buffer. When this packet has transmitted and ACKed  we must pop this packet and replace with new packet.
            Also rotate seq_nr for true indexing."""
        self.buffer_packet.pop()
        self.buffer_seq_nr.rotate(1)

    def timeout_func(self, seq_nr:int):
        """`seq_nr` packet timer timed out!"""
        pass  # Based on your algorithm: OVERRIDE THIS FUNCTION IN CHILDREN

    def call_from_L3(self, IDU:dict):
        """L3 calls L2. We assume that this happens only for Tx and L3 can only push new packet."""
        if IDU['SDU'] == None:
            self.push_buffer(IDU['PDU'])
        else:
            raise ValueError(f"Unknown IDU for L2 {IDU}")
    
    def call_from_L1(self, IDU):
        """PHY calls L2: receiving ACK, NAK or packets."""
        pass  # Based on your algorithm: OVERRIDE THIS FUNCTION IN CHILDREN

    def event_run(self, event):
        """Run nearest event. In this case PHY receives packet from channel."""
        # check for event type. Switch case!
        if event[1] == 'DL timeout':
            self.timeout_func(event[2])  # seq_nr
        elif event[1] == 'DL start':
            self.start_transmit(event[2])  # IDU
        else:
            raise ValueError(f"Unknown event for DL {event[1]}")


####################
# Stop and Wait
class Stop_Wait_Tx(DataLink):
    def __init__(self, timeout) -> None:
        super().__init__(timeout)
        self.N_buffer = 1
        self.next_frame_to_send = 0
        self.spare_time = 0
    
    def start_transmit(self, *arg):
        """Fullfil Tx buffer from L3 + Start transmitting packet + Set timer."""
        self.full_fil_buffer()  # Ensure buffer is full.
        PDU = self.buffer_packet[-1]  # -1,0???????????????????????????????????????????????????????????????
        # Add HEADER (tail)
        PDU['frame_size'] += 1
        PDU['frame'] = PDU['frame']<<1 | self.next_frame_to_send
        IDU = {'PDU':PDU, 'SDU':None}
        # Set transmitting event
        self.spare_time = self.Node.from_L2_to_L1(IDU)
        # Set timer event
        event = (self.spare_time+self.timeout, 'DL timeout', self.next_frame_to_send)
        self.Node.add_event(event)


    def call_from_L1(self, IDU):
        """Get ACK from Rx. Progress packet + Clear timer + Clear packet buffer + Set new transmit event"""
        assert (IDU['PDU']['frame']>>1) == (self.ACK_header), f"Unknown Rx header (Not ACK): {bin(IDU['PDU']['frame'])}"
        acked_frame = IDU['PDU']['frame'] & 0x1
        if acked_frame == self.next_frame_to_send:
            # Inc frame
            self.next_frame_to_send = 1 - self.next_frame_to_send
            # Clear timer
            eve_que= self.Node.ret_event_queue()
            # ind = list(map(lambda el:el[0], filter(lambda el:el[1]=='DL timeout', enumerate(eve_que))))[0]
            eve_que = list(filter(lambda el:el[1]!='DL timeout', eve_que))  # notch filter timeouts!
            self.Node.set_event_queue(eve_que)  # set filterd queue!
            # Clear sending packet buffer to inject new packet from L3
            self.pop_buffer()
            # Add new transmit
            event = (self.Node.get_sim_time(), 'DL start', None)
            self.Node.add_event(event)
    
    def timeout_func(self, seq_nr: int):
        """Retransmit packet"""
        # Retransmit
        event = (self.Node.get_sim_time(), 'DL start', None)
        self.Node.add_event(event)


class Stop_Wait_Rx(DataLink):
    def __init__(self) -> None:
        super().__init__()
        self.N_buffer = 1
        self.frame_expexcted = 0
        self.spare_time = 0
    
    def start_transmit(self, IDU: dict):
        self.spare_time = self.Node.from_L2_to_L1(IDU)

    def call_from_L1(self, IDU):
        """Check seq_nr of received frame + send ACK"""
        seq_nr = IDU['PDU']['frame'] & 0x1
        if seq_nr == self.frame_expexcted:
            IDU['PDU']['frame'] >>= 1; IDU['PDU']['frame_size'] -= 1  # Extract frame
            self.Node.from_L2_to_L3(IDU)  # Pass to L3
            self.frame_expexcted = 1 - self.frame_expexcted  # Next state
        IDU = {'PDU':{'frame':self.ACK_header<<1 | (1-self.frame_expexcted), 'frame_size':8+1}, 'SDU':None}  # ACK frame
        event = (self.Node.get_sim_time(), 'DL start', IDU)
        self.Node.add_event(event)  # transmit ACK

####################
# Go Back N
class Go_BackN_Tx(DataLink):
    def __init__(self, timeout) -> None:
        super().__init__(timeout)
    
    def start_transmit(self, IDU: dict):
        pass  # Override this

    def call_from_L1(self, IDU):
        pass  # Override this
    
    def timeout_func(self, seq_nr: int):
        pass  # Override this


class Go_BackN_Rx(DataLink):
    def __init__(self, timeout) -> None:
        super().__init__(timeout)
    
    def start_transmit(self, IDU: dict):
        pass  # Override this

    def call_from_L1(self, IDU):
        pass  # Override this

####################
# Selective Repeat
class Selective_Repeat_Tx(DataLink):
    def __init__(self, timeout) -> None:
        super().__init__(timeout)
    
    def start_transmit(self, IDU: dict):
        pass  # Override this

    def call_from_L1(self, IDU):
        pass  # Override this
    
    def timeout_func(self, seq_nr: int):
        pass  # Override this


class Selective_Repeat_Rx(DataLink):
    def __init__(self, timeout) -> None:
        super().__init__(timeout)
    
    def start_transmit(self, IDU: dict):
        pass  # Override this

    def call_from_L1(self, IDU):
        pass  # Override this
