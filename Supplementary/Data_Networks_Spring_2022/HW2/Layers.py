import numpy as np  # for source information bits generation.
from random import getrandbits, random  # for source information bits generation.
from functools import reduce  # for construct noise
#####
from CRC import CRC
from simulator import Simulator, Event_queues

# Service Access Point (SAP) data exchange format: PDU + SDU
## An example
IDU = {'PDU':{'frame':0x1241, 'frame_size': 32}, 'SDU':None}

# Communication Node
class Node:
    """A `Node` contains network layers stack (PHY, DL, NL) and acts like a user."""
    def __init__(self, simulator:Simulator) -> None:
        """`simulator`: Simulator engine that contains this Node."""
        self.L1, self.L2, self.L3 = None, None, None
        self.bind_sim(simulator)
        self.event_queue = Event_queues()
    
    def bind_sim(self, simulator:Simulator):
        """Bind this Node to simulator"""
        self.simulator = simulator  # Save simulator obj ref.
        simulator.add_element(self)  # Simulator detects this Node
    
    def get_sim_time(self):
        """Get simulator time. Actually fetch time from simulator and returns to ites elements like DL."""
        return self.simulator.get_sim_time()
    
    def bind_channels(self, Tx_chann, Rx_chann):  # Channel??
        """Bind channels to this Node. one channel for Tx and one for Rx."""
        # Tx
        self.Tx_chann = Tx_chann
        Tx_chann.bind_Tx(self)
        # Rx
        self.Rx_chann = Rx_chann
        Rx_chann.bind_Rx(self)

    def bind_element(self, elem_name, elem):
        """Bind elements (L1, L2, L3"""
        assert elem_name in ("L1", "L2", "L3"), f'unknown layer: {elem_name}'
        self.__setattr__(elem_name, elem)  # register element to Node
        elem.assign_Node(self)  # element detects its parent (Node)
    
    def from_L1_to_chann(self, IDU:dict):
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.Tx_chann.call_from_L1(IDU)
    
    def from_chann_to_L1(self, PDU:dict):  # exception: PDU instead of IDU because of channel
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.L1.call_from_chann(PDU)
    
    def from_L1_to_L2(self, IDU:dict):
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.L2.call_from_L1(IDU)
    
    def from_L2_to_L1(self, IDU:dict):
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.L1.call_from_L2(IDU)
    
    def from_L2_to_L3(self, IDU:dict):
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.L3.call_from_L2(IDU)
    
    def from_L3_to_L2(self, IDU:dict):
        """This function provide a platform to interact between layers while each layer does not know other layers type."""
        return self.L2.call_from_L3(IDU)

    def add_event(self, event):
        """Add new event to Node event queue."""
        self.event_queue.add_event(event)
    
    def ret_event_queue(self):
        """Return event queue. Use for find nearest event in all Nodes."""
        return self.event_queue
    
    def set_event_queue(self, queue):
        """Set event queue."""
        return self.event_queue.set_events(queue)
    
    def event_run(self):
        """Run nearest event in this Node. This function used when `Simulator` detects nearest event in all Nodes is in this Node."""
        event = self.event_queue.pop_event()
        # check for event layer. Switch case!
        if event[1][:2] == 'DL':  # e.g. event[1] = 'DL timeout' => event[1][:2]='DL' => DL event
            self.L2.event_run(event)
        else:
            raise ValueError(f"Unknown event layer {event[1]}")


# Data network layers
## L3 elements
class Source:
    """Generate radom fixed size packets in L3 and give that to L2."""
    def __init__(self, packet_size:int) -> None:
        """`packet_size`: Size of each packet. Each packet has a fixed size"""
        self.packet_size = packet_size
        self.Node = None
    
    def assign_Node(self, Node:Node):
        """Assign this Source to `Node` that contains this Source."""
        self.Node = Node

    def send_packet(self):
        """generate packet and send to L2.
            Out:
                `packet`: generated packet
                `pack_size`: length of packet i.e. `self.pack_size"""
        IDU = {'PDU':{'frame':getrandbits(self.packet_size), 'frame_size':self.packet_size}, 'SDU':None}
        self.Node.from_L3_to_L2(IDU)
        return
    
    def call_from_L2(self, IDU):
        """An event that L3 receives IDU from L2."""
        if IDU['SDU'] == 'push':
            self.send_packet()
        else:
            raise ValueError(f"Unknown IDU for L3 {IDU}")
    

class Sink:
    """Recieve packets from L2 and count them (for utilization calculating)."""
    def __init__(self) -> None:
        self.counter = 0
        self.Node = None
    
    def assign_Node(self, Node:Node):
        """Assign this Sink to `Node` that contains this Sink."""
        self.Node = Node

    def recv_packet(self, PDU:dict):
        """Recieve packet and count that. Assume that if packet passed to this layer, accept it."""
        self.counter += 1
    
    def call_from_L2(self, IDU):
        """An event that L3 receives frame from L2."""
        if IDU['SDU'] == None:
            self.recv_packet(IDU['PDU'])
        else:
            raise ValueError(f"Unknown IDU for L3 {IDU}")


