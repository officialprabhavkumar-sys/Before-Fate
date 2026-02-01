from queue import Queue

from GeneralVerifier import verifier
from WorldTime import WorldTimeStamp

class TimeScheduledCommand():
    def __init__(self, execution_time : WorldTimeStamp, actions : list[dict]):
        self.execution_time : WorldTimeStamp = verifier.verify_type(execution_time, WorldTimeStamp, "execution_time")
        self.actions = verifier.verify_type(actions, list, "actions")
    
    def to_dict(self) -> dict:
        return {"execution_time" : self.execution_time.to_dict(), "actions" : self.actions}
    
class TimedScheduler():
    def __init__(self):
        self.time_buckets : dict[int, list[int]] = {}
        self.actions : dict[int, dict] = {}
        self._next_id = 0
    
    @property
    def _sorted_order(self) -> list:
        return sorted(list(self.time_buckets.keys()))
    
    @property
    def next_id(self) -> int:
        self._next_id += 1
        return self._next_id
    
    def schedule(self, command : TimeScheduledCommand) -> None:
        time_id = command.execution_time.get_time_id()
        next_id = self.next_id
        if time_id in self.time_buckets:
            self.time_buckets[time_id].append(next_id)
        else:
            self.time_buckets[time_id] = [next_id]
        self.actions[next_id] = command.actions
    
    def pop_ready(self, time_stamp : WorldTimeStamp) -> list[dict]:
        time_id = time_stamp.get_time_id()
        
        commands = []
        sorted_times = self._sorted_order
        for scheduled_time_id in sorted_times:
            if scheduled_time_id > time_id:
                break
            for command_id in self.time_buckets[scheduled_time_id]:
                commands.extend(self.actions.pop(command_id))
            self.time_buckets.pop(scheduled_time_id)
        if len(self) == 0:
            self._next_id = 0
        return commands
    
    def pending(self, time_stamp : WorldTimeStamp) -> bool:
        sorted_order = self._sorted_order
        if len(sorted_order) == 0:
            return False
        return (sorted_order[0] <= time_stamp.get_time_id())
    
    def add_pending_to_command_queue(self, time_stamp : WorldTimeStamp, command_queue : CommandQueue) -> None:
        pending_commands = self.pop_ready(time_stamp = time_stamp)
        if len(pending_commands) == 0:
            return
        for pending_command in pending_commands:
            command_queue.add(pending_command)
    
    def to_dict(self) -> dict:
        return {"time_buckets" : self.time_buckets, "actions" : self.actions, "_next_id" : self._next_id}
    
    def load(self, data : dict):
        verifier.verify_type(data, dict, "data")
        self.time_buckets = data["time_buckets"]
        self.actions = data["actions"]
        self._next_id = data["_next_id"]
    
    def __len__(self) -> int:
        return len(self.actions)
    
class CommandQueue():
    def __init__(self):
        self.queue = Queue()
    
    def add(self, command : dict) -> None:
        self.queue.put(verifier.verify_type(command, dict, "command"))
    
    def empty(self) -> bool:
        return self.queue.empty()
    
    #blocking
    def get(self) -> dict:
        return self.queue.get()
    
    #non blocking
    def get_if_present(self) -> dict:
        if not self.queue.empty():
            return self.queue.get()