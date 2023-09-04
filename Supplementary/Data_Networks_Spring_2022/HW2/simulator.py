# Data network simulator 
class Event_queues:
    """This queue can store events in order of time. If you add a event, queue automatically 
        insert event that every event before new event has smaller timestamp.
        You can use one or more instances of this class e.g. 1 queue for Tx chann, 
        1 for Rx chann and 1 for Tx, Rx `OR` 1 queue for all elements.
        
        Events are tuple with `(timestamp, command, data)` format. for example:
        `(0.02, 'chann transmit', {'frame':0xAB23, 'frame_size':16})`"""
    
    def __init__(self) -> None:
        self.queue = []
        self.size = 0
    
    def __len__(self) -> int:
        """Retutn size of waiting events in queue."""
        return self.size
    
    def __repr__(self) -> str:
        return self.queue.__repr__()
    
    def __iter__(self):
        """Create iterator. Use for map, filter, reduce operations."""
        return self.queue.__iter__()

    def has_event(self):
        """Return wether queue is not empty or not i.e. len>0 => True; len==0 =>False"""
        return self.size > 0

    def clear_event(self):
        self.queue = []
        self.size = 0
    
    def add_event(self, event:tuple) -> None:
        """Add new event to queue."""
        self.insort_left(event)
        self.size += 1  # Increase queue length
    
    def nearest_event_time(self):
        """Return nearest event timestamp."""
        assert self.size != 0, "Queue has no event."
        return self.queue[0][0]  # first 0: nearest event, second 0: timestamp
    
    def set_events(self, queue):
        """Set events."""
        self.queue = queue
        self.size = len(queue)
    
    def pop_event(self, index=0):
        """Pop an event in queue.
            Default: nearest event."""
        assert self.size != 0, "Queue has no event."
        self.size -= 1
        return self.queue.pop(index)
    
    def insort_left(self, event):
        """Inspired by `bisect` module.
            Insert new `event` in queue, and keep it sorted. If new `event` has same timestamp 
            with another event in queue, insert new event to the left of the leftmost such events."""
        lo = 0;
        hi = self.size
        while lo < hi:
            mid = (lo+hi)//2
            if self.queue[mid][0] < event[0]:lo = mid+1  # 0: event timestamp
            else: hi = mid
        self.queue.insert(lo, event)


class Simulator:
    """Simulator engine"""
    def __init__(self) -> None:
        self.elements = []  # Initialize network elements list
        self.time = float(0)  # Initialize simulation time

    def add_element(self, element) -> None:
        """Add elements to simulator e.g. Node, channel"""
        self.elements.append(element)

    def get_sim_time(self) -> float:
        """Return simulation time."""
        return self.time
    
    def nearest_event(self):
        """Find nearest event across all elements."""
        node_event = enumerate(map(lambda elem: elem.ret_event_queue(), self.elements))  # Extract all events queue + enumerate
        node_has_event = filter(lambda n_e: n_e[1].has_event(), node_event)  # Extract event queues has at least 1 event.
        node_time_event = min(node_has_event, key=lambda n_e: n_e[1].nearest_event_time())  # Find nearest event across all nodes
        return node_time_event  # Maybe need some exception handling
    
    def run(self, t_end, t_start=0) -> None:
        self.time = t_start
        step = 1  # counter
        while self.time <= t_end:
            elem_ind, event = self.nearest_event()
            new_time = event.nearest_event_time()
            assert new_time >= self.time, "Bad timinig! New event occured in past!!"
            self.time = new_time  # Update time
            self.elements[elem_ind].event_run()  # Run nearest event!
            step += 1