## L1 elements
class PHY:
    """Get frame from L2 and injects in Tx channel+ Get frame from channel and pass that to L2."""
    def __init__(self, checker:CRC):
        """`checker`: coding tool that add some bits to frame tail for 
            ensure frame is valid. It has 2 method :`encode`, `decode`"""
        self.checker = checker
        self.Node = None  # Node that contains this PHY
    
    def assign_Node(self, Node:Node):
        """Assign this PHY to `Node` that contains this PHY."""
        self.Node = Node
    
    def call_from_chann(self, PDU:dict):
        """An event that PHY receives frame from channel.
            first check frame validation (like CRC) and if it was valid pass frame to L2, if not drops it.
            `PDU`: [Dict] recovered packet from channel. It contains `frame`, `frame_size`."""
        dec_frame, dec_frame_size, status = self.checker.decode(PDU['frame'], PDU['frame_size'])
        if status == False:  # invalid frame
            return  # Do nithing
        # valid frame -> pass to L2
        IDU_L2 = {'PDU':{'frame':dec_frame, 'frame_size':dec_frame_size}, 'SDU':None}
        self.Node.from_L1_to_L2(IDU_L2)
    
    def call_from_L2(self, IDU:dict):
        """An event that PHY receives frame from L2.
            first add frame validation (like CRC) and then send to channel.
            `IDU`: [Dict] Contains `PDU` and `SDU`."""
        if not(IDU['SDU'] is None):  # A command to channel e.g. cancel current packet transmission
            return self.Node.from_L1_to_chann(IDU)
        # Packet transmission in channel
        PDU = IDU['PDU']
        enc_frame, enc_frame_size = self.checker.encode(PDU['frame'], PDU['frame_size'])
        IDU_chann = {'PDU':{'frame':enc_frame, 'frame_size':enc_frame_size}, 'SDU':None}
        t_done = self.Node.from_L1_to_chann(IDU_chann)  # time that transmission has done.
        return t_done

# PHY Channel
class Channel:
    """Binary symmetric channel (BSC).
        `p`: error probability
        `R_T`: Transmission Rate
        `D_p`: propagation delay"""
    
    def __init__(self, p, R_T, D_p) -> None:
        self.p = p  # error probility
        self.R_T = R_T  # transmission rate
        self.D_p = D_p  # propagation delay

        self.event_queue = Event_queues()
        self.spare_time = 0  # nearest time that channel is free and ready to inject new packet.
    
    def bind_sim(self, simulator:Simulator):
        """Bind this Node to simulator"""
        self.simulator = simulator  # Save simulator obj ref.
        simulator.add_element(self)  # Simulator detects this Node
    
    def get_sim_time(self):
        """Get simulator time. Actually fetch time from simulator and returns to ites elements like DL."""
        return self.simulator.get_sim_time()
    
    def bind_Tx(self, Node:Node):
        """Bind Node to Tx port of this channel."""
        self.Tx_Node = Node
    
    def bind_Rx(self, Node:Node):
        """Bind Node to Rx port of this channel."""
        self.Rx_Node = Node
    
    def call_from_L1(self, IDU):
        """An event that channel receives frame from PHY.
            It could be 2 state: 1-packet transmitting 2-command(e.g. cancel transmitting)."""
        if not(IDU['SDU'] is None):  # A command to channel e.g. cancel current packet transmission
            if IDU['SDU'] == 'cancel transmit':
                event = self.event_queue.pop_event()  # pop acts like delete event from queue.
                assert event[1] == 'ch transmit', f"Unknown event for channel {event[1]}"  # check for event type
                return
        # Packet transmitting
        assert self.spare_time <= self.get_sim_time(), "Channel is occupied! You can't transmit new packet"
        return self.inject_chann(IDU['PDU'])

    def inject_chann(self, PDU:dict):
        """Inject frame(packet) into channel. This channel affect 2 parameters:
            1-Transmission delay(`R_T`) 2-Propagation delay(`D_p`)"""
        D_transmission = PDU['frame_size']/self.R_T  # Transmission delay
        self.spare_time = self.get_sim_time()+D_transmission  # at this time, PHY is free and can inject new packet into channel.
        event = (self.spare_time+self.D_p,  # timestamp
                'ch transmit',  # command
                PDU)  # data: in this case PDU.
        self.event_queue.add_event(event)
        return self.spare_time  # Transmission delay
    
    def recv_chann(self, PDU:dict):
        """Affect noise to packet and then pass it to PHY."""
        err = sum(map(lambda ind: 1<<ind if random()<self.p else 0, range(PDU['frame_size'])))  # BSC error
        # err = reduce(lambda x,y:(x<<1)|y, np.where(np.random.rand(PDU['frame_size'])>self.p,0,1))  # BSC error
        PDU['frame'] = err ^ PDU['frame']  # Add noise
        
        self.Rx_Node.from_chann_to_L1(PDU)  # call PHY to receives packet

    def ret_event_queue(self):
        """Return event queue. Use for find nearest event in all Nodes."""
        return self.event_queue
    
    def event_run(self):
        """Run nearest event. In this case PHY receives packet from channel."""
        event = self.event_queue.pop_event()
        # check for event type. Switch case!
        if event[1] == 'ch transmit':
            PDU = event[2]  # extract PDU
            return self.recv_chann(PDU)
        else:
            raise ValueError(f"Unknown event for channel {event[1]}")


if __name__=='__main__':
    pass